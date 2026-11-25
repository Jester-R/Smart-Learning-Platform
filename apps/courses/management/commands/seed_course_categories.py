"""Create the twelve built-in course categories used across the platform."""

from django.core.management.base import BaseCommand

from apps.courses.models import Category

CATEGORIES = [
    ("Programming", "Core programming, algorithms, and software fundamentals."),
    ("Web Development", "Front-end and back-end web engineering."),
    ("Mobile Development", "Android, iOS, and cross-platform mobile apps."),
    ("Data and AI", "Data science, machine learning, and artificial intelligence."),
    ("Cybersecurity", "Security, privacy, and safe computing practices."),
    ("Cloud Computing", "Cloud platforms, DevOps, and infrastructure."),
    ("Design", "User experience, user interface, and visual design."),
    ("Business", "Entrepreneurship, management, and marketing."),
    ("Mathematics", "Algebra, statistics, calculus, and discrete math."),
    ("Science", "Physics, chemistry, biology, and general science."),
    ("Communication", "Writing, speaking, and professional communication."),
    ("Languages", "English, Khmer, and other world languages."),
]


class Command(BaseCommand):
    help = "Create the twelve built-in course categories (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for name, description in CATEGORIES:
            _, was_created = Category.objects.get_or_create(
                name=name,
                defaults={"description": description},
            )
            if was_created:
                created += 1

        total = Category.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Course categories ready: {created} created, "
                f"{len(CATEGORIES) - created} already existed, {total} total."
            )
        )
