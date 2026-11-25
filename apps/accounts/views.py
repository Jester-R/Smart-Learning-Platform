from smtplib import SMTPException

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView

from apps.academic.models import AcademicCalendar, ClassSchedule, ExamSchedule
from apps.analytics.models import ActivityLog
from apps.careers.models import ApplicationMessage, CompanyProfile, Job, JobApplication
from apps.core.models import (
    Department,
    EmailVerificationToken,
    Faculty,
    PasswordResetToken,
    Role,
    University,
    UserRole,
)
from apps.assessments.models import (
    Assignment,
    Exam,
    Grade,
    Quiz,
    QuizAttempt,
    ExamAttempt,
    Submission,
)
from apps.assessments.services import calculate_gpa, format_percentage, weighted_percentage
from apps.certificates.models import Certificate
from apps.courses.models import Course, Enrollment
from apps.learning.models import CourseProgress, LearningProgress, Lesson
from apps.notifications.models import Announcement, Notification

from .forms import (
    EmailAuthenticationForm,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    PlatformConfigurationForm,
    ProfileForm,
    StudentProfileForm,
    StudentRegistrationForm,
)
from .models import PlatformConfiguration, StudentProfile, User
from .permissions import (
    is_admin,
    is_company,
    is_student,
    is_teacher,
    is_university_admin,
    role_required,
)


class AppLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        if user.account_status != User.AccountStatus.ACTIVE:
            ActivityLog.objects.create(
                user=user,
                action=ActivityLog.Action.UPDATE,
                model_name="User",
                object_id=user.pk,
                description=f"Sign-in blocked: account {user.account_status}",
                ip_address=get_client_ip(self.request),
                user_agent=self.request.META.get("HTTP_USER_AGENT", "")[:300],
            )
            form.add_error(
                None,
                "This account is not active. Contact support if you need assistance.",
            )
            return self.form_invalid(form)

        response = super().form_valid(form)
        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.LOGIN,
            description="Signed in",
            ip_address=get_client_ip(self.request),
            user_agent=self.request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        messages.success(self.request, f"Welcome back, {self.request.user.full_name}.")
        if not self.request.user.is_verified:
            messages.info(self.request, "Please verify your email address.")
        return response


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def send_verification_email(user, token):
    link = (
        f"{settings.SITE_URL.rstrip('/')}"
        f"{reverse('accounts:verify_email')}?uid={user.pk}&token={token.token}"
    )
    message = (
        f"Hello {user.full_name},\n\n"
        f"Verify your All-in-One Student Portal email address:\n{link}\n\n"
        "If you did not create this account, you can ignore this message."
    )
    try:
        send_mail(
            "Verify your email address",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except (SMTPException, OSError):
        return False


def send_password_reset_email(user, token):
    link = (
        f"{settings.SITE_URL.rstrip('/')}"
        f"{reverse('accounts:password_reset_confirm', args=[user.pk, token.token])}"
    )
    message = (
        f"Hello {user.full_name},\n\n"
        f"Use this link to reset your password:\n{link}\n\n"
        "The link expires soon. If you did not request it, ignore this message."
    )
    try:
        send_mail(
            "Reset your password",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except (SMTPException, OSError):
        return False


class RegisterView(CreateView):
    form_class = StudentRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.object.role == User.Role.STUDENT:
            StudentProfile.objects.get_or_create(user=self.object)

        verification_token = EmailVerificationToken.create_for_user(self.object)
        email_sent = send_verification_email(self.object, verification_token)

        login(self.request, self.object)
        ActivityLog.objects.create(
            user=self.object,
            action=ActivityLog.Action.CREATE,
            model_name="User",
            object_id=self.object.pk,
            description=f"{self.object.get_role_display()} account registered",
            ip_address=get_client_ip(self.request),
        )
        messages.success(
            self.request,
            "Your account has been created. Check your email for the verification link."
            if email_sent
            else "Your account has been created. Contact support to verify your email.",
        )
        return response


def verify_email(request):
    uid = request.GET.get("uid")
    token_value = request.GET.get("token")
    if not uid or not token_value:
        messages.error(request, "The verification link is incomplete.")
        return redirect("accounts:login")

    user = get_object_or_404(User, pk=uid)
    verification = EmailVerificationToken.objects.filter(
        user=user, token=token_value
    ).first()
    if verification is None or not verification.is_valid():
        messages.error(request, "This verification link is invalid or has expired.")
        return redirect("accounts:login")

    user.is_verified = True
    user.email_verified_at = timezone.now()
    user.save(update_fields=["is_verified", "email_verified_at", "updated_at"])
    verification.mark_used()
    ActivityLog.objects.create(
        user=user,
        action=ActivityLog.Action.UPDATE,
        model_name="User",
        object_id=user.pk,
        description="Email address verified",
        ip_address=get_client_ip(request),
    )

    if not request.user.is_authenticated or request.user.pk != user.pk:
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Your email address has been verified.")
    return redirect("dashboard")


@login_required
def resend_verification(request):
    if request.user.is_verified:
        messages.info(request, "Your email address is already verified.")
        return redirect("accounts:profile")

    token = EmailVerificationToken.create_for_user(request.user)
    sent = send_verification_email(request.user, token)
    messages.success(
        request,
        "A new verification link has been sent."
        if sent
        else "Email delivery failed. Contact support for verification.",
    )
    return redirect("accounts:profile")


def password_reset_request(request):
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            user = User.objects.filter(email=email, account_status=User.AccountStatus.ACTIVE).first()
            if user is not None:
                token = PasswordResetToken.create_for_user(user)
                send_password_reset_email(user, token)
                ActivityLog.objects.create(
                    user=user,
                    action=ActivityLog.Action.UPDATE,
                    model_name="User",
                    object_id=user.pk,
                    description="Password reset requested",
                    ip_address=get_client_ip(request),
                )
            messages.success(
                request,
                "If an active account uses that email, a reset link has been sent.",
            )
            return redirect("accounts:login")
    else:
        form = PasswordResetRequestForm()

    return render(request, "accounts/password_reset_request.html", {"form": form})


def password_reset_confirm(request, uid, token_value):
    user = get_object_or_404(User, pk=uid)
    reset = PasswordResetToken.objects.filter(user=user, token=token_value).first()
    if reset is None or not reset.is_valid():
        messages.error(request, "This password reset link is invalid or has expired.")
        return redirect("accounts:password_reset_request")

    if request.method == "POST":
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data["new_password1"])
            user.save(update_fields=["password", "updated_at"])
            PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
                used_at=timezone.now()
            )
            ActivityLog.objects.create(
                user=user,
                action=ActivityLog.Action.UPDATE,
                model_name="User",
                object_id=user.pk,
                description="Password reset completed",
                ip_address=get_client_ip(request),
            )
            messages.success(request, "Your password has been reset. Sign in to continue.")
            return redirect("accounts:login")
    else:
        form = PasswordResetConfirmForm()

    return render(
        request,
        "accounts/password_reset_confirm.html",
        {"form": form, "user_email": user.email},
    )


