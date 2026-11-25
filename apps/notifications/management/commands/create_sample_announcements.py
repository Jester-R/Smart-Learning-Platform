from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.models import Announcement


SAMPLES = [
    {
        "title": "Example: Welcome to Smart Learning",
        "content": (
            "Welcome to the learning platform. Use your dashboard to find your courses, "
            "review announcements, and keep track of your learning progress."
        ),
        "audience": Announcement.Audience.EVERYONE,
    },
    {
        "title": "Example: Keep your profile up to date",
        "content": (
            "Please check that your profile information is current so teachers and "
            "administrators can support you throughout the term."
        ),
        "audience": Announcement.Audience.EVERYONE,
    },
    {
        "title": "Example: Review assignment due dates",
        "content": (
            "Check the Upcoming deadlines section on your student dashboard and open "
            "each assignment for its instructions and submission requirements."
        ),
        "audience": Announcement.Audience.STUDENTS,
    },
    {
        "title": "Example: Prepare for quizzes and exams",
        "content": (
            "Review lesson notes and course materials before starting an assessment. "
            "Your course page shows published quizzes and examinations."
        ),
        "audience": Announcement.Audience.STUDENTS,
    },
    {
        "title": "Example: Publish a course update",
        "content": (
            "Teachers can use this announcement format to let colleagues know about "
            "course updates, new learning materials, or upcoming teaching activities."
        ),
        "audience": Announcement.Audience.TEACHERS,
    },
]


class Command(BaseCommand):
    help = "Create five clearly labeled sample announcements. Safe to run more than once."

    def handle(self, *args, **options):
        author = User.objects.filter(role=User.Role.ADMIN, is_active=True).first()
        if author is None:
            self.stderr.write(self.style.ERROR("Create an active administrator account first."))
            return

        now = timezone.now()
        for sample in SAMPLES:
            Announcement.objects.update_or_create(
                title=sample["title"],
                defaults={
                    **sample,
                    "created_by": author,
                    "is_published": True,
                    "published_at": now,
                    "course": None,
                },
            )
        self.stdout.write(self.style.SUCCESS("Created or refreshed 5 sample announcements."))
