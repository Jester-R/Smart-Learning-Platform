from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import is_admin, is_student, is_teacher
from apps.courses.models import Course
from apps.notifications.services import notify

from .models import Certificate
from .services import (
    check_eligibility,
    ensure_certificate_pdf,
    issue_certificate,
)


@login_required
def certificate_list(request):
    certificates = Certificate.objects.select_related(
        "student", "course", "issued_by"
    )
    if not is_admin(request.user):
        if is_student(request.user):
            certificates = certificates.filter(student=request.user)
        elif is_teacher(request.user):
            certificates = certificates.filter(course__teacher=request.user)
    total_count = certificates.count()
    valid_count = certificates.filter(status=Certificate.Status.VALID).count()
    return render(
        request,
        "certificates/list.html",
        {
            "certificates": certificates,
            "total_count": total_count,
            "valid_count": valid_count,
            "revoked_count": total_count - valid_count,
        },
    )


@login_required
def certificate_detail(request, pk):
    certificate = get_object_or_404(
        Certificate.objects.select_related("student", "course", "issued_by"), pk=pk
    )
    allowed = (
        is_admin(request.user)
        or certificate.student_id == request.user.id
        or certificate.course.teacher_id == request.user.id
    )
    if not allowed:
        raise PermissionDenied
    return render(
        request,
        "certificates/detail.html",
        {"certificate": certificate},
    )


@login_required
def claim_certificate(request, slug):
    if request.method != "POST":
        return redirect("courses:detail", slug=slug)
    course = get_object_or_404(Course, slug=slug)
    if not is_student(request.user):
        raise PermissionDenied
    try:
        certificate, created = issue_certificate(
            request.user, course, issued_by=course.teacher
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("courses:detail", slug=slug)
    if created:
        notify(
            request.user,
            "Certificate issued",
            f"Your certificate for {course.title} is ready.",
            kind="certificate",
            link=f"/certificates/{certificate.pk}/",
        )
        messages.success(request, "Certificate issued successfully.")
    else:
        messages.info(request, "A certificate already exists for this course.")
    return redirect("certificates:detail", pk=certificate.pk)


@login_required
def download_certificate(request, pk):
    certificate = get_object_or_404(
        Certificate.objects.select_related("student", "course"), pk=pk
    )
    allowed = (
        is_admin(request.user)
        or certificate.student_id == request.user.id
        or certificate.course.teacher_id == request.user.id
    )
    if not allowed:
        raise PermissionDenied
    ensure_certificate_pdf(certificate)
    return FileResponse(
        certificate.pdf_file.open("rb"),
        as_attachment=True,
        filename=f"{certificate.certificate_id}.pdf",
    )


def verify_certificate(request, code=None):
    query = code or request.GET.get("code", "").strip()
    certificate = None
    if query:
        certificate = (
            Certificate.objects.select_related("student", "course")
            .filter(verification_code__iexact=query)
            .first()
            or Certificate.objects.select_related("student", "course")
            .filter(certificate_id__iexact=query)
            .first()
        )
    return render(
        request,
        "certificates/verify.html",
        {"certificate": certificate, "query": query},
    )
