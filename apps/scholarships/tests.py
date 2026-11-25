from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .models import Scholarship, ScholarshipApplication


class ScholarshipsPhaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0, skip_user_assignment=True)
        cls.student = User.objects.create_user(
            email="phase4-scholarship-student@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Scholarship",
            last_name="Student",
        )
        cls.admin = User.objects.create_user(
            email="phase4-scholarship-admin@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            first_name="Scholarship",
            last_name="Admin",
        )
        cls.scholarship = Scholarship.objects.create(
            title="STEM Excellence",
            description="Support for STEM students.",
            deadline="2026-12-31",
        )

    def test_admin_can_create_scholarship(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("scholarships:create"),
            {
                "title": "Open Learning Grant",
                "description": "For motivated learners.",
                "deadline": "2027-01-31",
                "is_published": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Scholarship.objects.filter(title="Open Learning Grant").exists())

    def test_student_cannot_create_scholarship(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("scholarships:create"))
        self.assertEqual(response.status_code, 403)

    def test_student_can_apply_once(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("scholarships:apply", args=[self.scholarship.pk]),
            {"notes": "I meet the criteria."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ScholarshipApplication.objects.filter(
                scholarship=self.scholarship, student=self.student
            ).exists()
        )

        response = self.client.get(reverse("scholarships:apply", args=[self.scholarship.pk]))
        self.assertRedirects(response, reverse("scholarships:detail", args=[self.scholarship.pk]))

    def test_public_scholarship_list_renders_for_anonymous_visitor(self):
        response = self.client.get(reverse("scholarships:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "STEM Excellence")
