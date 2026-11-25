from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.permissions import (
    can_access_course,
    can_manage_course,
    is_admin,
    is_student,
    role_required,
)
from apps.analytics.models import ActivityLog, GradeAuditLog
from apps.courses.models import Course, Enrollment
from apps.notifications.services import notify

from .forms import (
    AssignmentForm,
    ExamForm,
    GradeSubmissionForm,
    QuestionForm,
    QuizForm,
    SubmissionForm,
)
from .models import (
    Assignment,
    Choice,
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamChoice,
    ExamQuestion,
    Grade,
    Question,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    Submission,
)

QUESTION_TYPES_AUTO = {"multiple_choice", "true_false", "short_answer"}


def _course(slug):
    return get_object_or_404(Course, slug=slug)


def _ensure_manager(request, course):
    if not can_manage_course(request.user, course):
        raise PermissionDenied
    return course


def _ensure_access(request, course):
    if not can_access_course(request.user, course):
        raise PermissionDenied("You must be enrolled in this course.")
    return course


def _ensure_enrolled(request, course):
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        raise PermissionDenied("You must be enrolled in this course.")


def _normalized(value):
    return " ".join((value or "").strip().lower().split())


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------
@role_required("teacher", "admin")
def assignment_create(request, slug):
    course = _ensure_manager(request, _course(slug))
    form = AssignmentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.course = course
        assignment.created_by = request.user
        assignment.save()
        messages.success(request, "Assignment created.")
        return redirect("assessments:assignment", slug=course.slug, pk=assignment.pk)
    return render(
        request,
        "assessments/assignment_form.html",
        {"form": form, "course": course, "title": "New assignment"},
    )


