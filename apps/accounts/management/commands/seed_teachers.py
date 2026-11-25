"""Create demo teacher accounts with profiles."""

from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import TeacherProfile, User

DEFAULT_PASSWORD = "Teacher@12345"

FIRST_NAMES = [
    "Aaron", "Abigail", "Adrian", "Aisha", "Alejandro", "Amara", "Andre",
    "Angela", "Benjamin", "Bianca", "Caleb", "Camila", "Carlos", "Carmen",
    "Chloe", "Daniel", "David", "Diego", "Elena", "Elijah", "Ella",
    "Emmanuel", "Ethan", "Fatima", "Gabriel", "Grace", "Hannah", "Haruto",
    "Isaac", "Isabella", "Jasmine", "Javier", "Joanna", "John", "Jose",
    "Joshua", "Julia", "Kai", "Karen", "Kevin", "Laila", "Leo", "Liam",
    "Lucas", "Lucia", "Maria", "Mark", "Mateo", "Maya", "Miguel", "Mila",
    "Nathan", "Nia", "Noah", "Olivia", "Omar", "Paolo", "Patricia", "Paul",
    "Rafael", "Rebecca", "Riley", "Robert", "Samantha", "Samuel", "Sara",
    "Sofia", "Sophia", "Teresa", "Thomas", "Valentina", "Victor", "Victoria",
    "William", "Zara", "Zoe",
]

LAST_NAMES = [
    "Abad", "Aguilar", "Alvarez", "Aquino", "Bautista", "Bernardo", "Bonifacio",
    "Castro", "Cruz", "Dela Cruz", "Diaz", "Domingo", "Estrada", "Flores",
    "Garcia", "Gonzales", "Hernandez", "Jimenez", "Lopez", "Lorenzo",
    "Magsaysay", "Manalo", "Mendoza", "Mercado", "Nolasco", "Ocampo",
    "Pascual", "Perez", "Quinto", "Ramos", "Reyes", "Rivera", "Rizal",
    "Rodriguez", "Romero", "Salazar", "Sanchez", "Santiago", "Santos",
    "Sison", "Soriano", "Suarez", "Tan", "Torres", "Vargas", "Velasco",
    "Villanueva", "Yap", "Zamora",
]

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

DEPARTMENTS = [
    "Information Technology",
    "Computer Science",
    "Business",
    "Mathematics",
    "Languages",
    "Science",
]

QUALIFICATIONS = [
    "Master's degree",
    "Doctorate",
    "Master's degree, licensed professional",
    "Bachelor's degree with honors",
]


class Command(BaseCommand):
    help = (
        "Create demo teacher accounts and teacher profiles. The command tops "
        "up to the requested total and is safe to run repeatedly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=48,
            help="Total number of teacher accounts to ensure (default: 48).",
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for generated teachers (default: {DEFAULT_PASSWORD}).",
        )
        parser.add_argument(
            "--prefix",
            default="teacher",
            help="Email prefix for generated accounts (default: teacher).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        target = max(0, options["count"])
        prefix = options["prefix"].strip() or "teacher"
        password = options["password"]

        current = User.objects.filter(role=User.Role.TEACHER).count()
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
                        role=User.Role.TEACHER,
                        first_name=FIRST_NAMES[index % len(FIRST_NAMES)],
                        last_name=LAST_NAMES[(index * 5) % len(LAST_NAMES)],
                        is_verified=True,
                        date_joined=now - timedelta(days=(index % 240) + 1),
                    )
                )

            User.objects.bulk_create(users, batch_size=500)
            created = list(
                User.objects.filter(
                    email__in=[user.email for user in users]
                ).order_by("id")
            )

            profiles = []
            for index, user in enumerate(created):
                department = DEPARTMENTS[index % len(DEPARTMENTS)]
                profiles.append(
                    TeacherProfile(
                        user=user,
                        department=department,
                        specialization=SUBJECTS[index % len(SUBJECTS)],
                        qualification=QUALIFICATIONS[index % len(QUALIFICATIONS)],
                        office_location=f"{department} Faculty Room",
                    )
                )
            TeacherProfile.objects.bulk_create(
                profiles, batch_size=500, ignore_conflicts=True
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Teacher seed complete: {len(created)} created, "
                f"{User.objects.filter(role=User.Role.TEACHER).count()} teachers total."
            )
        )
        if created:
            self.stdout.write(
                f"  First account: {created[0].email} / {password}"
            )
            self.stdout.write(
                f"  Last account:  {created[-1].email} / {password}"
            )
