import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_token() -> str:
    return secrets.token_urlsafe(32)


class Role(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    level = models.PositiveSmallIntegerField(default=0, db_index=True)
    is_system = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["level", "name"]
        verbose_name = "role"
        verbose_name_plural = "roles"

    def __str__(self) -> str:
        return self.name


class Permission(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, default="general", db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "code"]
        verbose_name = "permission"
        verbose_name_plural = "permissions"

    def __str__(self) -> str:
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="permission_links"
    )
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="role_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "role permission"
        verbose_name_plural = "role permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="core_role_permission_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.role.code}: {self.permission.code}"


class University(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=100, blank=True)
    email_domain = models.CharField(max_length=100, blank=True, db_index=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "university"
        verbose_name_plural = "universities"

    def __str__(self) -> str:
        return self.short_name or self.name


class Faculty(models.Model):
    university = models.ForeignKey(
        University, on_delete=models.PROTECT, related_name="faculties"
    )
    code = models.SlugField(max_length=50)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "faculty"
        verbose_name_plural = "faculties"
        constraints = [
            models.UniqueConstraint(
                fields=["university", "code"], name="core_faculty_university_code_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.university} - {self.name}"


class Department(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="departments")
    code = models.SlugField(max_length=50)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "department"
        verbose_name_plural = "departments"
        constraints = [
            models.UniqueConstraint(
                fields=["faculty", "code"], name="core_department_faculty_code_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.faculty} - {self.name}"


class UserRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portal_roles"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_links")
    university = models.ForeignKey(
        University,
        on_delete=models.SET_NULL,
        related_name="user_roles",
        blank=True,
        null=True,
    )
    is_primary = models.BooleanField(default=False)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_portal_roles",
        blank=True,
        null=True,
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        ordering = ["-is_primary", "role__level", "role__name"]
        verbose_name = "user role"
        verbose_name_plural = "user roles"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="core_user_role_unique")
        ]

    def __str__(self) -> str:
        return f"{self.user.email}: {self.role.code}"


class UserPermissionOverride(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="permission_overrides",
    )
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="user_overrides"
    )
    is_granted = models.BooleanField(default=True)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_permission_overrides",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["permission__code"]
        verbose_name = "user permission override"
        verbose_name_plural = "user permission overrides"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "permission"], name="core_user_permission_override_unique"
            )
        ]

    def __str__(self) -> str:
        state = "grant" if self.is_granted else "deny"
        return f"{self.user.email}: {state} {self.permission.code}"


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification_tokens",
    )
    token = models.CharField(max_length=64, unique=True, default=generate_token, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "email verification token"
        verbose_name_plural = "email verification tokens"

    @classmethod
    def create_for_user(cls, user, expires_in_hours: int = 24):
        return cls.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(hours=expires_in_hours),
        )

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def __str__(self) -> str:
        return f"Email verification for {self.user.email}"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token = models.CharField(max_length=64, unique=True, default=generate_token, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "password reset token"
        verbose_name_plural = "password reset tokens"

    @classmethod
    def create_for_user(cls, user, expires_in_hours: int = 2):
        return cls.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(hours=expires_in_hours),
        )

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def __str__(self) -> str:
        return f"Password reset for {self.user.email}"
