from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.core.models import EmailVerificationToken, PasswordResetToken

from .models import StudentProfile, User


class AccountFlowTests(TestCase):
    def test_student_registration_creates_profile_and_verification_token(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "account_type": User.Role.STUDENT,
                "first_name": "New",
                "last_name": "Student",
                "email": "new.student@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="new.student@example.com")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())
        self.assertTrue(EmailVerificationToken.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Verify", mail.outbox[0].subject)

    def test_company_registration_sets_company_role(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "account_type": User.Role.COMPANY,
                "first_name": "New",
                "last_name": "Employer",
                "email": "employer@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="employer@example.com")
        self.assertEqual(user.role, User.Role.COMPANY)
        self.assertFalse(StudentProfile.objects.filter(user=user).exists())

    def test_verification_link_activates_email(self):
        user = User.objects.create_user(
            email="verify@example.com",
            password="StrongPass123!",
            first_name="Verify",
            last_name="Student",
        )
        token = EmailVerificationToken.create_for_user(user)

        response = self.client.get(
            reverse("accounts:verify_email"),
            {"uid": user.pk, "token": token.token},
        )

        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        token.refresh_from_db()
        self.assertTrue(user.is_verified)
        self.assertIsNotNone(user.email_verified_at)
        self.assertIsNotNone(token.used_at)

    def test_password_reset_flow_changes_password(self):
        user = User.objects.create_user(
            email="reset@example.com",
            password="StrongPass123!",
            first_name="Reset",
            last_name="Student",
        )

        request_response = self.client.post(
            reverse("accounts:password_reset_request"),
            {"email": user.email},
        )
        self.assertEqual(request_response.status_code, 302)
        token = PasswordResetToken.objects.get(user=user)
        self.assertEqual(len(mail.outbox), 1)

        confirm_url = reverse(
            "accounts:password_reset_confirm", args=[user.pk, token.token]
        )
        self.assertEqual(self.client.get(confirm_url).status_code, 200)
        response = self.client.post(
            confirm_url,
            {
                "new_password1": "NewStrongPass123!",
                "new_password2": "NewStrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        token.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass123!"))
        self.assertIsNotNone(token.used_at)

    def test_suspended_account_cannot_sign_in(self):
        user = User.objects.create_user(
            email="suspended@example.com",
            password="StrongPass123!",
            first_name="Suspended",
            last_name="Student",
            account_status=User.AccountStatus.SUSPENDED,
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"username": user.email, "password": "StrongPass123!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account is not active")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_middleware_logs_out_suspended_account(self):
        user = User.objects.create_user(
            email="active-then-suspended@example.com",
            password="StrongPass123!",
            first_name="Active",
            last_name="Student",
        )
        self.client.force_login(user)
        user.account_status = User.AccountStatus.SUSPENDED
        user.save(update_fields=["account_status"])

        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_profile_shows_roles_and_permissions(self):
        user = User.objects.create_user(
            email="profile@example.com",
            password="StrongPass123!",
            first_name="Profile",
            last_name="Student",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portal roles")
        self.assertContains(response, "Permissions")