@login_required
def dashboard(request):
    user = request.user

    if is_admin(user):
        role_counts = {
            row["role"]: row["count"]
            for row in User.objects.values("role").annotate(count=Count("id"))
        }
        total_users = User.objects.count()
        total_students = role_counts.get(User.Role.STUDENT, 0)
        total_teachers = role_counts.get(User.Role.TEACHER, 0)
        total_admins = role_counts.get(User.Role.ADMIN, 0)

        course_status_counts = {
            row["status"]: row["count"]
            for row in Course.objects.values("status").annotate(count=Count("id"))
        }
        total_courses = sum(course_status_counts.values())
        published_courses = course_status_counts.get(Course.Status.PUBLISHED, 0)
        draft_courses = course_status_counts.get(Course.Status.DRAFT, 0)
        archived_courses = course_status_counts.get(Course.Status.ARCHIVED, 0)

        enrollment_status_counts = {
            row["status"]: row["count"]
            for row in Enrollment.objects.values("status").annotate(count=Count("id"))
        }
        total_enrollments = sum(enrollment_status_counts.values())
        active_enrollments = enrollment_status_counts.get(Enrollment.Status.ACTIVE, 0)
        completed_enrollments = enrollment_status_counts.get(
            Enrollment.Status.COMPLETED, 0
        )
        pending_submissions = Submission.objects.filter(
            status=Submission.Status.SUBMITTED
        ).count()
        certificates_issued = Certificate.objects.filter(
            status=Certificate.Status.VALID
        ).count()

        def percent(part, whole):
            return round(part / whole * 100) if whole else 0

        completion_rate = percent(completed_enrollments, total_enrollments)
        active_enrollment_rate = percent(active_enrollments, total_enrollments)

        student_percent = percent(total_students, total_users)
        teacher_percent = percent(total_teachers, total_users)
        admin_percent = max(0, 100 - student_percent - teacher_percent)
        role_gradient = (
            "conic-gradient("
            f"#7C3AED 0 {admin_percent}%, "
            f"#A78BFA {admin_percent}% {admin_percent + teacher_percent}%, "
            f"#C4B5FD {admin_percent + teacher_percent}% 100%)"
        )

        popular_courses = list(
            Course.objects.annotate(student_count=Count("enrollments"))
            .select_related("category", "teacher")
            .order_by("-student_count", "code")[:5]
        )
        max_course_students = max(
            (course.student_count for course in popular_courses), default=0
        )
        for course in popular_courses:
            course.enrollment_bar_percent = (
                round(course.student_count / max_course_students * 100)
                if max_course_students
                else 0
            )

        configuration = PlatformConfiguration.get_solo()
        ai_configured = bool(
            settings.GEMINI_API_KEY or configuration.get_gemini_api_key()
        )
        hour = timezone.localtime().hour
        greeting = (
            "Good morning" if hour < 12
            else "Good afternoon" if hour < 18
            else "Good evening"
        )

        context = {
            "greeting": greeting,
            "total_users": total_users,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_admins": total_admins,
            "total_courses": total_courses,
            "published_courses": published_courses,
            "draft_courses": draft_courses,
            "archived_courses": archived_courses,
            "published_percent": percent(published_courses, total_courses),
            "draft_percent": percent(draft_courses, total_courses),
            "archived_percent": percent(archived_courses, total_courses),
            "total_enrollments": total_enrollments,
            "active_enrollments": active_enrollments,
            "completed_enrollments": completed_enrollments,
            "active_enrollment_rate": active_enrollment_rate,
            "completion_rate": completion_rate,
            "pending_submissions": pending_submissions,
            "certificates_issued": certificates_issued,
            "total_lessons": Lesson.objects.count(),
            "total_assignments": Assignment.objects.count(),
            "total_quizzes": Quiz.objects.count(),
            "total_exams": Exam.objects.count(),
            "total_announcements": Announcement.objects.count(),
            "total_notifications": Notification.objects.count(),
            "student_percent": student_percent,
            "teacher_percent": teacher_percent,
            "admin_percent": admin_percent,
            "role_gradient": role_gradient,
            "recent_users": User.objects.order_by("-date_joined")[:6],
            "recent_activity": ActivityLog.objects.select_related("user")[:10],
            "popular_courses": popular_courses,
            "platform_configuration": configuration,
            "ai_configured": ai_configured,
        }
        return render(request, "dashboard/admin.html", context)

    if is_teacher(user):
        courses = Course.objects.filter(teacher=user).annotate(
            student_count=Count("enrollments", distinct=True),
            lesson_count=Count("lessons", distinct=True),
        )
        recent_video_lessons = (
            Lesson.objects.filter(course__teacher=user)
            .select_related("course")
            .order_by("-updated_at")[:6]
        )
        video_count = (
            Lesson.objects.filter(course__teacher=user)
            .exclude(youtube_video_id="")
            .count()
        )
        context = {
            "courses": courses,
            "course_count": courses.count(),
            "student_count": Enrollment.objects.filter(
                course__teacher=user, status=Enrollment.Status.ACTIVE
            )
            .values("student")
            .distinct()
            .count(),
            "video_count": video_count,
            "recent_video_lessons": recent_video_lessons,
            "pending_submissions": Submission.objects.filter(
                assignment__course__teacher=user,
                status=Submission.Status.SUBMITTED,
            )
            .select_related("student", "assignment")[:10],
            "pending_count": Submission.objects.filter(
                assignment__course__teacher=user,
                status=Submission.Status.SUBMITTED,
            ).count(),
            "quiz_count": Quiz.objects.filter(course__teacher=user).count(),
            "exam_count": Exam.objects.filter(course__teacher=user).count(),
            "recent_submissions": Submission.objects.filter(
                assignment__course__teacher=user
            )
            .select_related("student", "assignment")
            .order_by("-submitted_at")[:15],
        }
        return render(request, "dashboard/teacher.html", context)

    if is_company(user):
        company = CompanyProfile.objects.filter(user=user).first()
        company_jobs = Job.objects.filter(company=company).select_related("package")
        company_applications = JobApplication.objects.none()
        company_messages = ApplicationMessage.objects.none()
        if company:
            company_applications = (
                JobApplication.objects.filter(job__company=company)
                .select_related("applicant", "job", "cv_document")
                .order_by("-created_at")[:8]
            )
            company_messages = (
                ApplicationMessage.objects.filter(application__job__company=company)
                .select_related("application", "sender")
                .order_by("-created_at")[:8]
            )
        context = {
            "company_profile": company,
            "company_job_count": company_jobs.count(),
            "published_job_count": company_jobs.filter(
                status=Job.Status.PUBLISHED
            ).count(),
            "company_application_count": (
                JobApplication.objects.filter(job__company=company).count()
                if company
                else 0
            ),
            "shortlisted_count": (
                JobApplication.objects.filter(
                    job__company=company, status=JobApplication.Status.SHORTLISTED
                ).count()
                if company
                else 0
            ),
            "unread_company_messages": (
                ApplicationMessage.objects.filter(
                    application__job__company=company, is_read=False
                )
                .exclude(sender=user)
                .count()
                if company
                else 0
            ),
            "company_jobs": company_jobs[:6],
            "company_applications": company_applications,
            "company_messages": company_messages,
        }
        return render(request, "dashboard/company.html", context)

    if is_university_admin(user):
        role_link = (
            UserRole.objects.filter(user=user, university__isnull=False)
            .select_related("university")
            .first()
        )
        university = (
            role_link.university
            if role_link
            else University.objects.filter(is_active=True).order_by("id").first()
        )
        schedules = ClassSchedule.objects.none()
        events = AcademicCalendar.objects.none()
        exams = ExamSchedule.objects.none()
        if university:
            schedules = ClassSchedule.objects.filter(university=university)
            events = AcademicCalendar.objects.filter(university=university)
            exams = ExamSchedule.objects.filter(
                course__in=ClassSchedule.objects.filter(
                    university=university
                ).values("course_id")
            )
        context = {
            "university": university,
            "faculty_count": (
                Faculty.objects.filter(university=university).count()
                if university
                else 0
            ),
            "department_count": (
                Department.objects.filter(faculty__university=university).count()
                if university
                else 0
            ),
            "university_role_count": (
                UserRole.objects.filter(university=university).count()
                if university
                else 0
            ),
            "university_schedule_count": schedules.count(),
            "university_calendar_count": events.count(),
            "university_exam_count": exams.count(),
            "university_schedules": schedules.select_related("course", "lecturer")[:6],
            "university_events": events[:6],
            "university_exams": exams.select_related("course", "exam")[:6],
            "university_faculties": (
                Faculty.objects.filter(university=university).prefetch_related("departments")
                if university
                else Faculty.objects.none()
            ),
        }
        return render(request, "dashboard/university.html", context)

    enrollments = (
        Enrollment.objects.filter(student=user)
        .select_related("course", "course__teacher", "course__category")
        .order_by("-enrolled_at")
    )
    course_ids = list(enrollments.values_list("course_id", flat=True))
    now = timezone.now()

    grades = list(Grade.objects.filter(student=user))
    weighted_average = weighted_percentage(grades)
    average_grade = format_percentage(weighted_average)
    gpa = calculate_gpa(grades)

    # Progress mapping for template
    all_course_progress = list(CourseProgress.objects.filter(student=user).select_related("course"))
    progress_map = {cp.course_id: cp for cp in all_course_progress}

    # Find continue-watching lessons for enrolled courses
    completed_lesson_ids = set(
        LearningProgress.objects.filter(
            student=user, is_completed=True
        ).values_list("lesson_id", flat=True)
    )
    continue_watching_lessons = []
    for enr in enrollments.filter(status=Enrollment.Status.ACTIVE):
        next_lesson = (
            enr.course.lessons.filter(is_published=True)
            .exclude(id__in=completed_lesson_ids)
            .order_by("order")
            .first()
        )
        if not next_lesson:
            # If all completed, get the last lesson or first lesson
            next_lesson = enr.course.lessons.filter(is_published=True).order_by("order").first()
        if next_lesson:
            continue_watching_lessons.append({
                "lesson": next_lesson,
                "course": enr.course,
                "is_completed": next_lesson.id in completed_lesson_ids,
                "progress_percent": progress_map.get(enr.course_id).progress_percent if enr.course_id in progress_map else 0,
            })
    continue_watching_lessons = continue_watching_lessons[:4]

    context = {
        "enrollments": enrollments,
        "enrollment_count": enrollments.count(),
        "completed_courses": enrollments.filter(
            status=Enrollment.Status.COMPLETED
        ).count(),
        "completed_lessons": LearningProgress.objects.filter(
            student=user, is_completed=True
        ).count(),
        "progress": progress_map,
        "continue_watching_lessons": continue_watching_lessons,
        "upcoming_assignments": Assignment.objects.filter(
            course_id__in=course_ids,
            is_published=True,
            due_at__gte=now,
        )
        .select_related("course")
        .order_by("due_at")[:5],
        "open_quizzes": Quiz.objects.filter(
            course_id__in=course_ids, is_published=True
        )
        .filter(Q(closes_at__isnull=True) | Q(closes_at__gte=now))
        .select_related("course")
        .order_by("closes_at")[:5],
        "open_exams": Exam.objects.filter(
            course_id__in=course_ids, is_published=True
        )
        .filter(Q(closes_at__isnull=True) | Q(closes_at__gte=now))
        .select_related("course")
        .order_by("closes_at")[:5],
        "average_grade": average_grade,
        "gpa": format_percentage(gpa),
        "certificates": Certificate.objects.filter(
            student=user, status=Certificate.Status.VALID
        ).select_related("course")[:5],
        "notifications": Notification.objects.filter(
            recipient=user, is_read=False
        )[:5],
        "course_progress": CourseProgress.objects.filter(student=user)
        .select_related("course")
        .order_by("-updated_at")[:5],
        "in_progress_attempts": QuizAttempt.objects.filter(
            student=user, status=QuizAttempt.Status.IN_PROGRESS
        ).count()
        + ExamAttempt.objects.filter(
            student=user, status=ExamAttempt.Status.IN_PROGRESS
        ).count(),
    }
    return render(request, "dashboard/student.html", context)


