from django.conf import settings
from django.db import models

from apps.core.models import University


class ScholarshipCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "scholarship categories"

    def __str__(self) -> str:
        return self.name


class Scholarship(models.Model):
    category = models.ForeignKey(
        ScholarshipCategory, on_delete=models.SET_NULL, related_name="scholarships", null=True, blank=True
    )
    university = models.ForeignKey(
        University, on_delete=models.SET_NULL, related_name="scholarships", null=True, blank=True
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    eligibility = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    deadline = models.DateField(blank=True, null=True, db_index=True)
    application_link = models.URLField(blank=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["deadline", "title"]

    def __str__(self) -> str:
        return self.title


class ScholarshipApplication(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWING = "reviewing", "Reviewing"
        AWARDED = "awarded", "Awarded"
        NOT_AWARDED = "not_awarded", "Not awarded"

    scholarship = models.ForeignKey(
        Scholarship, on_delete=models.CASCADE, related_name="applications"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scholarship_applications"
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["scholarship", "student"], name="scholarships_unique_application"
            )
        ]

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.scholarship.title}"
