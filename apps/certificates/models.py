import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def generate_certificate_id() -> str:
    return f"CERT-{timezone.now():%Y}-{uuid.uuid4().hex[:8].upper()}"


def generate_verification_code() -> str:
    return uuid.uuid4().hex.upper()


class CertificateTemplate(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    background_image = models.ImageField(
        upload_to="certificate_templates/", blank=True, null=True
    )
    body_text = models.TextField(
        default=(
            "This certifies that {student_name} has successfully completed "
            "{course_title} on {issue_date}."
        ),
        help_text="Placeholders: {student_name}, {course_title}, {issue_date}.",
    )
    issuer_name = models.CharField(max_length=160, default="Smart Learning Platform")
    issuer_signature = models.ImageField(
        upload_to="certificate_templates/signatures/", blank=True, null=True
    )
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificate_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if self.is_default:
            CertificateTemplate.objects.filter(is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Certificate(models.Model):
    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        REVOKED = "revoked", "Revoked"

    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="certificates",
        limit_choices_to={"role": "student"},
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="certificates"
    )
    template = models.ForeignKey(
        CertificateTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificates",
    )
    certificate_id = models.CharField(
        max_length=40, unique=True, default=generate_certificate_id, editable=False
    )
    verification_code = models.CharField(
        max_length=64, unique=True, default=generate_verification_code, editable=False
    )
    grade_at_issue = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    issued_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="issued_certificates",
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.VALID, db_index=True
    )
    pdf_file = models.FileField(upload_to="certificates/", blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    revocation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"],
                name="unique_certificate_per_student_course",
            )
        ]
        indexes = [models.Index(fields=["student", "course", "status"])]

    def revoke(self, reason: str = ""):
        self.status = self.Status.REVOKED
        self.revoked_at = timezone.now()
        self.revocation_reason = reason
        self.save(
            update_fields=["status", "revoked_at", "revocation_reason"]
        )

    def __str__(self) -> str:
        return f"{self.certificate_id} - {self.student.full_name}"
