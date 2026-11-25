from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.permissions import (
    RoleRequiredMixin,
    can_access_course,
    can_manage_course,
    is_student,
    is_admin,
    is_teacher,
    is_university_admin,
    role_required,
)
from apps.accounts.models import PlatformConfiguration, User
from apps.analytics.models import ActivityLog
from apps.courses.models import Course, Enrollment

from .forms import AttendanceRecordForm, LearningMaterialForm, LessonForm, VideoLessonForm
from .models import (
    AttendanceRecord,
    CourseProgress,
    LearningMaterial,
    LearningProgress,
    Lesson,
    extract_youtube_video_id,
)


def _get_course(slug):
    return get_object_or_404(Course, slug=slug)


def _require_access(request, course, published_only=True):
    if can_manage_course(request.user, course):
        return
    if not can_access_course(request.user, course):
        raise PermissionDenied("Enroll in this course to access its content.")
    if published_only and course.status != Course.Status.PUBLISHED:
        raise PermissionDenied("This course is not published.")


@login_required
def lesson_detail(request, slug, pk):
    """Display lesson viewer with responsive YouTube video player, playlist, and progress."""
    course = _get_course(slug)
    _require_access(request, course)
    lesson = get_object_or_404(Lesson, pk=pk, course=course)
    is_manager = can_manage_course(request.user, course)
    if not lesson.is_published and not is_manager:
        raise PermissionDenied("This lesson is not published.")

    progress = None
    course_progress = None
    completed_lesson_ids = set()

    if is_student(request.user):
        progress, _ = LearningProgress.objects.get_or_create(
            student=request.user, lesson=lesson
        )
        course_progress, _ = CourseProgress.objects.get_or_create(
            student=request.user, course=course
        )
        course_progress.last_lesson = lesson
        course_progress.save(update_fields=["last_lesson", "updated_at"])

        completed_lesson_ids = set(
            LearningProgress.objects.filter(
                student=request.user,
                lesson__course=course,
                is_completed=True,
            ).values_list("lesson_id", flat=True)
        )

    lessons = course.lessons.filter(is_published=True).order_by("order")
    if is_manager:
        lessons = course.lessons.order_by("order")
    lesson_list = list(lessons)

    previous_lesson = None
    next_lesson = None
    for index, item in enumerate(lesson_list):
        if item.pk == lesson.pk:
            if index > 0:
                previous_lesson = lesson_list[index - 1]
            if index < len(lesson_list) - 1:
                next_lesson = lesson_list[index + 1]
            break

    # Group lessons by chapter for structured navigation
    chapter_map = {}
    for item in lesson_list:
        ch_name = item.chapter.strip() if item.chapter else "General Lessons"
        if ch_name not in chapter_map:
            chapter_map[ch_name] = []
        chapter_map[ch_name].append(item)

    chapter_groups = [{"chapter": k, "lessons": v} for k, v in chapter_map.items()]
    total_lessons = len(lesson_list)
    completed_count = len(completed_lesson_ids)

    return render(
        request,
        "learning/lesson_detail.html",
        {
            "course": course,
            "lesson": lesson,
            "progress": progress,
            "course_progress": course_progress,
            "materials": lesson.materials.all(),
            "is_manager": is_manager,
            "video_downloads_enabled": PlatformConfiguration.get_solo().video_downloads_enabled,
            "previous_lesson": previous_lesson,
            "next_lesson": next_lesson,
            "lesson_list": lesson_list,
            "chapter_groups": chapter_groups,
            "completed_lesson_ids": completed_lesson_ids,
            "total_lessons": total_lessons,
            "completed_count": completed_count,
        },
    )


