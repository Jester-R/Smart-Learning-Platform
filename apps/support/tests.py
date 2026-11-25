from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .models import FAQ, Feedback, SupportTicket, TicketMessage


class SupportPhaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0, skip_user_assignment=True)
        cls.student = User.objects.create_user(
            email="phase4-support-student@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Support",
            last_name="Student",
        )
        cls.other = User.objects.create_user(
            email="phase4-support-other@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Support",
            last_name="Other",
        )
        cls.admin = User.objects.create_user(
            email="phase4-support-admin@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            first_name="Support",
            last_name="Admin",
        )
        cls.ticket = SupportTicket.objects.create(
            user=cls.student,
            subject="Login problem",
            description="Cannot sign in.",
            category=SupportTicket.Category.TECHNICAL,
        )

    def test_student_can_create_ticket(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("support:ticket_create"),
            {
                "subject": "Payment question",
                "description": "Need help with a payment.",
                "category": SupportTicket.Category.PAYMENT,
                "priority": SupportTicket.Priority.NORMAL,
            },
        )
        self.assertEqual(response.status_code, 302)
        ticket = SupportTicket.objects.get(subject="Payment question")
        self.assertEqual(ticket.user, self.student)

    def test_ticket_is_private_to_owner(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("support:ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.get(reverse("support:ticket_detail", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_reply_and_change_status(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("support:ticket_detail", args=[self.ticket.pk]),
            {
                "body": "We are investigating.",
                "status": SupportTicket.Status.IN_PROGRESS,
            },
        )
        self.assertEqual(response.status_code, 302)
        message = TicketMessage.objects.get(ticket=self.ticket)
        self.assertTrue(message.is_staff_reply)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, SupportTicket.Status.IN_PROGRESS)

    def test_faq_management_requires_permission(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("support:faq_manage"),
            {
                "question": "How do I reset my password?",
                "answer": "Use the reset link.",
                "is_published": "on",
                "order": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(FAQ.objects.filter(question="How do I reset my password?").exists())

        self.client.force_login(self.student)
        response = self.client.get(reverse("support:faq_manage"))
        self.assertEqual(response.status_code, 403)

    def test_student_can_send_feedback(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("support:feedback_create"),
            {
                "subject": "Great platform",
                "message": "The portal is useful.",
                "rating": "5",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Feedback.objects.filter(user=self.student).exists())

    def test_public_help_center_renders_for_anonymous_visitor(self):
        FAQ.objects.create(question="Where are my certificates?", answer="Open the Certificates page.")
        response = self.client.get(reverse("support:faq_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Where are my certificates?")
