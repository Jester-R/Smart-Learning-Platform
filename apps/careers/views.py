from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from apps.accounts.permissions import is_admin
from apps.analytics.models import ActivityLog

from .forms import (
    ApplicationMessageForm,
    CVUploadForm,
    CompanyProfileForm,
    JobApplicationForm,
    JobForm,
)
from .models import ApplicationMessage, CVDocument, CompanyProfile, Job, JobApplication


def _require_permission(user, code):
    if not user.is_authenticated or not user.has_permission(code):
        raise PermissionDenied("You do not have permission for this action.")


def _company_for(user):
    return CompanyProfile.objects.filter(user=user).first()


def _is_hr(user):
    return is_admin(user) or bool(
        user.is_authenticated and user.has_permission("job.post") and _company_for(user)
    )


def job_list(request):
    positions = Job.objects.filter(status=Job.Status.PUBLISHED, is_approved=True).select_related(
        "company", "package"
    )
    total_positions = positions.count()
    internship_count = positions.filter(job_type=Job.JobType.INTERNSHIP).count()
    query = request.GET.get("q", "").strip()
    job_type = request.GET.get("job_type", "").strip()
    jobs = positions
    if query:
        jobs = jobs.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if job_type:
        jobs = jobs.filter(job_type=job_type)
    return render(
        request,
        "careers/job_list.html",
        {
            "jobs": jobs,
            "query": query,
            "job_type": job_type,
            "job_types": Job.JobType.choices,
            "total_positions": total_positions,
            "internship_count": internship_count,
        },
    )


def job_detail(request, pk):
    job = get_object_or_404(
        Job.objects.select_related("company"),
        pk=pk,
        status=Job.Status.PUBLISHED,
        is_approved=True,
    )
    has_applied = (
        request.user.is_authenticated
        and JobApplication.objects.filter(job=job, applicant=request.user).exists()
    )
    return render(request, "careers/job_detail.html", {"job": job, "has_applied": has_applied})


@login_required
def company_profile(request):
    _require_permission(request.user, "company.manage_own")
    profile = _company_for(request.user)
    form = CompanyProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        profile = form.save(commit=False)
        profile.user = request.user
        profile.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.UPDATE,
            model_name="CompanyProfile",
            object_id=profile.pk,
            description=f"Updated company profile for {profile.company_name}",
        )
        messages.success(request, "Company profile saved.")
        return redirect("careers:company_profile")
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Company profile", "cancel_url": "careers:job_list"},
    )


@login_required
def job_create(request):
    _require_permission(request.user, "job.post")
    company = _company_for(request.user)
    if company is None:
        messages.error(request, "Create and get your company profile approved before posting jobs.")
        return redirect("careers:company_profile")
    form = JobForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.company = company
        job.status = Job.Status.PENDING
        job.is_approved = False
        job.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.CREATE,
            model_name="Job",
            object_id=job.pk,
            description=f"Submitted job posting {job.title} for approval",
        )
        messages.success(request, "Job submitted for approval.")
        return redirect("careers:company_jobs")
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Post a job", "cancel_url": "careers:company_jobs"},
    )


@login_required
def company_jobs(request):
    _require_permission(request.user, "job.post")
    company = _company_for(request.user)
    jobs = Job.objects.filter(company=company).select_related("package") if company else Job.objects.none()
    return render(request, "careers/company_jobs.html", {"jobs": jobs})


