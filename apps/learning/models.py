import re
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.courses.models import Course, Enrollment

MATERIAL_EXTENSIONS = ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "zip", "mp3", "mp4"]

YOUTUBE_HOSTS = (
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
)

YOUTUBE_ID_PATTERN = r"^[A-Za-z0-9_-]{11}$"
YOUTUBE_ID_RE = re.compile(YOUTUBE_ID_PATTERN)


def extract_youtube_video_id(url: str | None) -> str | None:
    """Extract and validate the 11-character video ID from supported YouTube URL formats.

    Supported formats:
    - https://www.youtube.com/watch?v=VIDEO_ID (including extra params like &t=10s)
    - https://youtu.be/VIDEO_ID (including query params like ?t=10)
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    - https://www.youtube.com/live/VIDEO_ID
    - http / https / mobile (m.youtube.com) and privacy-enhanced (youtube-nocookie.com)
    """
    if not url:
        return None
    url = url.strip()
    if not url:
        return None

    # Handle URLs pasted without protocol (e.g., 'youtube.com/watch?v=...')
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    hostname = (parsed.hostname or "").lower()
    if hostname not in YOUTUBE_HOSTS:
        return None

    candidate = None
    if hostname in ("youtu.be", "www.youtu.be"):
        # Path is '/VIDEO_ID'
        clean_path = parsed.path.strip("/")
        if clean_path:
            candidate = clean_path.split("/")[0]
    elif parsed.path.startswith("/watch"):
        v_param = parse_qs(parsed.query).get("v")
        if v_param:
            candidate = v_param[0]
    else:
        for prefix in ("/embed/", "/shorts/", "/live/", "/v/"):
            if parsed.path.startswith(prefix):
                remainder = parsed.path[len(prefix):].strip("/")
                if remainder:
                    candidate = remainder.split("/")[0]
                break

    if candidate and YOUTUBE_ID_RE.match(candidate):
        return candidate
    return None


def validate_youtube_url(value: str):
    """Validate that the given URL is a valid, supported YouTube video URL."""
    if value and not extract_youtube_video_id(value):
        raise ValidationError(
            "Enter a valid YouTube URL. Supported formats: "
            "https://www.youtube.com/watch?v=VIDEO_ID, "
            "https://youtu.be/VIDEO_ID, "
            "https://www.youtube.com/embed/VIDEO_ID, or "
            "https://www.youtube.com/shorts/VIDEO_ID."
        )


