from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, UpdateView

from apps.accounts.permissions import (
    RoleRequiredMixin,
    can_manage_course,
    is_admin,
    is_student,
    is_teacher,
    role_required,
)
from apps.assessments.models import Assignment, Exam, Quiz
from apps.learning.models import CourseProgress, LearningProgress
from apps.notifications.models import Announcement
from apps.analytics.models import ActivityLog

from .forms import CourseForm
from .models import Category, Course, Enrollment


@login_required
def course_list(request):
    user = request.user
    courses = Course.objects.select_related("teacher", "category").annotate(
        student_count=Count("enrollments", distinct=True)
    )

    if is_student(user):
        courses = courses.filter(status=Course.Status.PUBLISHED)
    elif is_teacher(user):
        courses = courses.filter(teacher=user)
    elif not is_admin(user):
        raise PermissionDenied

    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "")
    status = request.GET.get("status", "")

    if query:
        courses = courses.filter(
            Q(title__icontains=query)
            | Q(code__icontains=query)
            | Q(description__icontains=query)
        )
    if category_id:
        courses = courses.filter(category_id=category_id)
    if status and not is_student(user):
        courses = courses.filter(status=status)

    enrolled_ids = set()
    if is_student(user):
        enrolled_ids = set(
            Enrollment.objects.filter(student=user).values_list(
                "course_id", flat=True
            )
        )

    return render(
        request,
        "courses/course_list.html",
        {
            "courses": courses,
            "categories": Category.objects.filter(is_active=True),
            "category_id": category_id,
            "status": status,
            "query": query,
            "enrolled_ids": enrolled_ids,
            "can_manage": is_teacher(user) or is_admin(user),
        },
    )


@login_required
def course_detail(request, slug):
    course = get_object_or_404(
        Course.objects.select_related("teacher", "category"), slug=slug
    )
    is_manager = can_manage_course(request.user, course)
    if course.status != Course.Status.PUBLISHED and not is_manager:
        raise PermissionDenied("This course is not published.")

    enrollment = None
    enrolled = False
    if is_student(request.user):
        enrollment = Enrollment.objects.filter(
            student=request.user, course=course
        ).first()
        enrolled = enrollment is not None

    lessons = course.lessons.select_related("course")
    if not is_manager:
        lessons = lessons.filter(is_published=True)
    lessons = list(lessons.order_by("order"))

    completed_lesson_ids = set()
    course_progress = None
    if enrolled:
        completed_lesson_ids = set(
            LearningProgress.objects.filter(
                student=request.user,
                lesson__course=course,
                is_completed=True,
            ).values_list("lesson_id", flat=True)
        )
        course_progress = CourseProgress.objects.filter(
            student=request.user, course=course
        ).first()

    next_lesson = None
    if enrolled and lessons:
        next_lesson = next(
            (lesson for lesson in lessons if lesson.pk not in completed_lesson_ids),
            lessons[0],
        )

    assignments = course.assignments.select_related("course")
    quizzes = Quiz.objects.filter(course=course).annotate(
        question_count=Count("questions")
    )
    exams = Exam.objects.filter(course=course).annotate(
        question_count=Count("questions")
    )
    if not is_manager:
        assignments = assignments.filter(is_published=True)
        quizzes = quizzes.filter(is_published=True)
        exams = exams.filter(is_published=True)

    announcements = course.announcements.filter(is_published=True).select_related(
        "created_by"
    )
    if not is_manager:
        announcements = announcements.filter(
            Q(audience=Announcement.Audience.COURSE)
            | Q(audience=Announcement.Audience.EVERYONE)
            | Q(audience=Announcement.Audience.STUDENTS)
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
        )

    context = {
        "course": course,
        "enrollment": enrollment,
        "enrolled": enrolled,
        "is_manager": is_manager,
        "lessons": lessons,
        "materials": course.materials.filter(
            Q(lesson__isnull=True) | Q(lesson__is_published=True)
        ).select_related("lesson"),
        "assignments": assignments.order_by("-created_at"),
        "quizzes": quizzes.order_by("-created_at"),
        "exams": exams.order_by("-created_at"),
        "announcements": announcements[:5],
        "completed_lesson_ids": completed_lesson_ids,
        "course_progress": course_progress,
        "next_lesson": next_lesson,
        "enrollments": course.enrollments.select_related("student").order_by(
            "student__first_name"
        )
        if is_manager
        else None,
        "can_claim_certificate": False,
        "certificate": None,
    }

    if enrolled:
        from apps.certificates.models import Certificate
        from apps.certificates.services import check_eligibility

        certificate = Certificate.objects.filter(
            student=request.user, course=course, status=Certificate.Status.VALID
        ).first()
        context["certificate"] = certificate
        if not certificate and course.certificate_enabled:
            context["can_claim_certificate"] = check_eligibility(
                request.user, course
            )["eligible"]

    return render(request, "courses/course_detail.html", context)


