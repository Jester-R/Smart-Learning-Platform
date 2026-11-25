from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.academic.models import AcademicCalendar, ExamSchedule
from apps.assessments.models import Exam
from apps.courses.models import Course

SLOTS = [
    (time(8, 0), time(9, 30), "Midterm Examination"),
    (time(10, 30), time(12, 0), "Final Examination"),
    (time(14, 0), time(15, 30), "Assessment Window"),
]
DAY_COUNT = 12
VENUES = ["Room A-101", "Room B-204", "Online / Proctored", "Lab 3", "Main Hall"]


class Command(BaseCommand):
    help = "Seed exam slots across multiple weekdays and an exam-period calendar entry (idempotent)."

    def handle(self, *args, **options):
        courses = list(Course.objects.filter(status=Course.Status.PUBLISHED).order_by("code")[:36])
        if not courses:
            self.stdout.write(self.style.WARNING("No published courses found; seed courses first."))
            return

        day = timezone.localdate() + timedelta(days=1)
        exam_days = []
        while len(exam_days) < DAY_COUNT:
            if day.weekday() < 5:
                exam_days.append(day)
            day += timedelta(days=1)

        created = 0
        for day_index, exam_day in enumerate(exam_days):
            for slot_index, (start_time, end_time, title) in enumerate(SLOTS):
                course = courses[(day_index * len(SLOTS) + slot_index) % len(courses)]
                exam = Exam.objects.filter(course=course).order_by("pk").first()
                start_at = timezone.make_aware(datetime.combine(exam_day, start_time))
                end_at = timezone.make_aware(datetime.combine(exam_day, end_time))
                _, was_created = ExamSchedule.objects.get_or_create(
                    course=course,
                    title=title,
                    start_at=start_at,
                    defaults={
                        "exam": exam,
                        "end_at": end_at,
                        "venue": VENUES[(day_index + slot_index) % len(VENUES)],
                        "is_published": True,
                        "remarks": "Bring your student ID and arrive 15 minutes early.",
                    },
                )
                created += int(was_created)

        AcademicCalendar.objects.get_or_create(
            title="Examination period",
            start_date=exam_days[0],
            end_date=exam_days[-1],
            defaults={
                "event_type": AcademicCalendar.EventType.EXAM,
                "description": "Midterm, final, and assessment windows published for the current term.",
                "is_published": True,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Exam schedule ready: {created} slots created across "
                f"{len(exam_days)} exam days ({exam_days[0]:%b %d} - {exam_days[-1]:%b %d})."
            )
        )