@login_required
def lesson_video_file(request, slug, pk):
    course = _get_course(slug)
    _require_access(request, course)
    lesson = get_object_or_404(Lesson, pk=pk, course=course)
    is_manager = can_manage_course(request.user, course)
    if not lesson.is_published and not is_manager:
        raise PermissionDenied("This lesson is not published.")
    if not lesson.video_file:
        raise Http404("No uploaded video is attached to this lesson.")

    download = request.GET.get("download") == "1"
    configuration = PlatformConfiguration.get_solo()
    if download and not is_admin(request.user):
        if not configuration.video_downloads_enabled or not lesson.video_downloadable:
            raise PermissionDenied("Video downloads are currently disabled.")

    return FileResponse(
        lesson.video_file.open("rb"),
        as_attachment=download,
        filename=lesson.video_file.name.split("/")[-1],
    )


@role_required("student")
def mark_complete(request, slug, pk):
    """Mark a lesson as completed by the student, updating learning and course progress."""
    course = _get_course(slug)
    if request.method != "POST":
        return redirect("learning:lesson", slug=slug, pk=pk)

    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({"success": False, "error": "Enroll in this course first."}, status=403)
        raise PermissionDenied("Enroll in this course first.")

    lesson = get_object_or_404(Lesson, pk=pk, course=course)
    progress, _ = LearningProgress.objects.get_or_create(
        student=request.user, lesson=lesson
    )

    if not progress.is_completed:
        progress.mark_completed()
        course_progress, _ = CourseProgress.objects.get_or_create(
            student=request.user, course=course
        )
        course_progress.last_lesson = lesson
        course_progress.save(update_fields=["last_lesson", "updated_at"])
        course_progress.recalculate()
        messages.success(request, f"Lesson '{lesson.title}' marked as completed.")

    if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
        course_progress = CourseProgress.objects.filter(student=request.user, course=course).first()
        total_lessons = course.lessons.filter(is_published=True).count()
        completed_lessons = LearningProgress.objects.filter(
            student=request.user,
            lesson__course=course,
            lesson__is_published=True,
            is_completed=True,
        ).count()
        return JsonResponse({
            "success": True,
            "is_completed": True,
            "progress_percent": float(course_progress.progress_percent) if course_progress else 0,
            "completed_count": completed_lessons,
            "total_count": total_lessons,
            "message": f"Lesson '{lesson.title}' marked as completed.",
        })

    return redirect("learning:lesson", slug=slug, pk=pk)


@role_required("teacher", "admin")
def lesson_toggle_publish(request, slug, pk):
    """Quickly toggle the published status of a video lesson."""
    course = _get_course(slug)
    if not can_manage_course(request.user, course):
        raise PermissionDenied
    lesson = get_object_or_404(Lesson, pk=pk, course=course)
    if request.method == "POST":
        lesson.is_published = not lesson.is_published
        lesson.save(update_fields=["is_published", "updated_at"])
        status_label = "published" if lesson.is_published else "unpublished"
        messages.success(request, f"Lesson '{lesson.title}' is now {status_label}.")

        if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({
                "success": True,
                "is_published": lesson.is_published,
                "status_label": "Published" if lesson.is_published else "Draft",
            })

    return redirect(request.META.get("HTTP_REFERER") or course.get_absolute_url())


@login_required
def material_download(request, slug, pk):
    course = _get_course(slug)
    _require_access(request, course)
    material = get_object_or_404(LearningMaterial, pk=pk, course=course)
    if is_student(request.user) and not material.is_downloadable:
        raise PermissionDenied("This material is not available for download.")
    if material.external_url:
        return HttpResponseRedirect(material.external_url)
    if not material.file:
        raise Http404("No file is attached to this material.")
    return FileResponse(
        material.file.open("rb"),
        as_attachment=True,
        filename=material.file.name.split("/")[-1],
    )


class LessonFormMixin(RoleRequiredMixin):
    allowed_roles = ("teacher", "admin")

    def dispatch(self, request, *args, **kwargs):
        self.course = _get_course(kwargs.get("slug"))
        if not can_manage_course(request.user, self.course):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["course"] = self.course
        return kwargs


