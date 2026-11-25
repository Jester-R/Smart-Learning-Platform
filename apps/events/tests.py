from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User

from .models import Event, EventRegistration


class EventsPhaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0, skip_user_assignment=True)
        cls.student = User.objects.create_user(
            email="phase4-event-student@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Event",
            last_name="Student",
        )
        cls.admin = User.objects.create_user(
            email="phase4-event-admin@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            first_name="Event",
            last_name="Admin",
        )
        start = timezone.now() + timedelta(days=7)
        end = start + timedelta(hours=2)
        cls.event = Event.objects.create(
            title="Open Workshop",
            description="Public workshop.",
            starts_at=start,
            ends_at=end,
            location="Main Hall",
            capacity=2,
        )
        cls.exclusive = Event.objects.create(
            title="Pro Workshop",
            description="Premium workshop.",
            starts_at=start,
            ends_at=end,
            is_exclusive=True,
        )

    def test_student_can_register_for_event(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("events:register", args=[self.event.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            EventRegistration.objects.filter(event=self.event, user=self.student).exists()
        )

    def test_exclusive_event_denies_student(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("events:register", args=[self.exclusive.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            EventRegistration.objects.filter(event=self.exclusive, user=self.student).exists()
        )

    def test_admin_can_create_event(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("events:create"),
            {
                "title": "Career Fair",
                "description": "Meet companies.",
                "starts_at": "2026-12-15T09:00",
                "ends_at": "2026-12-15T12:00",
                "location": "Campus",
                "capacity": "100",
                "is_published": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Event.objects.filter(title="Career Fair").exists())

    def test_student_cannot_create_event(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("events:create"))
        self.assertEqual(response.status_code, 403)

    def test_public_event_list_renders_for_anonymous_visitor(self):
        response = self.client.get(reverse("events:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open Workshop")