@role_required("teacher", "admin")
def assignment_update(request, slug, pk):
    course = _ensure_manager(request, _course(slug))
    assignment = get_object_or_404(Assignment, pk=pk, course=course)
    form = AssignmentForm(
        request.POST or None, request.FILES or None, instance=assignment
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Assignment updated.")
        return redirect("assessments:assignment", slug=course.slug, pk=assignment.pk)
    return render(
        request,
        "assessments/assignment_form.html",
        {"form": form, "course": course, "assignment": assignment, "title": "Edit assignment"},
    )


@role_required("teacher", "admin")
def assignment_delete(request, slug, pk):
    course = _ensure_manager(request, _course(slug))
    assignment = get_object_or_404(Assignment, pk=pk, course=course)
    if request.method == "POST":
        assignment.delete()
        messages.success(request, "Assignment deleted.")
        return redirect(course.get_absolute_url())
    return render(
        request,
        "confirm_delete.html",
        {"object": assignment, "cancel_url": course.get_absolute_url()},
    )


@login_required
def assignment_detail(request, slug, pk):
    course = _course(slug)
    assignment = get_object_or_404(Assignment, pk=pk, course=course)
    is_manager = can_manage_course(request.user, course)
    if not is_manager:
        _ensure_access(request, course)
        if not assignment.is_published:
            raise PermissionDenied("This assignment is not published.")

    submission = None
    if is_student(request.user):
        submission = Submission.objects.filter(
            assignment=assignment, student=request.user
        ).first()

    return render(
        request,
        "assessments/assignment_detail.html",
        {
            "course": course,
            "assignment": assignment,
            "submission": submission,
            "is_manager": is_manager,
            "can_submit": is_student(request.user)
            and (not assignment.is_past_due or assignment.allow_late_submission),
        },
    )


@role_required("student")
def assignment_submit(request, slug, pk):
    course = _course(slug)
    _ensure_enrolled(request, course)
    assignment = get_object_or_404(Assignment, pk=pk, course=course)
    if not assignment.is_published:
        raise PermissionDenied("This assignment is not published.")
    if assignment.is_past_due and not assignment.allow_late_submission:
        messages.error(request, "The deadline has passed for this assignment.")
        return redirect("assessments:assignment", slug=course.slug, pk=assignment.pk)

    submission = Submission.objects.filter(
        assignment=assignment, student=request.user
    ).first()
    form = SubmissionForm(
        request.POST or None, request.FILES or None, instance=submission
    )
    if request.method == "POST" and form.is_valid():
        new_submission = form.save(commit=False)
        new_submission.assignment = assignment
        new_submission.student = request.user
        new_submission.is_late = assignment.is_past_due
        if submission is not None:
            new_submission.resubmission_count = submission.resubmission_count + 1
            new_submission.status = Submission.Status.SUBMITTED
            new_submission.score = None
            new_submission.feedback = ""
            new_submission.graded_by = None
            new_submission.graded_at = None
        new_submission.save()
        notify(
            course.teacher,
            "New assignment submission",
            f"{request.user.full_name} submitted {assignment.title}.",
            kind="assignment",
            link=reverse("assessments:assignment_submissions", args=[course.slug, assignment.pk]),
        )
        messages.success(request, "Assignment submitted.")
        return redirect("assessments:assignment", slug=course.slug, pk=assignment.pk)
    return render(
        request,
        "assessments/submission_form.html",
        {"form": form, "course": course, "assignment": assignment},
    )


@role_required("teacher", "admin")
def assignment_submissions(request, slug, pk):
    course = _ensure_manager(request, _course(slug))
    assignment = get_object_or_404(Assignment, pk=pk, course=course)
    submissions = assignment.submissions.select_related("student").order_by(
        "-submitted_at"
    )
    return render(
        request,
        "assessments/submissions.html",
        {"course": course, "assignment": assignment, "submissions": submissions},
    )


@role_required("teacher", "admin")
def submission_grade(request, pk):
    submission = get_object_or_404(
        Submission.objects.select_related(
            "assignment", "assignment__course", "student"
        ),
        pk=pk,
    )
    course = submission.assignment.course
    _ensure_manager(request, course)
    if not request.user.has_permission("grade.record"):
        raise PermissionDenied("You do not have permission to record official grades.")
    initial = {
        "score": submission.score,
        "feedback": submission.feedback,
        "status": submission.status
        if submission.status != Submission.Status.SUBMITTED
        else Submission.Status.GRADED,
    }
    form = GradeSubmissionForm(
        request.POST or None,
        max_points=submission.assignment.max_points,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        old_score = submission.score
        old_feedback = submission.feedback
        submission.score = form.cleaned_data["score"]
        submission.feedback = form.cleaned_data["feedback"]
        submission.status = form.cleaned_data["status"]
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        submission.save()

        grade = Grade.objects.filter(
            student=submission.student,
            course=course,
            component=Grade.Component.ASSIGNMENT,
            title=submission.assignment.title,
        ).first()
        reason = form.cleaned_data.get("reason", "").strip()
        if grade is None:
            grade = Grade.objects.create(
                student=submission.student,
                course=course,
                component=Grade.Component.ASSIGNMENT,
                title=submission.assignment.title,
                score=submission.score,
                max_score=submission.assignment.max_points,
                feedback=submission.feedback,
                graded_by=request.user,
            )
            GradeAuditLog.objects.create(
                grade=grade,
                changed_by=request.user,
                old_score=None,
                new_score=submission.score,
                old_feedback="",
                new_feedback=submission.feedback,
                reason=reason or "Initial official grade entry",
            )
        else:
            GradeAuditLog.objects.create(
                grade=grade,
                changed_by=request.user,
                old_score=grade.score,
                new_score=submission.score,
                old_feedback=grade.feedback,
                new_feedback=submission.feedback,
                reason=reason or "Assignment regraded",
            )
            grade.score = submission.score
            grade.max_score = submission.assignment.max_points
            grade.feedback = submission.feedback
            grade.graded_by = request.user
            grade.graded_at = timezone.now()
            grade.save()

        notify(
            submission.student,
            "Assignment graded",
            f"{submission.assignment.title}: {submission.score}/{submission.assignment.max_points}.",
            kind="grade",
            link=reverse("assessments:assignment", args=[course.slug, submission.assignment.pk]),
        )
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.Action.GRADE,
            model_name="Submission",
            object_id=submission.pk,
            description=f"Graded {submission.assignment.title} for {submission.student.full_name}",
        )
        messages.success(request, "Submission graded.")
        return redirect(
            "assessments:assignment_submissions",
            slug=course.slug,
            pk=submission.assignment.pk,
        )
    return render(
        request,
        "assessments/submission_grade.html",
        {"form": form, "submission": submission, "course": course},
    )


# ---------------------------------------------------------------------------
# Quiz helpers
# ---------------------------------------------------------------------------
def _grade_answer(answer, question, selected_choice, text):
    answer.selected_choice = selected_choice
    answer.text_answer = text or ""
    if question.question_type in ("multiple_choice", "true_false"):
        correct = question.choices.filter(is_correct=True).first()
        answer.is_correct = bool(
            selected_choice and correct and selected_choice.pk == correct.pk
        )
        answer.points_awarded = question.points if answer.is_correct else Decimal("0")
    elif question.question_type == "short_answer":
        answer.is_correct = bool(
            _normalized(question.correct_answer)
            and _normalized(question.correct_answer) == _normalized(text)
        )
        answer.points_awarded = question.points if answer.is_correct else Decimal("0")
    else:
        answer.is_correct = None
        answer.points_awarded = Decimal("0")
    answer.save()


def _finalize_quiz(attempt, post_data=None):
    questions = list(attempt.quiz.questions.prefetch_related("choices"))
    with transaction.atomic():
        for question in questions:
            answer, _ = QuizAnswer.objects.get_or_create(
                attempt=attempt, question=question
            )
            if post_data is not None:
                choice = None
                choice_id = post_data.get(f"question_{question.pk}")
                if choice_id:
                    choice = question.choices.filter(pk=choice_id).first()
                text = post_data.get(f"text_{question.pk}", "")
            else:
                choice = answer.selected_choice
                text = answer.text_answer
            _grade_answer(answer, question, choice, text)

        has_subjective = any(q.question_type == "essay" for q in questions)
        totals = QuizAnswer.objects.filter(attempt=attempt).aggregate(
            total=Sum("points_awarded")
        )
        attempt.score = totals["total"] or Decimal("0")
        attempt.max_score = sum((q.points for q in questions), Decimal("0"))
        attempt.submitted_at = timezone.now()
        attempt.status = (
            QuizAttempt.Status.SUBMITTED if has_subjective else QuizAttempt.Status.GRADED
        )
        attempt.save()
    return attempt


def _finalize_exam(attempt, post_data=None):
    questions = list(attempt.exam.questions.prefetch_related("choices"))
    with transaction.atomic():
        for question in questions:
            answer, _ = ExamAnswer.objects.get_or_create(
                attempt=attempt, question=question
            )
            if post_data is not None:
                choice = None
                choice_id = post_data.get(f"question_{question.pk}")
                if choice_id:
                    choice = question.choices.filter(pk=choice_id).first()
                text = post_data.get(f"text_{question.pk}", "")
            else:
                choice = answer.selected_choice
                text = answer.text_answer
            _grade_answer(answer, question, choice, text)

        has_subjective = any(q.question_type == "essay" for q in questions)
        totals = ExamAnswer.objects.filter(attempt=attempt).aggregate(
            total=Sum("points_awarded")
        )
        attempt.score = totals["total"] or Decimal("0")
        attempt.max_score = sum((q.points for q in questions), Decimal("0"))
        attempt.submitted_at = timezone.now()
        attempt.status = (
            ExamAttempt.Status.SUBMITTED if has_subjective else ExamAttempt.Status.GRADED
        )
        attempt.save()
    return attempt


def _results_visible(assessment, attempt, user, course):
    if can_manage_course(user, course):
        return True
    if attempt.status not in (QuizAttempt.Status.SUBMITTED, QuizAttempt.Status.GRADED):
        return False
    mode = assessment.show_results
    if mode == "immediately":
        return True
    if mode == "after_close":
        return bool(assessment.closes_at and timezone.now() >= assessment.closes_at)
    if mode == "manual":
        return attempt.status in (QuizAttempt.Status.GRADED,)
    return False


# ---------------------------------------------------------------------------
# Quizzes
# ---------------------------------------------------------------------------
@role_required("teacher", "admin")
def quiz_create(request, slug):
    course = _ensure_manager(request, _course(slug))
    form = QuizForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        quiz = form.save(commit=False)
        quiz.course = course
        quiz.created_by = request.user
        quiz.save()
        messages.success(request, "Quiz created. Add questions next.")
        return redirect("assessments:quiz_questions", pk=quiz.pk)
    return render(
        request,
        "assessments/assessment_form.html",
        {"form": form, "course": course, "title": "New quiz", "kind": "quiz"},
    )


@role_required("teacher", "admin")
def quiz_update(request, slug, pk):
    course = _ensure_manager(request, _course(slug))
    quiz = get_object_or_404(Quiz, pk=pk, course=course)
    form = QuizForm(request.POST or None, instance=quiz)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Quiz updated.")
        return redirect("assessments:quiz_detail", pk=quiz.pk)
    return render(
        request,
        "assessments/assessment_form.html",
        {"form": form, "course": course, "title": "Edit quiz", "kind": "quiz"},
    )


@role_required("teacher", "admin")
def quiz_delete(request, slug, pk):
    course = _ensure_manager(request, _course(slug))
    quiz = get_object_or_404(Quiz, pk=pk, course=course)
    if request.method == "POST":
        quiz.delete()
        messages.success(request, "Quiz deleted.")
        return redirect(course.get_absolute_url())
    return render(
        request,
        "confirm_delete.html",
        {"object": quiz, "cancel_url": course.get_absolute_url()},
    )


@login_required
def quiz_detail(request, pk):
    quiz = get_object_or_404(Quiz.objects.select_related("course"), pk=pk)
    course = quiz.course
    is_manager = can_manage_course(request.user, course)
    if not is_manager:
        _ensure_access(request, course)
        if not quiz.is_published:
            raise PermissionDenied("This quiz is not published.")

    attempts = []
    remaining_attempts = 0
    if is_student(request.user):
        attempts = quiz.attempts.filter(student=request.user).order_by("-attempt_number")
        remaining_attempts = max(quiz.max_attempts - attempts.count(), 0)

    return render(
        request,
        "assessments/quiz_detail.html",
        {
            "quiz": quiz,
            "course": course,
            "is_manager": is_manager,
            "attempts": attempts,
            "remaining_attempts": remaining_attempts,
            "question_count": quiz.questions.count(),
            "total_points": quiz.total_points(),
        },
    )


@role_required("student")
def quiz_start(request, pk):
    quiz = get_object_or_404(Quiz.objects.select_related("course"), pk=pk)
    _ensure_enrolled(request, quiz.course)
    if request.method != "POST":
        return redirect("assessments:quiz_detail", pk=quiz.pk)
    if not quiz.is_available:
        messages.error(request, "This quiz is not currently available.")
        return redirect("assessments:quiz_detail", pk=quiz.pk)
    if not quiz.questions.exists():
        messages.error(request, "This quiz has no questions yet.")
        return redirect("assessments:quiz_detail", pk=quiz.pk)

    in_progress = quiz.attempts.filter(
        student=request.user, status=QuizAttempt.Status.IN_PROGRESS
    ).first()
    if in_progress:
        return redirect("assessments:quiz_attempt", pk=in_progress.pk)

    used_attempts = quiz.attempts.filter(student=request.user).count()
    if used_attempts >= quiz.max_attempts:
        messages.error(request, "You have used all attempts for this quiz.")
        return redirect("assessments:quiz_detail", pk=quiz.pk)

    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        student=request.user,
        attempt_number=used_attempts + 1,
        max_score=quiz.total_points(),
    )
    ActivityLog.objects.create(
        user=request.user,
        action=ActivityLog.Action.SUBMIT,
        model_name="QuizAttempt",
        object_id=attempt.pk,
        description=f"Started quiz {quiz.title}",
    )
    return redirect("assessments:quiz_attempt", pk=attempt.pk)


