import uuid
import base64
import hashlib
from datetime import date

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.conf import settings


def generate_student_number() -> str:
    return f"STU-{timezone.now():%Y}-{uuid.uuid4().hex[:6].upper()}"


def generate_employee_number() -> str:
    return f"TCH-{timezone.now():%Y}-{uuid.uuid4().hex[:6].upper()}"


class UserManager(BaseUserManager):
    """Custom manager that uses email as the unique login identifier."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.STUDENT)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Single account model for administrators, teachers, and students.

    Role checks are enforced on the server. The role field is not a substitute
    for ``is_staff``/``is_superuser``; it drives application-level access.
    """

    class Role(models.TextChoices):
        GUEST = "guest", "Guest"
        FREE_STUDENT = "free_student", "Free Student"
        STUDENT = "student", "Student"
        STUDENT_PRO = "student_pro", "Student Pro"
        STUDENT_PREMIUM = "student_premium", "Student Premium"
        TEACHER = "teacher", "Teacher"
        LECTURER = "lecturer", "Lecturer"
        INSTRUCTOR = "instructor", "Instructor"
        COMPANY = "company", "Company"
        UNIVERSITY_ADMIN = "university_admin", "University Administrator"
        ADMIN = "admin", "Administrator"
        SUPER_ADMIN = "super_admin", "Super Administrator"

    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Pending"
        SUSPENDED = "suspended", "Suspended"
        REJECTED = "rejected", "Rejected"

    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(
        max_length=32, choices=Role.choices, default=Role.STUDENT, db_index=True
    )
    account_status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
        db_index=True,
    )
    phone_number = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    bio = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "user"
        verbose_name_plural = "users"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email

    @property
    def is_admin_role(self) -> bool:
        return self.role in {self.Role.ADMIN, self.Role.SUPER_ADMIN} or self.is_superuser

    @property
    def is_teacher_role(self) -> bool:
        return self.role in {self.Role.TEACHER, self.Role.LECTURER}

    @property
    def is_student_role(self) -> bool:
        return self.role in {
            self.Role.STUDENT,
            self.Role.FREE_STUDENT,
            self.Role.STUDENT_PRO,
            self.Role.STUDENT_PREMIUM,
        }

    @property
    def is_university_admin_role(self) -> bool:
        return self.role == self.Role.UNIVERSITY_ADMIN

    def has_role(self, code: str) -> bool:
        from apps.core.services import user_has_role

        return user_has_role(self, code)

    def has_permission(self, code: str) -> bool:
        from apps.core.services import user_has_permission

        return user_has_permission(self, code)

    def __str__(self) -> str:
        return f"{self.full_name} ({self.get_role_display()})"


class PlatformConfiguration(models.Model):
    """Singleton controls for shared platform services."""

    ai_assistant_enabled = models.BooleanField(default=True)
    video_downloads_enabled = models.BooleanField(default=True)
    encrypted_gemini_api_key = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "platform configuration"
        verbose_name_plural = "platform configuration"

    @classmethod
    def get_solo(cls):
        configuration, _ = cls.objects.get_or_create(pk=1)
        return configuration

    @staticmethod
    def _fernet():
        from cryptography.fernet import Fernet

        derived_key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(derived_key))

    def set_gemini_api_key(self, api_key):
        self.encrypted_gemini_api_key = (
            self._fernet().encrypt(api_key.encode("utf-8")).decode("ascii")
            if api_key
            else ""
        )

    def get_gemini_api_key(self):
        if not self.encrypted_gemini_api_key:
            return ""
        from cryptography.fernet import InvalidToken

        try:
            return self._fernet().decrypt(
                self.encrypted_gemini_api_key.encode("ascii")
            ).decode("utf-8")
        except (InvalidToken, ValueError):
            return ""

    def __str__(self):
        return "Platform configuration"


class StudentProfile(models.Model):
    class YearLevel(models.IntegerChoices):
        FIRST = 1, "First Year"
        SECOND = 2, "Second Year"
        THIRD = 3, "Third Year"
        FOURTH = 4, "Fourth Year"
        FIFTH = 5, "Fifth Year"

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    student_number = models.CharField(
        max_length=20, unique=True, default=generate_student_number, editable=False
    )
    program = models.CharField(max_length=120, blank=True)
    year_level = models.PositiveSmallIntegerField(
        choices=YearLevel.choices, default=YearLevel.FIRST
    )
    section = models.CharField(max_length=60, blank=True)
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    enrollment_date = models.DateField(default=date.today)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student_number"]
        verbose_name = "student profile"
        verbose_name_plural = "student profiles"

    def __str__(self) -> str:
        return f"{self.student_number} - {self.user.full_name}"


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )
    employee_number = models.CharField(
        max_length=20, unique=True, default=generate_employee_number, editable=False
    )
    department = models.CharField(max_length=120, blank=True)
    specialization = models.CharField(max_length=160, blank=True)
    qualification = models.CharField(max_length=160, blank=True)
    hire_date = models.DateField(blank=True, null=True)
    office_location = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_number"]
        verbose_name = "teacher profile"
        verbose_name_plural = "teacher profiles"

    def __str__(self) -> str:
        return f"{self.employee_number} - {self.user.full_name}"