@role_required("teacher", "admin")
def lesson_create(request, slug):
    course = _get_course(slug)
    if not can_manage_course(request.user, course):
        raise PermissionDenied
    next_order = course.lessons.count() + 1
    form = VideoLessonForm(
        request.POST or None,
        request.FILES or None,
        course=course,
        user=request.user,
        initial={"order": next_order, "is_published": True},
    )
    if request.method == "POST" and form.is_valid():
        lesson = form.save()
        messages.success(request, f"Lesson '{lesson.title}' created.")
        return redirect("learning:lesson", slug=course.slug, pk=lesson.pk)
    return render(
        request,
        "learning/lesson_form.html",
        {
            "form": form,
            "course": course,
            "title": "Add Video Lesson",
            "is_video_lesson": True,
        },
    )


@role_required("teacher", "admin")
def lesson_update(request, slug, pk):
    course = _get_course(slug)
    if not can_manage_course(request.user, course):
        raise PermissionDenied
    lesson = get_object_or_404(Lesson, pk=pk, course=course)
    form = VideoLessonForm(
        request.POST or None,
        request.FILES or None,
        instance=lesson,
        course=course,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Lesson '{lesson.title}' updated.")
        return redirect("learning:lesson", slug=course.slug, pk=lesson.pk)
    return render(
        request,
        "learning/lesson_form.html",
        {
            "form": form,
            "course": course,
            "lesson": lesson,
            "title": f"Edit Lesson: {lesson.title}",
            "is_video_lesson": True,
        },
    )


@role_required("teacher", "admin")
def lesson_delete(request, slug, pk):
    course = _get_course(slug)
    if not can_manage_course(request.user, course):
        raise PermissionDenied
    lesson = get_object_or_404(Lesson, pk=pk, course=course)
    if request.method == "POST":
        title = lesson.title
        lesson.delete()
        messages.success(request, f"Lesson '{title}' deleted.")
        return redirect(course.get_absolute_url())
    return render(
        request,
        "confirm_delete.html",
        {"object": lesson, "cancel_url": course.get_absolute_url()},
    )


@role_required("teacher", "admin")
def teacher_video_manage(request):
    """Dedicated management page for teachers to manage YouTube video lessons."""
    user = request.user
    if user.is_superuser or getattr(user, "role", None) == "admin":
        courses_qs = Course.objects.all()
        lessons_qs = Lesson.objects.all()
    else:
        courses_qs = Course.objects.filter(teacher=user)
        lessons_qs = Lesson.objects.filter(course__teacher=user)

    courses_qs = courses_qs.order_by("code")

    course_filter = request.GET.get("course", "").strip()
    status_filter = request.GET.get("status", "").strip()
    query = request.GET.get("q", "").strip()

    if course_filter:
        lessons_qs = lessons_qs.filter(course_id=course_filter)
    if status_filter == "published":
        lessons_qs = lessons_qs.filter(is_published=True)
    elif status_filter == "draft":
        lessons_qs = lessons_qs.filter(is_published=False)
    if query:
        lessons_qs = lessons_qs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(chapter__icontains=query)
            | Q(course__title__icontains=query)
            | Q(course__code__icontains=query)
        )

    lessons = lessons_qs.select_related("course").order_by("course__code", "order")

    base_qs = Lesson.objects.all() if (user.is_superuser or getattr(user, "role", None) == "admin") else Lesson.objects.filter(course__teacher=user)
    total_count = base_qs.count()
    published_count = base_qs.filter(is_published=True).count()
    draft_count = base_qs.filter(is_published=False).count()
    youtube_count = base_qs.exclude(youtube_video_id="").count()
    total_minutes = sum(base_qs.values_list("duration_minutes", flat=True))

    return render(
        request,
        "learning/teacher_videos.html",
        {
            "lessons": lessons,
            "courses": courses_qs,
            "selected_course": course_filter,
            "selected_status": status_filter,
            "query": query,
            "total_count": total_count,
            "published_count": published_count,
            "draft_count": draft_count,
            "youtube_count": youtube_count,
            "total_minutes": total_minutes,
        },
    )