@role_required("student")
def quiz_attempt(request, pk):
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "quiz__course"), pk=pk
    )
    if attempt.student_id != request.user.id:
        raise PermissionDenied
    if attempt.status != QuizAttempt.Status.IN_PROGRESS:
        return redirect("assessments:quiz_result", pk=attempt.pk)

    if attempt.is_expired:
        _finalize_quiz(attempt)
        messages.warning(request, "Time expired. Your saved answers were submitted.")
        return redirect("assessments:quiz_result", pk=attempt.pk)

    if request.method == "POST":
        _finalize_quiz(attempt, request.POST)
        messages.success(request, "Quiz submitted.")
        return redirect("assessments:quiz_result", pk=attempt.pk)

    questions = list(
        attempt.quiz.questions.prefetch_related("choices").order_by("order")
    )
    if attempt.quiz.shuffle_questions:
        import random

        random.shuffle(questions)

    existing = {
        answer.question_id: answer
        for answer in QuizAnswer.objects.filter(attempt=attempt)
    }
    elapsed = int((timezone.now() - attempt.started_at).total_seconds())
    remaining = max(attempt.quiz.time_limit_minutes * 60 - elapsed, 0)

    return render(
        request,
        "assessments/quiz_attempt.html",
        {
            "attempt": attempt,
            "quiz": attempt.quiz,
            "course": attempt.quiz.course,
            "questions": questions,
            "existing": existing,
            "remaining_seconds": remaining,
        },
    )