@login_required
def platform_settings(request):
    from importlib.util import find_spec

    if not is_admin(request.user):
        raise PermissionDenied
    configuration = PlatformConfiguration.get_solo()
    form = PlatformConfigurationForm(request.POST or None, instance=configuration)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except ImportError:
            form.add_error(
                "gemini_api_key",
                "Install the project requirements before saving an API key.",
            )
        else:
            messages.success(request, "Platform settings updated.")
            return redirect("accounts:platform_settings")

    return render(
        request,
        "accounts/platform_settings.html",
        {
            "form": form,
            "has_saved_api_key": bool(configuration.encrypted_gemini_api_key),
            "has_environment_api_key": bool(settings.GEMINI_API_KEY),
            "can_encrypt_api_key": find_spec("cryptography") is not None,
        },
    )


@login_required
def profile(request):
    user = request.user
    profile_form = ProfileForm(instance=user)
    student_profile = None
    student_form = None
    if is_student(user):
        student_profile, _ = StudentProfile.objects.get_or_create(user=user)
        student_form = StudentProfileForm(instance=student_profile)

    if request.method == "POST":
        profile_form = ProfileForm(request.POST, request.FILES, instance=user)
        forms_valid = profile_form.is_valid()
        if is_student(user):
            student_form = StudentProfileForm(
                request.POST, instance=student_profile
            )
            forms_valid = forms_valid and student_form.is_valid()
        if forms_valid:
            profile_form.save()
            if is_student(user):
                student_form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")

    return render(
        request,
        "accounts/profile.html",
        {
            "profile_form": profile_form,
            "student_form": student_form,
        },
    )