@role_required("teacher", "admin")
def teacher_video_create(request):
    """Global add video lesson form from the Teacher Dashboard."""
    course_slug = request.GET.get("course")
    preset_course = None
    if course_slug:
        preset_course = get_object_or_404(Course, slug=course_slug)
        if not can_manage_course(request.user, preset_course):
            raise PermissionDenied

    if request.method == "POST":
        form = VideoLessonForm(request.POST, user=request.user, course=preset_course)
        if form.is_valid():
            lesson = form.save()
            messages.success(request, f"YouTube video lesson '{lesson.title}' created.")
            return redirect("learning:lesson", slug=lesson.course.slug, pk=lesson.pk)
    else:
        initial = {"is_published": True}
        if preset_course:
            initial["order"] = preset_course.lessons.count() + 1
        form = VideoLessonForm(user=request.user, course=preset_course, initial=initial)

    return render(
        request,
        "learning/lesson_form.html",
        {
            "form": form,
            "course": preset_course,
            "title": "Add YouTube Video Lesson",
            "is_video_lesson": True,
        },
    )


@login_required
def youtube_validate_api(request):
    """API endpoint to validate YouTube URL and return video metadata."""
    url = request.GET.get("url") or request.POST.get("url", "")
    video_id = extract_youtube_video_id(url)
    if not video_id:
        return JsonResponse(
            {
                "valid": False,
                "error": "Invalid YouTube URL format.",
            },
            status=400,
        )
    return JsonResponse(
        {
            "valid": True,
            "video_id": video_id,
            "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1&enablejsapi=1",
            "watch_url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        }
    )


@role_required("teacher", "admin")
def material_create(request, slug):
    course = _get_course(slug)
    if not can_manage_course(request.user, course):
        raise PermissionDenied
    form = LearningMaterialForm(
        request.POST or None, request.FILES or None, course=course
    )
    if request.method == "POST" and form.is_valid():
        material = form.save(commit=False)
        material.uploaded_by = request.user
        material.save()
        messages.success(request, "Learning material uploaded.")
        return redirect(course.get_absolute_url())
    return render(
        request,
        "learning/material_form.html",
        {"form": form, "course": course},
    )


ATTENDANCE_PAGE_SIZE = 50
ATTENDANCE_EXPORT_LIMIT = 2000


def attendance_report_queryset(user):
    """Return ``(queryset, scope)`` of attendance records visible to *user*."""
    queryset = AttendanceRecord.objects.select_related(
        "student", "course", "recorded_by"
    )
    if is_student(user):
        return queryset.filter(student=user), "student"
    if is_admin(user) or is_university_admin(user):
        return queryset, "admin"
    if (
        is_teacher(user)
        or user.has_role("lecturer")
        or user.has_role("instructor")
    ):
        return queryset.filter(course__teacher=user), "teacher"
    raise PermissionDenied


@login_required
def attendance_record(request):
    user = request.user
    can_record = user.has_permission("attendance.record") and (
        is_admin(user)
        or is_university_admin(user)
        or is_teacher(user)
        or user.has_role("lecturer")
        or user.has_role("instructor")
    )
    if not can_record:
        raise PermissionDenied("You do not have permission to record attendance.")

    courses = Course.objects.all()
    if not (is_admin(user) or is_university_admin(user)):
        courses = courses.filter(teacher=user)
    students = User.objects.filter(
        role__in=["student", "free_student", "student_pro", "student_premium"]
    )
    form = AttendanceRecordForm(
        request.POST or None, courses=courses, students=students
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            record, created = AttendanceRecord.objects.update_or_create(
                student=form.cleaned_data["student"],
                course=form.cleaned_data["course"],
                date=form.cleaned_data["date"],
                defaults={
                    "status": form.cleaned_data["status"],
                    "remarks": form.cleaned_data["remarks"],
                    "recorded_by": user,
                },
            )
            ActivityLog.objects.create(
                user=user,
                action=ActivityLog.Action.UPDATE,
                model_name="AttendanceRecord",
                object_id=record.pk,
                description=(
                    f"{'Recorded' if created else 'Updated'} attendance for "
                    f"{record.student.full_name} in {record.course.code}"
                ),
                metadata={
                    "status": record.status,
                    "date": record.date.isoformat(),
                    "created": created,
                },
            )
        messages.success(request, "Attendance saved.")
        return redirect("learning:attendance_record")
    return render(
        request,
        "learning/attendance_record.html",
        {"form": form},
    )


@login_required
def attendance(request):
    """Show attendance records for students, teachers, or administrators.

    Students only see their own attendance, teachers see the courses they
    teach, and administrators see every record.
    """
    records_query, scope = attendance_report_queryset(request.user)
    student_view = scope == "student"
    page_title = {
        "student": "My attendance",
        "teacher": "Course attendance",
        "admin": "Attendance records",
    }[scope]

    statuses = AttendanceRecord.Status
    totals = {choice.value: 0 for choice in statuses}
    for row in records_query.values("status").annotate(total=Count("id")):
        totals[row["status"]] = row["total"]

    total_sessions = sum(totals.values())
    attended = totals[statuses.PRESENT.value] + totals[statuses.LATE.value]
    attendance_rate = (
        round(attended / total_sessions * 100, 1) if total_sessions else None
    )

    summary_rows = list(
        records_query.values(
            "course_id", "course__code", "course__title", "status"
        ).annotate(total=Count("id"))
    )
    courses_by_id = Course.objects.in_bulk(
        {row["course_id"] for row in summary_rows}
    )
    course_summaries = {}
    for row in summary_rows:
        summary = course_summaries.setdefault(
            row["course_id"],
            {
                "course": courses_by_id[row["course_id"]],
                "present": 0,
                "late": 0,
                "absent": 0,
                "excused": 0,
                "total": 0,
            },
        )
        summary[row["status"]] += row["total"]
        summary["total"] += row["total"]

    for summary in course_summaries.values():
        attended_sessions = summary["present"] + summary["late"]
        summary["rate"] = round(attended_sessions / summary["total"] * 100, 1)
        summary["is_low"] = summary["rate"] < 75

    paginator = Paginator(
        records_query.order_by("-date", "course__code", "-id"),
        ATTENDANCE_PAGE_SIZE,
    )
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "learning/attendance.html",
        {
            "page_title": page_title,
            "student_view": student_view,
            "scope": scope,
            "records": page_obj,
            "page_obj": page_obj,
            "totals": totals,
            "total_sessions": total_sessions,
            "attendance_rate": attendance_rate,
            "course_summaries": course_summaries.values(),
        },
    )


@login_required
def attendance_export_pdf(request):
    """Download a PDF attendance report for the signed-in user's scope."""
    from html import escape
    from io import BytesIO
    from pathlib import Path

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    records_query, scope = attendance_report_queryset(request.user)
    records_query = records_query.order_by("-date", "course__code", "-id")

    totals_rows = records_query.values("status").annotate(total=Count("id"))
    totals = {choice.value: 0 for choice in AttendanceRecord.Status}
    for row in totals_rows:
        totals[row["status"]] = row["total"]

    total_sessions = sum(totals.values())
    attended = totals["present"] + totals["late"]
    attendance_rate = (
        round(attended / total_sessions * 100, 1) if total_sessions else None
    )
    records = list(records_query[:ATTENDANCE_EXPORT_LIMIT])
    truncated = total_sessions > len(records)

    student_view = scope == "student"
    scope_label = {
        "student": f"Attendance for {request.user.full_name}",
        "teacher": "Attendance for your courses",
        "admin": "All platform attendance",
    }[scope]
    filename_scope = {
        "student": "my-attendance",
        "teacher": "course-attendance",
        "admin": "all-attendance",
    }[scope]

    buffer = BytesIO()
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="smart-learning-{filename_scope}-'
        f'{timezone.localtime():%Y%m%d}.pdf"'
    )
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        title="Smart Learning Platform Attendance Report",
        author="Smart Learning Platform",
    )

    styles = getSampleStyleSheet()
    font_name = "Helvetica"
    font_bold = "Helvetica-Bold"
    for font_path in (
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("SLPAttendanceFont", str(font_path)))
            font_name = font_bold = "SLPAttendanceFont"
            break

    title_style = ParagraphStyle(
        "AttendanceReportTitle",
        parent=styles["Title"],
        fontName=font_bold,
        textColor=colors.HexColor("#24283b"),
        alignment=TA_LEFT,
        fontSize=18,
        leading=22,
        spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "AttendanceReportMeta",
        parent=styles["Normal"],
        fontName=font_name,
        textColor=colors.HexColor("#565f89"),
        fontSize=9,
        leading=12,
    )
    cell_style = ParagraphStyle(
        "AttendanceReportCell",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#24283b"),
    )
    header_style = ParagraphStyle(
        "AttendanceReportHeader",
        parent=cell_style,
        fontName=font_bold,
        textColor=colors.white,
    )

    if student_view:
        headers = ("Date", "Course", "Status", "Remarks")
        widths = [30 * mm, 85 * mm, 25 * mm, 125 * mm]
    else:
        headers = ("Date", "Course", "Student", "Status", "Remarks")
        widths = [26 * mm, 65 * mm, 45 * mm, 22 * mm, 107 * mm]
    data = [[Paragraph(label, header_style) for label in headers]]

    for record in records:
        row = [
            Paragraph(record.date.strftime("%b %d, %Y"), cell_style),
            Paragraph(
                escape(f"{record.course.code} - {record.course.title}"),
                cell_style,
            ),
        ]
        if not student_view:
            row.append(Paragraph(escape(record.student.full_name), cell_style))
        row.extend(
            [
                Paragraph(escape(record.get_status_display()), cell_style),
                Paragraph(
                    escape(record.remarks).replace("\n", "<br/>") or "-",
                    cell_style,
                ),
            ]
        )
        data.append(row)

    rate_display = (
        f"{attendance_rate:.1f}%" if attendance_rate is not None else "n/a"
    )
    story = [
        Paragraph("Smart Learning Platform", title_style),
        Paragraph(
            f"Attendance report - {scope_label}<br/>"
            f"Generated {timezone.localtime():%b %d, %Y %H:%M} - "
            f"Total {total_sessions} - Present {totals['present']} - "
            f"Late {totals['late']} - Absent {totals['absent']} - "
            f"Excused {totals['excused']} - Rate {rate_display}",
            small_style,
        ),
        Spacer(1, 8 * mm),
    ]

    if truncated:
        story.append(
            Paragraph(
                f"Showing the most recent {len(records)} of {total_sessions} records.",
                small_style,
            )
        )
        story.append(Spacer(1, 3 * mm))

    if records:
        table = Table(data, colWidths=widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3d59a1")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#eef1fa")],
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7cce0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(table)
    else:
        story.append(
            Paragraph("No attendance records have been recorded yet.", small_style)
        )

    doc.build(story)
    response.content = buffer.getvalue()
    return response


@role_required("teacher", "admin")
def material_delete(request, slug, pk):
    course = _get_course(slug)
    if not can_manage_course(request.user, course):
        raise PermissionDenied
    material = get_object_or_404(LearningMaterial, pk=pk, course=course)
    if request.method == "POST":
        material.delete()
        messages.success(request, "Learning material deleted.")
        return redirect(course.get_absolute_url())
    return render(
        request,
        "confirm_delete.html",
        {"object": material, "cancel_url": course.get_absolute_url()},
    )