@login_required
def quiz_result(request, pk):
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "quiz__course", "student"), pk=pk
    )
    course = attempt.quiz.course
    is_manager = can_manage_course(request.user, course)
    if not is_manager and attempt.student_id != request.user.id:
        raise PermissionDenied
    visible = _results_visible(attempt.quiz, attempt, request.user, course)
    answers = attempt.answers.select_related("question", "selected_choice")
    return render(
        request,
        "assessments/quiz_result.html",
        {
            "attempt": attempt,
            "quiz": attempt.quiz,
            "course": course,
            "answers": answers,
            "visible": visible,
            "is_manager": is_manager,
        },
    )


@role_required("teacher", "admin")
def quiz_questions(request, pk):
    quiz = get_object_or_404(Quiz.objects.select_related("course"), pk=pk)
    _ensure_manager(request, quiz.course)
    return render(
        request,
        "assessments/quiz_questions.html",
        {"quiz": quiz, "course": quiz.course, "questions": quiz.questions.prefetch_related("choices")},
    )


@role_required("teacher", "admin")
def question_create(request, pk):
    quiz = get_object_or_404(Quiz.objects.select_related("course"), pk=pk)
    _ensure_manager(request, quiz.course)
    next_order = quiz.questions.count() + 1
    form = QuestionForm(
        request.POST or None, initial={"order": next_order}
    )
    if request.method == "POST" and form.is_valid():
        form.save(quiz, Question, Choice)
        messages.success(request, "Question added.")
        return redirect("assessments:quiz_questions", pk=quiz.pk)
    return render(
        request,
        "assessments/question_form.html",
        {"form": form, "quiz": quiz, "course": quiz.course, "title": "Add quiz question"},
    )