@role_required("admin")
def user_list(request):
    users = _filtered_users(request)
    role = request.GET.get("role", "")
    query = request.GET.get("q", "").strip()
    return render(
        request,
        "accounts/user_list.html",
        {"users": users, "role": role, "query": query, "roles": User.Role.choices},
    )


def _filtered_users(request):
    users = User.objects.all()
    role = request.GET.get("role", "")
    query = request.GET.get("q", "").strip()
    if role:
        users = users.filter(role=role)
    if query:
        users = users.filter(
            Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    return users.order_by("role", "last_name", "first_name", "email")


@role_required("admin")
def user_export_pdf(request):
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

    users = _filtered_users(request)
    buffer = BytesIO()
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="smart-learning-users.pdf"'
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        title="Smart Learning Platform User Report",
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
            pdfmetrics.registerFont(TTFont("SLPReportFont", str(font_path)))
            font_name = font_bold = "SLPReportFont"
            break
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], textColor=colors.HexColor("#24283b"),
        alignment=TA_LEFT, fontSize=18, leading=22, spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "ReportMeta", parent=styles["Normal"], textColor=colors.HexColor("#565f89"),
        fontSize=9, leading=12,
    )
    cell_style = ParagraphStyle(
        "ReportCell", parent=styles["Normal"], fontName=font_name, fontSize=8,
        leading=10, textColor=colors.HexColor("#24283b"),
    )
    header_style = ParagraphStyle(
        "ReportHeader", parent=cell_style, fontName=font_bold,
        textColor=colors.white,
    )
    data = [[Paragraph(label, header_style) for label in ("Name", "Email", "Role", "Status", "Joined")]]
    for user in users.iterator():
        data.append([
            Paragraph(escape(user.full_name), cell_style),
            Paragraph(escape(user.email), cell_style),
            Paragraph(escape(user.get_role_display()), cell_style),
            Paragraph("Active" if user.is_active else "Inactive", cell_style),
            Paragraph(user.date_joined.strftime("%b %d, %Y"), cell_style),
        ])

    story = [
        Paragraph("Smart Learning Platform", title_style),
        Paragraph("User report · generated " + timezone.localtime().strftime("%b %d, %Y %H:%M"), small_style),
        Spacer(1, 8 * mm),
    ]
    table = Table(data, colWidths=[48 * mm, 80 * mm, 40 * mm, 34 * mm, 38 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3d59a1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef1fa")]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7cce0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    doc.build(story)
    response.content = buffer.getvalue()
    return response
