from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.careers.models import JobPostingPackage
from apps.community.models import ForumCategory
from apps.events.models import EventCategory
from apps.scholarships.models import ScholarshipCategory
from apps.support.models import FAQ, FAQCategory


PACKAGES = [
    ("basic", "Basic Listing", "30", "Standard job posting with 30 days visibility."),
    ("featured", "Featured Listing", "79", "Highlighted job posting with priority placement."),
    ("premium", "Premium Listing", "149", "Premium posting with extended visibility and analytics."),
]

FORUM_CATEGORIES = [
    ("General", "Open discussion for all learners."),
    ("Courses", "Questions and discussion about courses."),
    ("Career", "Jobs, internships, and career advice."),
    ("Scholarships", "Scholarship opportunities and application help."),
    ("Events", "Workshops, seminars, and campus events."),
]

EVENT_CATEGORIES = [
    ("Workshop", "Hands-on learning workshops."),
    ("Career Fair", "Recruitment and employer events."),
    ("Seminar", "Academic and professional seminars."),
    ("Competition", "Hackathons and student competitions."),
]

SCHOLARSHIP_CATEGORIES = [
    ("Academic", "Merit-based academic scholarships."),
    ("Needs-based", "Financial support for students in need."),
    ("Sports", "Athletic scholarships."),
]

FAQ_CATEGORIES = ["Account", "Payments", "Courses", "Certificates"]

FAQS = [
    ("Account", "How do I reset my password?", "Use the Forgot password link on the sign-in page."),
    ("Payments", "How do I verify a payment?", "Upload your payment receipt and wait for administrator verification."),
    ("Courses", "How do I access a lesson?", "Enroll in the course, then open the lesson from the course detail page."),
    ("Certificates", "When is a certificate issued?", "Certificates are issued after you complete and pass a course."),
]


class Command(BaseCommand):
    help = "Seed baseline Phase 4 categories, packages, and FAQs (idempotent)."

    def handle(self, *args, **options):
        created = 0

        for code, name, price, description in PACKAGES:
            _, was_created = JobPostingPackage.objects.get_or_create(
                code=code,
                defaults={"name": name, "price": price, "duration_days": 30, "description": description},
            )
            created += int(was_created)

        for name, description in FORUM_CATEGORIES:
            _, was_created = ForumCategory.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name), "description": description},
            )
            created += int(was_created)

        for name, description in EVENT_CATEGORIES:
            _, was_created = EventCategory.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name), "description": description},
            )
            created += int(was_created)

        for name, description in SCHOLARSHIP_CATEGORIES:
            _, was_created = ScholarshipCategory.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name), "description": description},
            )
            created += int(was_created)

        faq_categories = {}
        for name in FAQ_CATEGORIES:
            category, was_created = FAQCategory.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name)},
            )
            faq_categories[name] = category
            created += int(was_created)

        for category_name, question, answer in FAQS:
            _, was_created = FAQ.objects.get_or_create(
                question=question,
                defaults={"category": faq_categories[category_name], "answer": answer},
            )
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(f"Phase 4 baseline data ready: {created} records created.")
        )