@role_required("teacher", "admin")
def question_update(request, pk):
    question = get_object_or_404(
        Question.objects.select_related("quiz", "quiz__course"), pk=pk
    )
    _ensure_manager(request, question.quiz.course)
    form = QuestionForm(request.POST or None, instance=question)
    if request.method == "POST" and form.is_valid():
        form.save(question.quiz, Question, Choice)
        messages.success(request, "Question updated.")
        return redirect("assessments:quiz_questions", pk=question.quiz.pk)
    return render(
        request,
        "assessments/question_form.html",
        {
            "form": form,
            "quiz": question.quiz,
            "course": question.quiz.course,
            "title": "Edit quiz question",
        },
    )


@role_required("teacher", "admin")
def question_delete(request, pk):
    question = get_object_or_404(
        Question.objects.select_related("quiz", "quiz__course"), pk=pk
    )
    _ensure_manager(request, question.quiz.course)
    quiz = question.quiz
    if request.method == "POST":
        question.delete()
        messages.success(request, "Question deleted.")
        return redirect("assessments:quiz_questions", pk=quiz.pk)
    return render(
        request,
        "confirm_delete.html",
        {"object": question, "cancel_url": reverse("assessments:quiz_questions", args=[quiz.pk])},
    )


@role_required("teacher", "admin")
def quiz_grade_attempt(request, pk):
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related("quiz", "quiz__course", "student"), pk=pk
    )
    _ensure_manager(request, attempt.quiz.course)
    answers = attempt.answers.select_related("question", "selected_choice")
    if request.method == "POST":
        for answer in answers:
            if answer.question.question_type != "essay":
                continue
            raw = request.POST.get(f"points_{answer.pk}")
            try:
                points = Decimal(raw) if raw not in (None, "") else Decimal("0")
            except InvalidOperation:
                points = Decimal("0")
            points = max(Decimal("0"), min(points, answer.question.points))
            answer.points_awarded = points
            answer.is_correct = points >= answer.question.points
            answer.save()
        totals = attempt.answers.aggregate(total=Sum("points_awarded"))
        attempt.score = totals["total"] or Decimal("0")
        attempt.status = QuizAttempt.Status.GRADED
        attempt.save(update_fields=["score", "status"])
        notify(
            attempt.student,
            "Quiz graded",
            f"{attempt.quiz.title}: {attempt.score}/{attempt.max_score}.",
            kind="grade",
            link=reverse("assessments:quiz_result", args=[attempt.pk]),
        )
        messages.success(request, "Quiz attempt graded.")
        return redirect("assessments:quiz_result", pk=attempt.pk)
    return render(
        request,
        "assessments/attempt_grade.html",
        {"attempt": attempt, "answers": answers, "kind": "quiz", "course": attempt.quiz.course},
    )