@login_required
def job_apply(request, pk):
    _require_permission(request.user, "job.apply")
    job = get_object_or_404(
        Job, pk=pk, status=Job.Status.PUBLISHED, is_approved=True
    )
    if JobApplication.objects.filter(job=job, applicant=request.user).exists():
        messages.info(request, "You have already applied for this job.")
        return redirect("careers:job_detail", pk=job.pk)
    form = JobApplicationForm(request.POST or None, request.FILES or None)
    form.fields["cv_document"].queryset = request.user.cv_documents.all()
    form.fields["cv_document"].help_text = format_html(
        'Or manage saved CVs in <a href="{}">My CVs</a>.',
        reverse("careers:my_cvs"),
    )
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        uploaded_cv = form.cleaned_data.get("cv_file")
        if uploaded_cv:
            document = CVDocument.objects.create(
                student=request.user,
                title=f"CV for {job.title}",
                file=uploaded_cv,
            )
            application.cv_document = document
        application.job = job
        application.applicant = request.user
        application.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.CREATE,
            model_name="JobApplication",
            object_id=application.pk,
            description=f"Applied for {job.title}",
        )
        messages.success(request, "Application submitted.")
        return redirect("careers:my_applications")
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Apply for job", "cancel_url": "careers:job_list"},
    )


@login_required
def my_applications(request):
    _require_permission(request.user, "job.apply")
    applications = JobApplication.objects.filter(applicant=request.user).select_related(
        "job", "job__company"
    )
    return render(request, "careers/my_applications.html", {"applications": applications})


@login_required
def all_applications(request):
    if not _is_hr(request.user):
        raise PermissionDenied("You do not have permission to view applications.")
    applications = JobApplication.objects.select_related(
        "applicant", "job", "job__company", "cv_document"
    )
    if not is_admin(request.user):
        applications = applications.filter(job__company=_company_for(request.user))
    total_count = applications.count()
    status = request.GET.get("status", "").strip()
    if status:
        applications = applications.filter(status=status)
    return render(
        request,
        "careers/all_applications.html",
        {
            "applications": applications,
            "status": status,
            "status_choices": JobApplication.Status.choices,
            "total_count": total_count,
        },
    )


@login_required
def application_conversation(request, pk):
    application = get_object_or_404(
        JobApplication.objects.select_related(
            "applicant", "job", "job__company", "cv_document"
        ),
        pk=pk,
    )
    company = _company_for(request.user)
    is_owner = application.applicant_id == request.user.id
    is_hr = _is_hr(request.user) and (
        is_admin(request.user) or (company is not None and application.job.company_id == company.pk)
    )
    if not (is_owner or is_hr):
        raise PermissionDenied("You cannot view this conversation.")

    if request.method == "POST":
        form = ApplicationMessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.application = application
            message.sender = request.user
            message.save()
            ApplicationMessage.objects.filter(application=application).exclude(
                sender=request.user
            ).update(is_read=True)
            messages.success(request, "Message sent to the interview contact.")
            return redirect("careers:application_conversation", pk=application.pk)
    else:
        form = ApplicationMessageForm()

    thread = application.messages.select_related("sender")
    thread.exclude(sender=request.user).update(is_read=True)
    return render(
        request,
        "careers/conversation.html",
        {
            "application": application,
            "thread": thread,
            "form": form,
            "is_hr": is_hr,
            "current_user_id": request.user.id,
        },
    )


@login_required
def my_cvs(request):
    _require_permission(request.user, "job.apply")
    form = CVUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.student = request.user
        document.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.CREATE,
            model_name="CVDocument",
            object_id=document.pk,
            description=f"Uploaded CV {document.title}",
        )
        messages.success(request, "CV uploaded. Select it when you apply for a job.")
        return redirect("careers:my_cvs")
    return render(
        request,
        "careers/my_cvs.html",
        {"form": form, "documents": request.user.cv_documents.all()},
    )


@login_required
@require_POST
def cv_delete(request, pk):
    _require_permission(request.user, "job.apply")
    document = get_object_or_404(CVDocument, pk=pk, student=request.user)
    title = document.title
    document.delete()
    ActivityLog.objects.create(
        user=request.user,
        action=ActivityLog.Action.DELETE,
        model_name="CVDocument",
        object_id=pk,
        description=f"Deleted CV {title}",
    )
    messages.success(request, "CV deleted.")
    return redirect("careers:my_cvs")