@role_required("student")
def enroll(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if course.status != Course.Status.PUBLISHED:
        messages.error(request, "This course is not open for enrollment.")
        return redirect("courses:list")

    if course.price > 0:
        return redirect("courses:checkout", slug=course.slug)

    if request.method != "POST":
        return redirect(course.get_absolute_url())

    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=course,
        defaults={"status": Enrollment.Status.ACTIVE},
    )
    if not created:
        if enrollment.status == Enrollment.Status.DROPPED:
            enrollment.status = Enrollment.Status.ACTIVE
            enrollment.save(update_fields=["status", "updated_at"])
            messages.success(request, "Enrollment restored.")
        else:
            messages.info(request, "You are already enrolled in this course.")
    else:
        messages.success(request, f"You are now enrolled in {course.title}.")
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.ENROLL,
            model_name="Enrollment",
            object_id=enrollment.pk,
            description=f"Enrolled in {course.code}",
        )
    return redirect(course.get_absolute_url())


@login_required
def my_courses(request):
    if not is_student(request.user):
        return redirect("courses:list")
    enrollments = (
        Enrollment.objects.filter(student=request.user)
        .select_related("course", "course__teacher", "course__category")
        .order_by("-enrolled_at")
    )
    progress = {
        item.course_id: item
        for item in CourseProgress.objects.filter(student=request.user)
    }
    return render(
        request,
        "courses/my_courses.html",
        {"enrollments": enrollments, "progress": progress},
    )


class CourseFormMixin(RoleRequiredMixin):
    allowed_roles = ("teacher", "admin")
    model = Course

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_queryset(self):
        queryset = Course.objects.all()
        if self.request.user.is_admin_role:
            return queryset
        return queryset.filter(teacher=self.request.user)


class CourseCreateView(CourseFormMixin, CreateView):
    form_class = CourseForm
    template_name = "courses/course_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Course created successfully.")
        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.Action.CREATE,
            model_name="Course",
            object_id=self.object.pk,
            description=f"Created course {self.object.code}",
        )
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class CourseUpdateView(CourseFormMixin, UpdateView):
    form_class = CourseForm
    template_name = "courses/course_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Course updated successfully.")
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class CourseDeleteView(CourseFormMixin, DeleteView):
    template_name = "confirm_delete.html"
    success_url = "/courses/"

    def form_valid(self, form):
        messages.success(self.request, "Course deleted.")
        return super().form_valid(form)


@role_required("teacher", "admin")
def course_students(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if not can_manage_course(request.user, course):
        raise PermissionDenied
    enrollments = (
        course.enrollments.select_related("student", "student__student_profile")
        .order_by("student__first_name", "student__last_name")
    )
    progress = {
        item.student_id: item
        for item in CourseProgress.objects.filter(course=course)
    }
    return render(
        request,
        "courses/course_students.html",
        {"course": course, "enrollments": enrollments, "progress": progress},
    )