# ---------------------------------------------------------------------------
# Exams
# ---------------------------------------------------------------------------
@role_required("teacher", "admin")
def exam_create(request, slug):
    course = _ensure_manager(request, _course(slug))
    form = ExamForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        exam = form.save(commit=False)
        exam.course = course
        exam.created_by = request.user
        exam.save()
        messages.success(request, "Midterm examination created. Add questions next.")
        return redirect("assessments:exam_questions", pk=exam.pk)
    return render(
        request,
        "assessments/assessment_form.html",
        {"form": form, "course": course, "title": "New midterm exam", "kind": "exam"},
    )


@role_required("teacher", "admin")
def exam_update(request, slug, pk):
    course = _ensure_manager(request, _course(slug))
    exam = get_object_or_404(Exam, pk=pk, course=course)
    form = ExamForm(request.POST or None, instance=exam)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Examination updated.")
        return redirect("assessments:exam_detail", pk=exam.pk)
    return render(
        request,
        "assessments/assessment_form.html",
        {"form": form, "course": course, "title": "Edit midterm exam", "kind": "exam"},
    )


@role_required("teacher", "admin")
def exam_delete(request, slug, pk):
    course = _ensure_manager(request, _course(slug))
    exam = get_object_or_404(Exam, pk=pk, course=course)
    if request.method == "POST":
        exam.delete()
        messages.success(request, "Examination deleted.")
        return redirect(course.get_absolute_url())
    return render(
        request,
        "confirm_delete.html",
        {"object": exam, "cancel_url": course.get_absolute_url()},
    )


