from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Announcement(models.Model):
    class Audience(models.TextChoices):
        EVERYONE = "everyone", "Everyone"
        STUDENTS = "students", "All Students"
        TEACHERS = "teachers", "All Teachers"
        COURSE = "course", "Specific Course"

    title = models.CharField(max_length=200)
    content = models.TextField()
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="announcements",
    )
    audience = models.CharField(
        max_length=20, choices=Audience.choices, default=Audience.EVERYONE
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="announcements",
    )
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["audience", "is_published"])]

    def clean(self):
        if self.audience == self.Audience.COURSE and not self.course_id:
            raise ValidationError(
                {"course": "A course must be selected for course announcements."}
            )
        if self.expires_at and self.published_at and self.expires_at <= self.published_at:
            raise ValidationError(
                {"expires_at": "Expiry must be after the publication date."}
            )

    def publish(self):
        self.is_published = True
        self.published_at = timezone.now()
        self.save(update_fields=["is_published", "published_at", "updated_at"])

    def __str__(self) -> str:
        return self.title


class Notification(models.Model):
    class Kind(models.TextChoices):
        INFO = "info", "Information"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ANNOUNCEMENT = "announcement", "Announcement"
        ASSIGNMENT = "assignment", "Assignment"
        QUIZ = "quiz", "Quiz"
        EXAM = "exam", "Examination"
        GRADE = "grade", "Grade"
        CERTIFICATE = "certificate", "Certificate"

    recipient = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.INFO)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    def __str__(self) -> str:
        return f"{self.recipient.full_name} - {self.title}"
