from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.analytics.models import ActivityLog

from .forms import ScholarshipApplicationForm, ScholarshipForm
from .models import Scholarship, ScholarshipApplication


def _require_permission(user, code):
    if not user.is_authenticated or not user.has_permission(code):
        raise PermissionDenied("You do not have permission for this action.")


def scholarship_list(request):
    scholarships = Scholarship.objects.filter(is_published=True).select_related(
        "category", "university"
    )
    return render(request, "scholarships/list.html", {"scholarships": scholarships})


def scholarship_detail(request, pk):
    scholarship = get_object_or_404(Scholarship, pk=pk, is_published=True)
    applied = (
        request.user.is_authenticated
        and ScholarshipApplication.objects.filter(
            scholarship=scholarship, student=request.user
        ).exists()
    )
    return render(
        request,
        "scholarships/detail.html",
        {"scholarship": scholarship, "applied": applied},
    )


@login_required
def scholarship_create(request):
    _require_permission(request.user, "scholarship.manage")
    form = ScholarshipForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        scholarship = form.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.CREATE,
            model_name="Scholarship",
            object_id=scholarship.pk,
            description=f"Created scholarship {scholarship.title}",
        )
        messages.success(request, "Scholarship created.")
        return redirect("scholarships:detail", pk=scholarship.pk)
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Create scholarship", "cancel_url": "scholarships:list"},
    )


@login_required
def scholarship_apply(request, pk):
    _require_permission(request.user, "scholarship.view")
    scholarship = get_object_or_404(Scholarship, pk=pk, is_published=True)
    if ScholarshipApplication.objects.filter(
        scholarship=scholarship, student=request.user
    ).exists():
        messages.info(request, "You have already applied for this scholarship.")
        return redirect("scholarships:detail", pk=scholarship.pk)
    form = ScholarshipApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.scholarship = scholarship
        application.student = request.user
        application.save()
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.CREATE,
            model_name="ScholarshipApplication",
            object_id=application.pk,
            description=f"Applied for scholarship {scholarship.title}",
        )
        messages.success(request, "Scholarship application submitted.")
        return redirect("scholarships:my_applications")
    return render(
        request,
        "phase4/form.html",
        {"form": form, "title": "Apply for scholarship", "cancel_url": "scholarships:list"},
    )


@login_required
def my_applications(request):
    applications = ScholarshipApplication.objects.filter(student=request.user).select_related(
        "scholarship"
    )
    return render(request, "scholarships/my_applications.html", {"applications": applications})
