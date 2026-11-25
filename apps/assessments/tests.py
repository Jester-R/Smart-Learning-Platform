from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course

from .models import (
    Assignment,
    Choice,
    Exam,
    ExamQuestion,
    Grade,
    Question,
    Quiz,
    QuizAttempt,
    Submission,
)


class AssessmentModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Teacher",
            last_name="One",
        )
        cls.student = User.objects.create_user(
            email="student@example.com",
            password="StrongPass123!",
            first_name="Student",
            last_name="One",
        )
        cls.course = Course.objects.create(
            code="CS101",
            title="Intro to Programming",
            teacher=cls.teacher,
            description="Programming fundamentals.",
        )
        cls.quiz = Quiz.objects.create(
            course=cls.course,
            title="Variables Quiz",
            created_by=cls.teacher,
            time_limit_minutes=15,
            is_published=True,
        )
        cls.question = Question.objects.create(
            quiz=cls.quiz,
            text="What is a variable?",
            points=Decimal("5"),
            order=1,
        )
        Choice.objects.create(question=cls.question, text="A storage location", is_correct=True, order=1)
        Choice.objects.create(question=cls.question, text="A loop", is_correct=False, order=2)

    def test_quiz_total_points(self):
        self.assertEqual(self.quiz.total_points(), Decimal("5"))

    def test_attempt_numbers_are_unique_per_student(self):
        QuizAttempt.objects.create(
            quiz=self.quiz, student=self.student, attempt_number=1
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                QuizAttempt.objects.create(
                    quiz=self.quiz, student=self.student, attempt_number=1
                )

    def test_attempt_expiry_uses_time_limit(self):
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz, student=self.student, attempt_number=1
        )
        self.assertFalse(attempt.is_expired)
        QuizAttempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - timedelta(minutes=20)
        )
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_expired)

    def test_submission_score_cannot_exceed_max_points(self):
        assignment = Assignment.objects.create(
            course=self.course,
            title="Exercise 1",
            description="Complete the exercise.",
            max_points=Decimal("10"),
            created_by=self.teacher,
        )
        submission = Submission(
            assignment=assignment, student=self.student, score=Decimal("11")
        )
        with self.assertRaises(ValidationError):
            submission.full_clean()

    def test_grade_percentage(self):
        grade = Grade(
            student=self.student,
            course=self.course,
            component=Grade.Component.QUIZ,
            title="Quiz 1",
            score=Decimal("8"),
            max_score=Decimal("10"),
            graded_by=self.teacher,
        )
        self.assertEqual(grade.percentage, Decimal("80"))

    def test_exam_total_points(self):
        exam = Exam.objects.create(
            course=self.course,
            title="Midterm",
            created_by=self.teacher,
            is_published=True,
        )
        ExamQuestion.objects.create(
            exam=exam, text="Explain recursion.", points=Decimal("20"), order=1
        )
        self.assertEqual(exam.total_points(), Decimal("20"))
