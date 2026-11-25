from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .models import Notification
from .views import notification_report_queryset


class NotificationExportPdfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            email="admin@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            first_name="Site",
            last_name="Admin",
        )
        cls.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Tina",
            last_name="Teacher",
        )
        cls.student = User.objects.create_user(
            email="student@example.com",
            password="StrongPass123!",
            first_name="Sam",
            last_name="Student",
        )
        cls.other_student = User.objects.create_user(
            email="other@example.com",
            password="StrongPass123!",
            first_name="Olive",
            last_name="Other",
        )

        cls.admin_notification = Notification.objects.create(
            recipient=cls.admin,
            title="Admin notice",
            message="Visible only to the administrator.",
        )
        cls.student_notification = Notification.objects.create(
            recipient=cls.student,
            title="Student notice",
            message="Visible only to Sam Student.",
        )
        cls.teacher_notification = Notification.objects.create(
            recipient=cls.teacher,
            title="Teacher notice",
            message="Visible only to Tina Teacher.",
        )
        cls.other_notification = Notification.objects.create(
            recipient=cls.other_student,
            title="Other student notice",
            message="Visible only to Olive Other.",
        )

    def test_export_requires_login(self):
        response = self.client.get(reverse("notifications:export_pdf"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_student_downloads_pdf_attachment(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("notifications:export_pdf"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("my-notifications", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 1000)

    def test_admin_downloads_all_notifications_report(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("notifications:export_pdf"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("all-notifications", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_admin_queryset_covers_every_notification(self):
        queryset, show_all = notification_report_queryset(self.admin)

        self.assertTrue(show_all)
        self.assertEqual(queryset.count(), Notification.objects.count())

    def test_student_queryset_only_contains_own_notifications(self):
        queryset, show_all = notification_report_queryset(self.student)

        self.assertFalse(show_all)
        self.assertEqual(list(queryset), [self.student_notification])

    def test_teacher_queryset_only_contains_own_notifications(self):
        queryset, show_all = notification_report_queryset(self.teacher)

        self.assertFalse(show_all)
        self.assertEqual(list(queryset), [self.teacher_notification])

    def test_pdf_reports_empty_state_when_user_has_no_notifications(self):
        self.client.force_login(self.other_student)
        Notification.objects.filter(recipient=self.other_student).delete()

        response = self.client.get(reverse("notifications:export_pdf"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
