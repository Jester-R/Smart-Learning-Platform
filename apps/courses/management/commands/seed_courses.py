"""Create demo courses across categories and teachers."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.courses.models import Category, Course, Enrollment

DEFAULT_COUNT = 89
DEFAULT_ENROLL = 25

SUBJECTS = [
    "Python Programming", "Web Development", "Data Structures", "Algorithms",
    "Database Systems", "Computer Networking", "Cybersecurity",
    "Cloud Computing", "Machine Learning", "Data Science", "Statistics",
    "Calculus", "Linear Algebra", "Discrete Mathematics",
    "Software Engineering", "Mobile Development", "Game Development",
    "UI/UX Design", "Digital Marketing", "Business Analytics",
    "Project Management", "English Communication", "Academic Writing",
    "Physics", "Chemistry", "Biology", "Economics", "Accounting",
    "Multimedia Arts", "Information Systems",
]

LEVELS = ["Introduction to", "Intermediate", "Advanced"]

DIFFICULTIES = [
    Course.Difficulty.BEGINNER,
    Course.Difficulty.INTERMEDIATE,
    Course.Difficulty.ADVANCED,
]


class Command(BaseCommand):
    help = (
        "Create demo courses, assign teachers and categories, and enroll a "
        "sample of students in each new course. Tops up to the requested "
        "total and is safe to run repeatedly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=DEFAULT_COUNT,
            help=f"Total number of courses to ensure (default: {DEFAULT_COUNT}).",
        )
        parser.add_argument(
            "--enroll",
            type=int,
            default=DEFAULT_ENROLL,
            help="Students to enroll per new course (default: 25, 0 to skip).",
        )
        parser.add_argument(
            "--published-ratio",
            type=float,
            default=0.85,
            help="Fraction of new courses that are published (default: 0.85).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        target = max(0, options["count"])
        enroll_per_course = max(0, options["enroll"])
        published_ratio = min(max(options["published_ratio"], 0.0), 1.0)

        teachers = list(User.objects.filter(role=User.Role.TEACHER).order_by("id"))
        if not teachers:
            self.stderr.write(self.style.ERROR("Teachers are required first."))
            return

        categories = list(Category.objects.order_by("id"))
        if not categories:
            self.stderr.write(
                self.style.ERROR("Run seed_course_categories first.")
            )
            return

        current = Course.objects.count()
        needed = max(0, target - current)
        if needed == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Courses already at {current}; nothing to add."
                )
            )
            return

        existing_codes = set(Course.objects.values_list("code", flat=True))
        existing_slugs = set(Course.objects.values_list("slug", flat=True))
        now = timezone.now()
        published_cutoff = int(needed * published_ratio)

        courses = []
        sequence = 1
        while len(courses) < needed:
            code = f"CRS{sequence:03d}"
            sequence += 1
            if code in existing_codes:
                continue

            index = len(courses)
            subject = SUBJECTS[index % len(SUBJECTS)]
            level = LEVELS[(index // len(SUBJECTS)) % len(LEVELS)]
            title = f"{level} {subject}"
            slug = slugify(f"{title}-{code}")
            suffix = 2
            while slug in existing_slugs:
                slug = slugify(f"{title}-{code}-{suffix}")
                suffix += 1
            existing_slugs.add(slug)

            is_published = index < published_cutoff
            status = (
                Course.Status.PUBLISHED if is_published else Course.Status.DRAFT
            )
            courses.append(
                Course(
                    code=code,
                    title=title,
                    slug=slug,
                    category=categories[index % len(categories)],
                    teacher=teachers[index % len(teachers)],
                    description=(
                        f"{title} builds practical skills through guided lessons, "
                        "hands-on activities, and authentic assessments."
                    ),
                    objectives=(
                        "Understand the core concepts\n"
                        "Apply skills in practical exercises\n"
                        "Complete a final project"
                    ),
                    status=status,
                    difficulty=DIFFICULTIES[index % len(DIFFICULTIES)],
                    duration_hours=8 + (index % 25),
                    certificate_enabled=is_published,
                    is_featured=index < 6 and is_published,
                    published_at=(
                        now - timedelta(days=index * 2) if is_published else None
                    ),
                )
            )

        Course.objects.bulk_create(courses, batch_size=300)
        created = list(
            Course.objects.filter(code__in=[course.code for course in courses])
        )

        enrolled = 0
        if enroll_per_course:
            students = list(
                User.objects.filter(role=User.Role.STUDENT).order_by("id")
            )
            if students:
                rows = []
                for course_index, course in enumerate(created):
                    if course.status != Course.Status.PUBLISHED:
                        continue
                    count = min(enroll_per_course, len(students))
                    start = (course_index * 7) % len(students)
                    for step in range(count):
                        rows.append(
                            Enrollment(
                                student=students[(start + step) % len(students)],
                                course=course,
                            )
                        )
                Enrollment.objects.bulk_create(
                    rows, batch_size=500, ignore_conflicts=True
                )
                enrolled = len(rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"Course seed complete: {len(created)} created "
                f"({sum(1 for c in created if c.status == Course.Status.PUBLISHED)} published), "
                f"{enrolled} enrollment rows, {Course.objects.count()} courses total."
            )
        )
