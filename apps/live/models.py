from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.courses.models import Course
from apps.learning.models import extract_youtube_video_id, validate_youtube_url


class LiveSession(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live now"
        ENDED = "ended", "Ended"
        CANCELLED = "cancelled", "Cancelled"

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="live_sessions"
    )
    teacher = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="live_sessions"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    youtube_url = models.URLField(blank=True, validators=[validate_youtube_url])
    youtube_video_id = models.CharField(max_length=11, blank=True, editable=False)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED, db_index=True
    )
    is_published = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at", "title"]
        indexes = [
            models.Index(fields=["is_published", "starts_at"]),
            models.Index(fields=["course", "starts_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.course.code} - {self.title}"

    def get_absolute_url(self) -> str:
        return reverse("live:detail", args=[self.pk])

    def clean(self):
        super().clean()
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End time must be after start time."})

    def save(self, *args, **kwargs):
        self.youtube_video_id = extract_youtube_video_id(self.youtube_url) or ""
        super().save(*args, **kwargs)

    @property
    def is_live_now(self) -> bool:
        now = timezone.now()
        return (
            self.status == self.Status.LIVE
            and self.starts_at <= now <= self.ends_at
        )

    @property
    def embed_url(self) -> str:
        if not self.youtube_video_id:
            return ""
        return (
            f"https://www.youtube-nocookie.com/embed/{self.youtube_video_id}"
            "?rel=0&modestbranding=1"
        )

    @property
    def youtube_watch_url(self) -> str:
        if not self.youtube_video_id:
            return ""
        return f"https://www.youtube.com/watch?v={self.youtube_video_id}"
