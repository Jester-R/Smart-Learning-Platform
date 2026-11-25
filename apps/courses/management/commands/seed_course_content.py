"""Populate courses with lessons, materials, assignments, quizzes, and exams."""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.assessments.models import (
    Assignment,
    Choice,
    Exam,
    ExamChoice,
    ExamQuestion,
    Question,
    Quiz,
)
from apps.courses.models import Course
from apps.learning.models import Lesson, LearningMaterial, extract_youtube_video_id

YOUTUBE_IDS = [
    "rfscVS0vtbw", "W6NZfCO5SIk", "1Rs2ND1ryYc", "qz0aGYrrlhU",
    "PkZNo7MFNFg", "mU6anWqZJcc", "srvUrASNj0s", "yfoY53QXEnI",
    "9No-FiEInLA", "hdI2bqOjy3c", "3PHXvlpOkf4", "f77ZozI0rwg",
    "XqFRJpQkXdQ", "K0HTF-eA2GI", "8jLOx1hD3_o", "G3e-cpL7ofc",
    "lZsc1Czwnio", "c8VJY3FzL2E", "dQw4w9WgXcQ", "6mbwJ2xhgzM",
]

CHAPTERS = ["Getting Started", "Core Concepts", "Hands-On Practice"]

LESSON_TITLES = [
    "Welcome and Course Overview",
    "Setting Up Your Environment",
    "Key Terminology",
    "Core Principles Explained",
    "Working Through Examples",
    "Common Pitfalls to Avoid",
    "Guided Practice",
    "Applied Mini Project",
    "Review and Next Steps",
]

QUESTION_TEMPLATES = [
    (
        "Which of the following best describes the main focus of {subject}?",
        [
            "Foundational theory with practical application",
            "Historical trivia only",
            "Unrelated general knowledge",
            "None of the above",
        ],
    ),
    (
        "What is the recommended first step when studying {subject}?",
        [
            "Skip the basics",
            "Understand the core concepts",
            "Memorize without practice",
            "Avoid the exercises",
        ],
    ),
    (
        "Which activity best reinforces learning in {subject}?",
        [
            "Hands-on practice",
            "Passive reading only",
            "Cramming the night before",
            "Skipping assessments",
        ],
    ),
    (
        "How should you prepare for the {subject} assessment?",
        [
            "Ignore the materials",
            "Study only the night before",
            "Review lessons and complete exercises",
            "Skip the quiz",
        ],
    ),
]


def _build_choices(correct_index, choices):
    return [
        {"text": text, "is_correct": position == correct_index, "order": position + 1}
        for position, text in enumerate(choices)
    ]


