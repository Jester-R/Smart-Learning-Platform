from collections import defaultdict
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.permissions import (
    is_admin,
    is_student,
    is_teacher,
    is_university_admin,
)
from apps.courses.models import Enrollment

from .forms import AcademicCalendarForm, ClassScheduleForm, ExamScheduleForm
from .models import AcademicCalendar, ClassSchedule, ExamSchedule


def _require_view_permission(user):
    if not user.has_permission("schedule.view"):
        raise PermissionDenied("You do not have permission to view schedules.")


def _can_manage(user):
    return user.has_permission("schedule.manage") and (
        is_admin(user)
        or is_university_admin(user)
        or is_teacher(user)
        or user.has_role("instructor")
    )


def _visible_schedules(user):
    queryset = ClassSchedule.objects.filter(is_active=True).select_related(
        "course", "lecturer", "university"
    )
    if is_admin(user) or is_university_admin(user):
        return queryset
    if is_teacher(user) or user.has_role("instructor"):
        return queryset.filter(Q(lecturer=user) | Q(course__teacher=user)).distinct()
    if is_student(user):
        return queryset.filter(
            course__enrollments__student=user,
            course__enrollments__status=Enrollment.Status.ACTIVE,
        ).distinct()
    return queryset.none()


def _visible_exams(user):
    queryset = ExamSchedule.objects.filter(is_published=True).select_related(
        "course", "exam"
    )
    if is_admin(user) or is_university_admin(user):
        return queryset
    if is_teacher(user) or user.has_role("instructor"):
        return queryset.filter(course__teacher=user).distinct()
    if is_student(user):
        return queryset.filter(
            course__enrollments__student=user,
            course__enrollments__status=Enrollment.Status.ACTIVE,
        ).distinct()
    return queryset.none()


@login_required
def timetable(request):
    _require_view_permission(request.user)
    schedules = list(_visible_schedules(request.user))
    days = [
        {"value": value, "label": label}
        for value, label in ClassSchedule.Weekday.choices
    ]
    for day in days:
        day["items"] = [item for item in schedules if item.day_of_week == day["value"]]
    return render(
        request,
        "academic/timetable.html",
        {
            "days": days,
            "can_manage": _can_manage(request.user),
            "total_sessions": len(schedules),
        },
    )


@login_required
def academic_calendar(request):
    _require_view_permission(request.user)
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month
    month = min(max(month, 1), 12)

    events = AcademicCalendar.objects.filter(
        is_published=True, start_date__year=year, start_date__month=month
    ).select_related("university")
    return render(
        request,
        "academic/calendar.html",
        {
            "events": events,
            "year": year,
            "month": month,
            "months": range(1, 13),
            "month_name": date(year, month, 1).strftime("%B"),
            "can_manage": _can_manage(request.user),
        },
    )


@login_required
def exam_schedule(request):
    _require_view_permission(request.user)
    visible = _visible_exams(request.user)
    now = timezone.now()
    period = request.GET.get("period", "all")
    schedules = visible
    if period == "upcoming":
        schedules = schedules.filter(start_at__gte=now)
    elif period == "past":
        schedules = schedules.filter(end_at__lt=now)

    by_day = defaultdict(list)
    for item in schedules:
        by_day[timezone.localtime(item.start_at).date()].append(item)
    days = [
        {
            "date": day,
            "label": day.strftime("%A, %d %B %Y"),
            "items": items,
            "count": len(items),
        }
        for day, items in sorted(by_day.items())
    ]
    return render(
        request,
        "academic/exam_schedule.html",
        {
            "days": days,
            "period": period,
            "now": now,
            "total_exams": visible.count(),
            "upcoming_count": visible.filter(start_at__gte=now).count(),
            "can_manage": _can_manage(request.user),
        },
    )


@login_required
def schedule_create(request):
    if not _can_manage(request.user):
        raise PermissionDenied("You do not have permission to manage schedules.")
    form = ClassScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Class schedule created.")
        return redirect("academic:timetable")
    return render(
        request,
        "academic/form.html",
        {
            "form": form,
            "title": "Add class schedule",
            "cancel_url": "academic:timetable",
        },
    )


@login_required
def calendar_event_create(request):
    if not _can_manage(request.user):
        raise PermissionDenied("You do not have permission to manage the calendar.")
    form = AcademicCalendarForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Calendar event created.")
        return redirect("academic:calendar")
    return render(
        request,
        "academic/form.html",
        {
            "form": form,
            "title": "Add calendar event",
            "cancel_url": "academic:calendar",
        },
    )


@login_required
def exam_schedule_create(request):
    if not _can_manage(request.user):
        raise PermissionDenied("You do not have permission to manage exam schedules.")
    form = ExamScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Exam schedule created.")
        return redirect("academic:exam_schedule")
    return render(
        request,
        "academic/form.html",
        {
            "form": form,
            "title": "Add exam schedule",
            "cancel_url": "academic:exam_schedule",
        },
    )
