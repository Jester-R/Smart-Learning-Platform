"""Create demo student accounts with profiles and course enrollments."""

from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import StudentProfile, User
from apps.courses.models import Course, Enrollment

DEFAULT_PASSWORD = "Student@12345"

FIRST_NAMES = [
    "Aaliyah", "Aaron", "Abigail", "Adrian", "Aisha", "Alejandro", "Alexa",
    "Amara", "Andre", "Angela", "Aria", "Benjamin", "Bianca", "Caleb",
    "Camila", "Carlos", "Carmen", "Chloe", "Daniel", "Daniella", "David",
    "Diego", "Elena", "Elijah", "Ella", "Emmanuel", "Ethan", "Fatima",
    "Gabriel", "Grace", "Hannah", "Haruto", "Isaac", "Isabella", "Jasmine",
    "Javier", "Joanna", "John", "Jose", "Joshua", "Julia", "Kai", "Karen",
    "Kevin", "Laila", "Leo", "Liam", "Lucas", "Lucia", "Maria", "Mark",
    "Mateo", "Maya", "Mia", "Noah", "Olivia", "Omar", "Priya", "Rachel",
    "Rafael", "Sara", "Sofia", "Tariq", "Valentina", "Victoria", "William",
    "Yara", "Zoe",
]

LAST_NAMES = [
    "Adams", "Alvarez", "Anderson", "Baker", "Bautista", "Brown", "Castillo",
    "Chen", "Cruz", "Davis", "Delgado", "Diaz", "Edwards", "Evans", "Flores",
    "Garcia", "Gonzalez", "Green", "Gupta", "Hall", "Hernandez", "Hill",
    "Ibrahim", "Jackson", "Johnson", "Khan", "Kim", "Lee", "Lewis", "Lopez",
    "Martin", "Martinez", "Mendoza", "Miller", "Mitchell", "Moore", "Morales",
    "Nelson", "Nguyen", "Ortiz", "Parker", "Patel", "Perez", "Ramos",
    "Reyes", "Rivera", "Roberts", "Rodriguez", "Romero", "Rosa", "Sanchez",
    "Santos", "Smith", "Taylor", "Thomas", "Torres", "Turner", "Vargas",
    "Walker", "Wang", "White", "Williams", "Wilson", "Wright", "Young",
]

PROGRAMS = [
    "Computer Science",
    "Information Technology",
    "Business Administration",
    "Education",
    "Engineering",
    "Nursing",
]

SECTIONS = ["A", "B", "C", "D"]


class Command(BaseCommand):
    help = (
        "Create demo student accounts, student profiles, and course "
        "enrollments. The command tops up to the requested total and is "
        "safe to run repeatedly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=30,
            help="Total number of student accounts to ensure (default: 30).",
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for generated students (default: {DEFAULT_PASSWORD}).",
        )
        parser.add_argument(
            "--prefix",
            default="student",
            help="Email prefix for generated accounts (default: student).",
        )
        parser.add_argument(
            "--enroll",
            type=int,
            default=2,
            help="Published courses to enroll each new student in (default: 2, 0 to skip).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        target = max(0, options["count"])
        prefix = options["prefix"].strip() or "student"
        password = options["password"]
        enroll_limit = max(0, options["enroll"])

        current = User.objects.filter(role=User.Role.STUDENT).count()
        needed = max(0, target - current)
        created = []

        if needed:
            existing_emails = set(User.objects.values_list("email", flat=True))
            hashed_password = make_password(password)
            now = timezone.now()
            users = []
            sequence = 1
            while len(users) < needed:
                email = f"{prefix}{sequence:04d}@smartlearning.local"
                sequence += 1
                if email in existing_emails:
                    continue

                index = len(users)
                users.append(
                    User(
                        email=email,
                        password=hashed_password,
                        role=User.Role.STUDENT,
                        first_name=FIRST_NAMES[index % len(FIRST_NAMES)],
                        last_name=LAST_NAMES[(index * 7) % len(LAST_NAMES)],
                        is_verified=True,
                        date_joined=now - timedelta(days=(index % 60) + 1),
                    )
                )

            User.objects.bulk_create(users, batch_size=500)
            created = list(
                User.objects.filter(
                    email__in=[user.email for user in users]
                ).order_by("id")
            )

            profiles = [
                StudentProfile(
                    user=user,
                    program=PROGRAMS[index % len(PROGRAMS)],
                    year_level=(index % 4) + 1,
                    section=SECTIONS[index % len(SECTIONS)],
                    enrollment_date=user.date_joined.date(),
                )
                for index, user in enumerate(created)
            ]
            StudentProfile.objects.bulk_create(
                profiles, batch_size=500, ignore_conflicts=True
            )

        enrolled = 0
        if created and enroll_limit:
            courses = list(
                Course.objects.filter(status=Course.Status.PUBLISHED).order_by("id")
            )
            if courses:
                rows = []
                for index, user in enumerate(created):
                    offset = index % len(courses)
                    selected = [
                        courses[(offset + step) % len(courses)]
                        for step in range(min(enroll_limit, len(courses)))
                    ]
                    rows.extend(
                        Enrollment(student=user, course=course)
                        for course in selected
                    )
                Enrollment.objects.bulk_create(
                    rows, batch_size=500, ignore_conflicts=True
                )
                enrolled = len(rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"Student seed complete: {len(created)} created, "
                f"{len(created) and enrolled or 0} enrollments, "
                f"{User.objects.filter(role=User.Role.STUDENT).count()} students total."
            )
        )
        if created:
            self.stdout.write(
                f"  First account: {created[0].email} / {password}"
            )
            self.stdout.write(
                f"  Last account:  {created[-1].email} / {password}"
            )
