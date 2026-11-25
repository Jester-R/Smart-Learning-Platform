from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course, Enrollment

from .models import LiveSession


class LivePortalTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="live-teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Live",
            last_name="Teacher",
        )
        self.student = User.objects.create_user(
            email="live-student@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Live",
            last_name="Student",
        )
        self.other_student = User.objects.create_user(
            email="other-student@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Other",
            last_name="Student",
        )
        self.course = Course.objects.create(
            code="LIVE-001",
            title="Live Course",
            description="Course used for live portal tests.",
            teacher=self.teacher,
            status=Course.Status.PUBLISHED,
        )
        Enrollment.objects.create(student=self.student, course=self.course)
        now = timezone.now()
        self.session = LiveSession.objects.create(
            course=self.course,
            teacher=self.teacher,
            title="Live Lesson",
            description="Demo lesson.",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
            status=LiveSession.Status.SCHEDULED,
        )

    def test_enrolled_student_can_open_live_portal_and_session(self):
        self.client.force_login(self.student)
        portal = self.client.get(reverse("live:portal"))
        self.assertEqual(portal.status_code, 200)
        self.assertContains(portal, "Live Lesson")
        detail = self.client.get(reverse("live:detail", args=[self.session.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "youtube-nocookie.com/embed")

    def test_student_not_enrolled_cannot_open_session(self):
        self.client.force_login(self.other_student)
        response = self.client.get(reverse("live:detail", args=[self.session.pk]))
        self.assertEqual(response.status_code, 404)

    def test_teacher_can_schedule_live_session(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("live:create"),
            {
                "course": self.course.pk,
                "title": "Another Live Lesson",
                "description": "Second demo lesson.",
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "starts_at": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                "ends_at": (timezone.now() + timedelta(days=1, hours=1)).strftime("%Y-%m-%dT%H:%M"),
                "status": LiveSession.Status.SCHEDULED,
                "is_published": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            LiveSession.objects.filter(title="Another Live Lesson", teacher=self.teacher).exists()
        )