class Lesson(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="lessons"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    chapter = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Optional chapter or module name to organize lessons.",
    )
    content = models.TextField(
        blank=True, help_text="Lesson notes or reading content shown to students."
    )
    video_url = models.URLField(
        blank=True, help_text="External video URL (YouTube, Vimeo, etc.)."
    )
    video_file = models.FileField(
        upload_to="lessons/videos/", blank=True, null=True
    )
    video_downloadable = models.BooleanField(
        default=True,
        help_text="Allow students to download this uploaded video when platform downloads are enabled.",
    )
    youtube_url = models.URLField(
        blank=True,
        help_text=(
            "YouTube video URL (watch?v=ID, youtu.be/ID, /embed/ID, or /shorts/ID). "
            "Only youtube.com and youtu.be links are accepted."
        ),
        validators=[validate_youtube_url],
    )
    youtube_video_id = models.CharField(
        max_length=11, blank=True, db_index=True, editable=False
    )
    duration_minutes = models.PositiveIntegerField(
        default=0, help_text="Estimated lesson duration in minutes."
    )
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "order"], name="unique_lesson_order_per_course"
            )
        ]
        indexes = [
            models.Index(fields=["course", "is_published"]),
            models.Index(fields=["course", "chapter"]),
        ]

    def clean(self):
        super().clean()
        if self.youtube_url:
            video_id = extract_youtube_video_id(self.youtube_url)
            if not video_id:
                raise ValidationError(
                    {
                        "youtube_url": (
                            "Enter a valid YouTube URL. Supported formats: "
                            "https://www.youtube.com/watch?v=VIDEO_ID, "
                            "https://youtu.be/VIDEO_ID, "
                            "https://www.youtube.com/embed/VIDEO_ID, or "
                            "https://www.youtube.com/shorts/VIDEO_ID."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        if self.youtube_url:
            self.youtube_video_id = extract_youtube_video_id(self.youtube_url) or ""
        else:
            self.youtube_video_id = ""
        super().save(*args, **kwargs)

    @property
    def has_youtube(self) -> bool:
        return bool(self.youtube_video_id)

    @property
    def youtube_embed_url(self) -> str:
        """Safe privacy-enhanced YouTube embed URL."""
        if not self.youtube_video_id:
            return ""
        return f"https://www.youtube-nocookie.com/embed/{self.youtube_video_id}?rel=0&modestbranding=1&enablejsapi=1"

    @property
    def youtube_watch_url(self) -> str:
        if not self.youtube_video_id:
            return ""
        return f"https://www.youtube.com/watch?v={self.youtube_video_id}"

    @property
    def youtube_thumbnail_url(self) -> str:
        if not self.youtube_video_id:
            return ""
        return f"https://img.youtube.com/vi/{self.youtube_video_id}/hqdefault.jpg"

    @property
    def duration(self) -> int:
        """Alias for duration_minutes to satisfy duration property requirement."""
        return self.duration_minutes

    @duration.setter
    def duration(self, value: int):
        self.duration_minutes = value

    @property
    def duration_display(self) -> str:
        if not self.duration_minutes:
            return "0 min"
        hours, mins = divmod(self.duration_minutes, 60)
        if hours and mins:
            return f"{hours}h {mins}m"
        elif hours:
            return f"{hours}h"
        return f"{mins} min"

    def get_absolute_url(self) -> str:
        from django.urls import reverse

        return reverse("learning:lesson", kwargs={"slug": self.course.slug, "pk": self.pk})

    def __str__(self) -> str:
        return f"{self.course.code} - Lesson {self.order}: {self.title}"


class LearningMaterial(models.Model):
    class MaterialType(models.TextChoices):
        PDF = "pdf", "PDF Document"
        DOCUMENT = "document", "Document"
        PRESENTATION = "presentation", "Presentation"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        LINK = "link", "External Link"
        OTHER = "other", "Other"

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="materials"
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materials",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    material_type = models.CharField(
        max_length=20, choices=MaterialType.choices, default=MaterialType.PDF
    )
    file = models.FileField(
        upload_to="materials/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=MATERIAL_EXTENSIONS)],
    )
    external_url = models.URLField(blank=True)
    is_downloadable = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_materials",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["course", "title"]
        indexes = [models.Index(fields=["course", "material_type"])]

    def __str__(self) -> str:
        return f"{self.title} ({self.course.code})"


class LearningProgress(models.Model):
    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="lesson_progress",
        limit_choices_to={"role": "student"},
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="progress_records"
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    last_position_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "lesson"], name="unique_student_lesson_progress"
            )
        ]
        indexes = [models.Index(fields=["student", "is_completed"])]

    def clean(self):
        if self.student_id and self.student.role != "student":
            raise ValidationError({"student": "Progress belongs to a student account."})
        if self.lesson_id and self.student_id:
            enrolled = Enrollment.objects.filter(
                student=self.student, course=self.lesson.course
            ).exists()
            if not enrolled:
                raise ValidationError(
                    {"lesson": "The student must be enrolled in this course."}
                )

    def mark_completed(self):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save(update_fields=["is_completed", "completed_at", "updated_at"])

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.lesson.title}"


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        LATE = "late", "Late"
        ABSENT = "absent", "Absent"
        EXCUSED = "excused", "Excused"

    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="attendance_records",
        limit_choices_to={"role": "student"},
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="attendance_records"
    )
    date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PRESENT,
        db_index=True,
    )
    remarks = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendance",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "course__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course", "date"],
                name="unique_attendance_per_student_course_date",
            )
        ]
        indexes = [
            models.Index(fields=["course", "date"]),
            models.Index(fields=["student", "status"]),
        ]

    @property
    def is_present(self) -> bool:
        return self.status in (self.Status.PRESENT, self.Status.LATE)

    def __str__(self) -> str:
        return (
            f"{self.student.full_name} - {self.course.code} "
            f"({self.date:%b %d, %Y}): {self.get_status_display()}"
        )


class CourseProgress(models.Model):
    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="course_progress",
        limit_choices_to={"role": "student"},
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="progress_records"
    )
    progress_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    last_lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    last_accessed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"], name="unique_student_course_progress"
            )
        ]

    def recalculate(self):
        total = self.course.lessons.filter(is_published=True).count()
        completed = LearningProgress.objects.filter(
            student=self.student,
            lesson__course=self.course,
            lesson__is_published=True,
            is_completed=True,
        ).count()
        self.progress_percent = (completed / total * 100) if total else 0
        self.last_accessed_at = timezone.now()
        self.save(
            update_fields=["progress_percent", "last_accessed_at", "updated_at"]
        )
        return self.progress_percent

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.course.code}: {self.progress_percent}%"
