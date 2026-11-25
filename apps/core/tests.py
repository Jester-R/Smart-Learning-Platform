from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.permissions import is_admin, is_teacher
from apps.core.constants import PERMISSION_DEFINITIONS, ROLE_DEFINITIONS
from apps.core.models import (
    EmailVerificationToken,
    PasswordResetToken,
    Permission,
    Role,
    UserPermissionOverride,
    UserRole,
)
from apps.core.services import (
    get_active_roles,
    get_user_permissions,
    user_has_permission,
    user_has_role,
)


class RBACTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0, skip_user_assignment=True)
        user_model = get_user_model()
        cls.student = user_model.objects.create_user(
            email="rbac-student@example.com",
            password="Test@12345",
            first_name="RBAC",
            last_name="Student",
            role="student",
        )
        cls.teacher = user_model.objects.create_user(
            email="rbac-teacher@example.com",
            password="Test@12345",
            first_name="RBAC",
            last_name="Teacher",
            role="teacher",
        )
        cls.superuser = user_model.objects.create_superuser(
            email="rbac-admin@example.com",
            password="Test@12345",
            first_name="RBAC",
            last_name="Admin",
        )

    def test_seed_creates_all_roles_and_permissions(self):
        self.assertEqual(Role.objects.count(), len(ROLE_DEFINITIONS))
        self.assertEqual(Permission.objects.count(), len(PERMISSION_DEFINITIONS))
        self.assertTrue(Role.objects.filter(code="super_admin").exists())
        self.assertTrue(Permission.objects.filter(code="settings.manage").exists())

    def test_seed_is_idempotent(self):
        call_command("seed_roles", verbosity=0, skip_user_assignment=True)
        self.assertEqual(Role.objects.count(), len(ROLE_DEFINITIONS))
        self.assertEqual(Permission.objects.count(), len(PERMISSION_DEFINITIONS))

    def test_legacy_roles_map_to_portal_roles(self):
        self.assertTrue(user_has_role(self.student, "free_student"))
        self.assertTrue(user_has_role(self.student, "student"))
        self.assertFalse(user_has_role(self.student, "lecturer"))
        self.assertTrue(user_has_role(self.teacher, "lecturer"))
        self.assertTrue(is_admin(self.superuser))
        self.assertTrue(is_teacher(self.teacher))

    def test_assigned_role_grants_permissions(self):
        role = Role.objects.get(code="lecturer")
        UserRole.objects.create(user=self.student, role=role)
        self.assertTrue(user_has_role(self.student, "lecturer"))
        self.assertTrue(user_has_permission(self.student, "assignment.grade"))

    def test_permission_override_deny_wins(self):
        UserRole.objects.create(user=self.student, role=Role.objects.get(code="lecturer"))
        permission = Permission.objects.get(code="assignment.grade")
        UserPermissionOverride.objects.create(
            user=self.student, permission=permission, is_granted=False
        )
        self.assertFalse(user_has_permission(self.student, "assignment.grade"))

    def test_permission_override_can_grant(self):
        permission = Permission.objects.get(code="settings.manage")
        UserPermissionOverride.objects.create(
            user=self.student, permission=permission, is_granted=True
        )
        self.assertTrue(user_has_permission(self.student, "settings.manage"))

    def test_superuser_has_all_permissions(self):
        self.assertTrue(user_has_permission(self.superuser, "settings.manage"))
        self.assertTrue(user_has_permission(self.superuser, "payment.verify"))
        self.assertIn("super_admin", get_active_roles(self.superuser).values_list("code", flat=True))
        self.assertIn("settings.manage", get_user_permissions(self.superuser))

    def test_tokens_expire_and_mark_used(self):
        email_token = EmailVerificationToken.create_for_user(self.student)
        reset_token = PasswordResetToken.create_for_user(self.student)
        self.assertTrue(email_token.is_valid())
        self.assertTrue(reset_token.is_valid())

        email_token.expires_at = timezone.now() - timedelta(minutes=1)
        email_token.save(update_fields=["expires_at"])
        self.assertFalse(email_token.is_valid())

        reset_token.mark_used()
        self.assertFalse(reset_token.is_valid())
