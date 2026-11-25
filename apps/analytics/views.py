import json
from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.shortcuts import render

from apps.accounts.models import User
from apps.accounts.permissions import is_admin, is_teacher, role_required
from apps.assessments.models import ExamAttempt, Grade, QuizAttempt, Submission
from apps.courses.models import Course, Enrollment
from apps.learning.models import LearningProgress

from .models import ActivityLog


@role_required("teacher", "admin")
def reports(request):
    user = request.user
    courses = Course.objects.select_related("teacher", "category").annotate(
        enrolled=Count("enrollments", distinct=True),
        lesson_total=Count("lessons", distinct=True),
    )

    enrollments = Enrollment.objects.all()
    grades = Grade.objects.select_related("course", "student")
    submissions = Submission.objects.all()
    quiz_attempts = QuizAttempt.objects.filter(
        status__in=[QuizAttempt.Status.GRADED, QuizAttempt.Status.SUBMITTED],
        max_score__gt=0,
    )
    exam_attempts = ExamAttempt.objects.filter(
        status__in=[ExamAttempt.Status.GRADED, ExamAttempt.Status.SUBMITTED],
        max_score__gt=0,
    )

    if is_teacher(user) and not is_admin(user):
        courses = courses.filter(teacher=user)
        enrollments = enrollments.filter(course__teacher=user)
        grades = grades.filter(course__teacher=user)
        submissions = submissions.filter(assignment__course__teacher=user)
        quiz_attempts = quiz_attempts.filter(quiz__course__teacher=user)
        exam_attempts = exam_attempts.filter(exam__course__teacher=user)

    labels = [course.code for course in courses]
    enrollment_data = [course.enrolled for course in courses]

    grade_buckets = Counter()
    for grade in grades:
        percentage = float(grade.percentage)
        if percentage >= 90:
            grade_buckets["90-100"] += 1
        elif percentage >= 80:
            grade_buckets["80-89"] += 1
        elif percentage >= 70:
            grade_buckets["70-79"] += 1
        elif percentage >= 60:
            grade_buckets["60-69"] += 1
        else:
            grade_buckets["Below 60"] += 1

    quiz_scores = [
        round(float(attempt.score / attempt.max_score * 100), 1)
        for attempt in quiz_attempts
    ]
    exam_scores = [
        round(float(attempt.score / attempt.max_score * 100), 1)
        for attempt in exam_attempts
    ]

    context = {
        "courses": courses,
        "total_students": User.objects.filter(role=User.Role.STUDENT).count()
        if is_admin(user)
        else enrollments.values("student").distinct().count(),
        "total_enrollments": enrollments.count(),
        "total_submissions": submissions.count(),
        "graded_submissions": submissions.filter(
            status=Submission.Status.GRADED
        ).count(),
        "average_grade": round(
            sum(float(g.percentage) for g in grades) / len(grades), 1
        )
        if grades
        else None,
        "quiz_average": round(sum(quiz_scores) / len(quiz_scores), 1)
        if quiz_scores
        else None,
        "exam_average": round(sum(exam_scores) / len(exam_scores), 1)
        if exam_scores
        else None,
        "completed_lessons": LearningProgress.objects.filter(
            is_completed=True,
            lesson__course__in=courses,
        ).count(),
        "chart_labels": json.dumps(labels),
        "chart_enrollments": json.dumps(enrollment_data),
        "grade_labels": json.dumps(list(grade_buckets.keys())),
        "grade_values": json.dumps(list(grade_buckets.values())),
        "is_admin_view": is_admin(user),
    }
    return render(request, "analytics/reports.html", context)


@login_required
def activity_log(request):
    if not is_admin(request.user):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    logs = ActivityLog.objects.select_related("user")[:200]
    return render(request, "analytics/activity_log.html", {"logs": logs})
