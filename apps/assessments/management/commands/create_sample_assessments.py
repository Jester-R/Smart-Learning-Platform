from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.assessments.models import (
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
from apps.courses.models import Course


QUIZ_EXAMPLES = [
    ("HTML", "Which tag creates a hyperlink?", "<a>"),
    ("CSS", "Which property changes text color?", "color"),
    ("JavaScript", "Which keyword declares a constant?", "const"),
    ("Web basics", "What does URL stand for?", "Uniform Resource Locator"),
    ("Accessibility", "What does HTML alt text describe?", "An image"),
]

EXAM_EXAMPLES = [
    ("HTML", "Which element contains the page's main visible content?", "<body>"),
    ("CSS", "Which layout system uses rows and columns?", "Grid"),
    ("JavaScript", "Which method converts JSON text into an object?", "JSON.parse"),
    ("Web basics", "Which protocol secures a website connection?", "HTTPS"),
    ("Accessibility", "Which attribute names a form control's label?", "for"),
]


class Command(BaseCommand):
    help = "Create five related example records for each assignment and assessment admin list."

    def handle(self, *args, **options):
        course = Course.objects.filter(status=Course.Status.PUBLISHED).first()
        course = course or Course.objects.first()
        student = User.objects.filter(role=User.Role.STUDENT, is_active=True).first()
        if course is None:
            raise CommandError("Create a course before seeding sample assessments.")
        if student is None:
            raise CommandError("Create an active student account before seeding sample assessments.")

        teacher = course.teacher
        now = timezone.now()
        with transaction.atomic():
            for index in range(1, 6):
                self._create_assignment(index, course, student, teacher, now)
                self._create_quiz(index, course, student, teacher, now)
                self._create_exam(index, course, student, teacher, now)

        self.stdout.write(
            self.style.SUCCESS(
                "Created or refreshed five examples for assignments, submissions, grades, "
                "quizzes, questions, quiz attempts and answers, exams, exam questions, "
                "exam attempts and answers."
            )
        )

    def _create_assignment(self, index, course, student, teacher, now):
        topics = ("HTML profile page", "CSS course card", "JavaScript form check", "Responsive layout", "Accessible navigation")
        title = f"Example Assignment {index}: {topics[index - 1]}"
        assignment, _ = Assignment.objects.update_or_create(
            course=course,
            title=title,
            defaults={
                "description": f"Example assignment about {topics[index - 1].lower()}.",
                "instructions": "Submit a short explanation of your approach and the completed work.",
                "due_at": now + timedelta(days=index * 7),
                "max_points": Decimal("100.00"),
                "allow_late_submission": index % 2 == 0,
                "is_published": True,
                "created_by": teacher,
            },
        )
        score = Decimal(80 + index)
        submission, _ = Submission.objects.update_or_create(
            assignment=assignment,
            student=student,
            defaults={
                "text_response": f"Example response for {topics[index - 1]}.",
                "status": Submission.Status.GRADED,
                "score": score,
                "feedback": "Example feedback: clear work; review the course rubric for details.",
                "graded_by": teacher,
                "graded_at": now,
            },
        )
        Grade.objects.update_or_create(
            student=student,
            course=course,
            component=Grade.Component.ASSIGNMENT,
            title=title,
            defaults={
                "score": score,
                "max_score": Decimal("100.00"),
                "weight": Decimal("20.00"),
                "feedback": "Example grade linked to a sample assignment.",
                "graded_by": teacher,
                "graded_at": now,
            },
        )

    def _create_quiz(self, index, course, student, teacher, now):
        topic, prompt, answer = QUIZ_EXAMPLES[index - 1]
        title = f"Example Quiz {index}: {topic} Basics"
        quiz, _ = Quiz.objects.update_or_create(
            course=course,
            title=title,
            defaults={
                "description": f"Sample multiple-choice quiz covering {topic}.",
                "instructions": "Choose the best answer. This is example assessment data.",
                "time_limit_minutes": 15,
                "passing_score": 70,
                "max_attempts": 2,
                "is_published": True,
                "created_by": teacher,
                "show_results": "immediately",
            },
        )
        question, _ = Question.objects.update_or_create(
            quiz=quiz,
            order=1,
            defaults={
                "question_type": "multiple_choice",
                "text": prompt,
                "correct_answer": answer,
                "explanation": f"{answer} is the correct answer for this {topic} example.",
                "points": Decimal("10.00"),
            },
        )
        correct_choice = self._choices(Choice, question, answer, ("<div>", "<a>", "<img>"))
        attempt, _ = QuizAttempt.objects.update_or_create(
            quiz=quiz,
            student=student,
            attempt_number=1,
            defaults={
                "submitted_at": now,
                "score": Decimal("10.00"),
                "max_score": Decimal("10.00"),
                "status": QuizAttempt.Status.GRADED,
            },
        )
        QuizAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                "selected_choice": correct_choice,
                "text_answer": answer,
                "is_correct": True,
                "points_awarded": Decimal("10.00"),
            },
        )

    def _create_exam(self, index, course, student, teacher, now):
        topic, prompt, answer = EXAM_EXAMPLES[index - 1]
        title = f"Example Midterm {index}: {topic}"
        exam, _ = Exam.objects.update_or_create(
            course=course,
            title=title,
            defaults={
                "description": f"Sample midterm examination covering {topic}.",
                "instructions": "Answer each question. This is example assessment data.",
                "time_limit_minutes": 30,
                "passing_score": 70,
                "max_attempts": 1,
                "is_published": True,
                "created_by": teacher,
                "show_results": "manual",
            },
        )
        question, _ = ExamQuestion.objects.update_or_create(
            exam=exam,
            order=1,
            defaults={
                "question_type": "multiple_choice",
                "text": prompt,
                "correct_answer": answer,
                "explanation": f"{answer} is the correct answer for this {topic} example.",
                "points": Decimal("20.00"),
            },
        )
        correct_choice = self._choices(ExamChoice, question, answer, ("HTTP", "HTTPS", "FTP"))
        attempt, _ = ExamAttempt.objects.update_or_create(
            exam=exam,
            student=student,
            attempt_number=1,
            defaults={
                "submitted_at": now,
                "score": Decimal("20.00"),
                "max_score": Decimal("20.00"),
                "status": ExamAttempt.Status.GRADED,
            },
        )
        ExamAnswer.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                "selected_choice": correct_choice,
                "text_answer": answer,
                "is_correct": True,
                "points_awarded": Decimal("20.00"),
            },
        )

    @staticmethod
    def _choices(model, question, answer, distractors):
        choices = [answer, *[item for item in distractors if item != answer][:2]]
        correct_choice = None
        for order, text in enumerate(choices, start=1):
            choice, _ = model.objects.update_or_create(
                question=question,
                order=order,
                defaults={"text": text, "is_correct": text == answer},
            )
            if text == answer:
                correct_choice = choice
        return correct_choice
