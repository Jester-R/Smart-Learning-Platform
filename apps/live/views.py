from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.permissions import is_admin, is_student, is_teacher
from apps.courses.models import Enrollment

from .forms import LiveSessionForm
from .models import LiveSession


def _visible_sessions(user):
    queryset = LiveSession.objects.filter(is_published=True).select_related(
        "course", "teacher"
    )
    if is_admin(user) or is_teacher(user):
        return queryset
    if is_student(user):
        return queryset.filter(course__enrollments__student=user).distinct()
    return queryset


def _can_manage(user):
    return is_admin(user) or is_teacher(user)


@login_required
def live_portal(request):
    sessions = _visible_sessions(request.user)
    now = timezone.now()
    context = {
        "live_now": sessions.filter(
            status=LiveSession.Status.LIVE, starts_at__lte=now, ends_at__gte=now
        ),
        "upcoming_sessions": sessions.filter(starts_at__gt=now).order_by("starts_at"),
        "recent_sessions": sessions.filter(ends_at__lte=now).order_by("-starts_at")[:8],
        "scheduled_count": sessions.filter(status=LiveSession.Status.SCHEDULED).count(),
        "live_count": sessions.filter(status=LiveSession.Status.LIVE).count(),
        "completed_count": sessions.filter(status=LiveSession.Status.ENDED).count(),
        "can_manage": _can_manage(request.user),
    }
    return render(request, "live/portal.html", context)


@login_required
def session_detail(request, pk):
    session = get_object_or_404(_visible_sessions(request.user), pk=pk)
    context = {
        "session": session,
        "attendee_count": Enrollment.objects.filter(course=session.course).count(),
        "can_manage": _can_manage(request.user),
    }
    return render(request, "live/detail.html", context)


@login_required
def session_create(request):
    if not _can_manage(request.user):
        raise PermissionDenied("You cannot schedule live sessions.")
    form = LiveSessionForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        session = form.save(commit=False)
        session.teacher = session.course.teacher if is_admin(request.user) else request.user
        session.save()
        messages.success(request, "Live session scheduled successfully.")
        return redirect("live:detail", pk=session.pk)
    return render(request, "live/session_form.html", {"form": form})