class Command(BaseCommand):
    help = (
        "Add lessons, learning materials, assignments, quizzes, and midterm "
        "exams to courses that do not have lessons yet. Safe to run more "
        "than once."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--lessons",
            type=int,
            default=9,
            help="Lessons per course (default: 9).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of courses to populate (0 = all).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        lesson_count = max(1, options["lessons"])
        limit = max(0, options["limit"])

        courses = list(
            Course.objects.filter(lessons__isnull=True)
            .select_related("teacher")
            .order_by("id")
        )
        if limit:
            courses = courses[:limit]

        if not courses:
            self.stdout.write(
                self.style.SUCCESS("Every course already has lessons.")
            )
            return

        admin = User.objects.filter(role=User.Role.ADMIN).first()
        now = timezone.now()
        lessons_created = materials_created = 0
        assignments_created = quizzes_created = exams_created = 0

        for course_index, course in enumerate(courses):
            subject = course.title
            teacher = course.teacher or admin

            lessons = []
            for index in range(lesson_count):
                chapter = CHAPTERS[(index * len(CHAPTERS)) // lesson_count]
                video_id = YOUTUBE_IDS[
                    (course_index * lesson_count + index) % len(YOUTUBE_IDS)
                ]
                lessons.append(
                    Lesson(
                        course=course,
                        title=LESSON_TITLES[index % len(LESSON_TITLES)],
                        chapter=chapter,
                        description=(
                            f"{LESSON_TITLES[index % len(LESSON_TITLES)]} for "
                            f"{subject}."
                        ),
                        content=(
                            f"In this lesson you will explore "
                            f"\"{LESSON_TITLES[index % len(LESSON_TITLES)]}\" as part "
                            f"of {subject}. Follow along, take notes, and complete "
                            "the practice activity before moving on."
                        ),
                        youtube_url=f"https://www.youtube.com/watch?v={video_id}",
                        youtube_video_id=video_id,
                        duration_minutes=8 + (index % 6) * 3,
                        order=index + 1,
                        is_published=True,
                    )
                )
            Lesson.objects.bulk_create(lessons, batch_size=200)
            lessons_created += len(lessons)

            materials = [
                LearningMaterial(
                    course=course,
                    title=f"{subject} - Course Syllabus",
                    description="Overview, schedule, and grading policy.",
                    material_type=LearningMaterial.MaterialType.LINK,
                    external_url="https://developer.mozilla.org/en-US/",
                    uploaded_by=teacher,
                ),
                LearningMaterial(
                    course=course,
                    title=f"{subject} - Reference Notes",
                    description="Supplementary notes and further reading.",
                    material_type=LearningMaterial.MaterialType.LINK,
                    external_url="https://www.w3schools.com/",
                    uploaded_by=teacher,
                ),
            ]
            LearningMaterial.objects.bulk_create(materials, batch_size=200)
            materials_created += len(materials)

            Assignment.objects.create(
                course=course,
                title=f"{subject} - Assignment 1",
                description=(
                    "Complete the practice tasks covered in the lessons and "
                    "submit your work."
                ),
                instructions="Follow the rubric provided in class.",
                due_at=now + timedelta(days=14),
                max_points=Decimal("100"),
                allow_late_submission=True,
                is_published=True,
                created_by=teacher,
            )
            assignments_created += 1

            quiz = Quiz.objects.create(
                course=course,
                title=f"{subject} - Quiz 1",
                description="Check your understanding of the core concepts.",
                instructions="Choose the best answer for each question.",
                time_limit_minutes=15,
                passing_score=60,
                max_attempts=2,
                is_published=True,
                created_by=teacher,
            )
            quizzes_created += 1
            self._add_questions(
                Question, Choice, {"quiz": quiz}, subject, course_index
            )

            exam = Exam.objects.create(
                course=course,
                title=f"{subject} - Midterm Exam",
                description="Comprehensive midterm covering all modules.",
                instructions="Answer all items within the time limit.",
                time_limit_minutes=60,
                passing_score=75,
                max_attempts=1,
                is_published=True,
                created_by=teacher,
            )
            exams_created += 1
            self._add_questions(
                ExamQuestion, ExamChoice, {"exam": exam}, subject, course_index
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Course content seeded for {len(courses)} courses: "
                f"{lessons_created} lessons, {materials_created} materials, "
                f"{assignments_created} assignments, {quizzes_created} quizzes, "
                f"{exams_created} exams."
            )
        )

    def _add_questions(self, question_model, choice_model, parent, subject, seed):
        questions = []
        for index, (template, choices) in enumerate(QUESTION_TEMPLATES):
            correct_index = (seed + index) % len(choices)
            questions.append(
                question_model(
                    text=template.format(subject=subject),
                    points=Decimal("1"),
                    order=index + 1,
                    **parent,
                )
            )
        question_model.objects.bulk_create(questions, batch_size=200)

        saved = list(
            question_model.objects.filter(**parent).order_by("order")
        )
        rows = []
        for index, question in enumerate(saved):
            _, choices = QUESTION_TEMPLATES[index % len(QUESTION_TEMPLATES)]
            correct_index = (seed + index) % len(choices)
            for option in _build_choices(correct_index, choices):
                rows.append(choice_model(question=question, **option))
        choice_model.objects.bulk_create(rows, batch_size=200)