@login_required
def exam_detail(request, pk):
    exam = get_object_or_404(Exam.objects.select_related("course"), pk=pk)
    course = exam.course
    is_manager = can_manage_course(request.user, course)
    if not is_manager:
        _ensure_access(request, course)
        if not exam.is_published:
            raise PermissionDenied("This examination is not published.")
    attempts = []
    remaining_attempts = 0
    if is_student(request.user):
        attempts = exam.attempts.filter(student=request.user).order_by("-attempt_number")
        remaining_attempts = max(exam.max_attempts - attempts.count(), 0)
    return render(
        request,
        "assessments/exam_detail.html",
        {
            "exam": exam,
            "course": course,
            "is_manager": is_manager,
            "attempts": attempts,
            "remaining_attempts": remaining_attempts,
            "question_count": exam.questions.count(),
            "total_points": exam.total_points(),
        },
    )


@role_required("student")
def exam_start(request, pk):
    exam = get_object_or_404(Exam.objects.select_related("course"), pk=pk)
    _ensure_enrolled(request, exam.course)
    if request.method != "POST":
        return redirect("assessments:exam_detail", pk=exam.pk)
    if not exam.is_available:
        messages.error(request, "This examination is not currently available.")
        return redirect("assessments:exam_detail", pk=exam.pk)
    if not exam.questions.exists():
        messages.error(request, "This examination has no questions yet.")
        return redirect("assessments:exam_detail", pk=exam.pk)
    in_progress = exam.attempts.filter(
        student=request.user, status=ExamAttempt.Status.IN_PROGRESS
    ).first()
    if in_progress:
        return redirect("assessments:exam_attempt", pk=in_progress.pk)
    used = exam.attempts.filter(student=request.user).count()
    if used >= exam.max_attempts:
        messages.error(request, "You have used all attempts for this examination.")
        return redirect("assessments:exam_detail", pk=exam.pk)
    attempt = ExamAttempt.objects.create(
        exam=exam,
        student=request.user,
        attempt_number=used + 1,
        max_score=exam.total_points(),
    )
    return redirect("assessments:exam_attempt", pk=attempt.pk)


@role_required("student")
def exam_attempt(request, pk):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("exam", "exam__course"), pk=pk
    )
    if attempt.student_id != request.user.id:
        raise PermissionDenied
    if attempt.status != ExamAttempt.Status.IN_PROGRESS:
        return redirect("assessments:exam_result", pk=attempt.pk)
    if attempt.is_expired:
        _finalize_exam(attempt)
        messages.warning(request, "Time expired. Your saved answers were submitted.")
        return redirect("assessments:exam_result", pk=attempt.pk)
    if request.method == "POST":
        _finalize_exam(attempt, request.POST)
        messages.success(request, "Examination submitted.")
        return redirect("assessments:exam_result", pk=attempt.pk)
    questions = list(
        attempt.exam.questions.prefetch_related("choices").order_by("order")
    )
    if attempt.exam.shuffle_questions:
        import random

        random.shuffle(questions)
    existing = {
        answer.question_id: answer
        for answer in ExamAnswer.objects.filter(attempt=attempt)
    }
    elapsed = int((timezone.now() - attempt.started_at).total_seconds())
    remaining = max(attempt.exam.time_limit_minutes * 60 - elapsed, 0)
    return render(
        request,
        "assessments/exam_attempt.html",
        {
            "attempt": attempt,
            "exam": attempt.exam,
            "course": attempt.exam.course,
            "questions": questions,
            "existing": existing,
            "remaining_seconds": remaining,
        },
    )


@login_required
def exam_result(request, pk):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("exam", "exam__course", "student"), pk=pk
    )
    course = attempt.exam.course
    is_manager = can_manage_course(request.user, course)
    if not is_manager and attempt.student_id != request.user.id:
        raise PermissionDenied
    visible = _results_visible(attempt.exam, attempt, request.user, course)
    answers = attempt.answers.select_related("question", "selected_choice")
    return render(
        request,
        "assessments/exam_result.html",
        {
            "attempt": attempt,
            "exam": attempt.exam,
            "course": course,
            "answers": answers,
            "visible": visible,
            "is_manager": is_manager,
        },
    )


@role_required("teacher", "admin")
def exam_questions(request, pk):
    exam = get_object_or_404(Exam.objects.select_related("course"), pk=pk)
    _ensure_manager(request, exam.course)
    return render(
        request,
        "assessments/exam_questions.html",
        {"exam": exam, "course": exam.course, "questions": exam.questions.prefetch_related("choices")},
    )


@role_required("teacher", "admin")
def exam_question_create(request, pk):
    exam = get_object_or_404(Exam.objects.select_related("course"), pk=pk)
    _ensure_manager(request, exam.course)
    next_order = exam.questions.count() + 1
    form = QuestionForm(request.POST or None, initial={"order": next_order})
    if request.method == "POST" and form.is_valid():
        form.save(exam, ExamQuestion, ExamChoice)
        messages.success(request, "Question added.")
        return redirect("assessments:exam_questions", pk=exam.pk)
    return render(
        request,
        "assessments/question_form.html",
        {"form": form, "exam": exam, "course": exam.course, "title": "Add exam question"},
    )


@role_required("teacher", "admin")
def exam_question_update(request, pk):
    question = get_object_or_404(
        ExamQuestion.objects.select_related("exam", "exam__course"), pk=pk
    )
    _ensure_manager(request, question.exam.course)
    form = QuestionForm(request.POST or None, instance=question)
    if request.method == "POST" and form.is_valid():
        form.save(question.exam, ExamQuestion, ExamChoice)
        messages.success(request, "Question updated.")
        return redirect("assessments:exam_questions", pk=question.exam.pk)
    return render(
        request,
        "assessments/question_form.html",
        {
            "form": form,
            "exam": question.exam,
            "course": question.exam.course,
            "title": "Edit exam question",
        },
    )


@role_required("teacher", "admin")
def exam_question_delete(request, pk):
    question = get_object_or_404(
        ExamQuestion.objects.select_related("exam", "exam__course"), pk=pk
    )
    _ensure_manager(request, question.exam.course)
    exam = question.exam
    if request.method == "POST":
        question.delete()
        messages.success(request, "Question deleted.")
        return redirect("assessments:exam_questions", pk=exam.pk)
    return render(
        request,
        "confirm_delete.html",
        {"object": question, "cancel_url": reverse("assessments:exam_questions", args=[exam.pk])},
    )


@role_required("teacher", "admin")
def exam_grade_attempt(request, pk):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("exam", "exam__course", "student"), pk=pk
    )
    _ensure_manager(request, attempt.exam.course)
    answers = attempt.answers.select_related("question", "selected_choice")
    if request.method == "POST":
        for answer in answers:
            if answer.question.question_type != "essay":
                continue
            raw = request.POST.get(f"points_{answer.pk}")
            try:
                points = Decimal(raw) if raw not in (None, "") else Decimal("0")
            except InvalidOperation:
                points = Decimal("0")
            points = max(Decimal("0"), min(points, answer.question.points))
            answer.points_awarded = points
            answer.is_correct = points >= answer.question.points
            answer.save()
        totals = attempt.answers.aggregate(total=Sum("points_awarded"))
        attempt.score = totals["total"] or Decimal("0")
        attempt.status = ExamAttempt.Status.GRADED
        attempt.save(update_fields=["score", "status"])
        notify(
            attempt.student,
            "Examination graded",
            f"{attempt.exam.title}: {attempt.score}/{attempt.max_score}.",
            kind="grade",
            link=reverse("assessments:exam_result", args=[attempt.pk]),
        )
        messages.success(request, "Examination attempt graded.")
        return redirect("assessments:exam_result", pk=attempt.pk)
    return render(
        request,
        "assessments/attempt_grade.html",
        {"attempt": attempt, "answers": answers, "kind": "exam", "course": attempt.exam.course},
    )
