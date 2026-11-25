from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class CourseQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Course.Status.PUBLISHED)


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Difficulty(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    code = models.CharField(max_length=30, unique=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
    )
    teacher = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="teaching_courses",
        limit_choices_to={"role": "teacher"},
    )
    description = models.TextField()
    objectives = models.TextField(
        blank=True, help_text="One learning objective per line."
    )
    thumbnail = models.ImageField(
        upload_to="courses/thumbnails/", blank=True, null=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    difficulty = models.CharField(
        max_length=20, choices=Difficulty.choices, default=Difficulty.BEGINNER
    )
    duration_hours = models.PositiveIntegerField(default=0)
    passing_score = models.PositiveSmallIntegerField(
        default=75, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    certificate_enabled = models.BooleanField(default=False)
    min_lesson_completion = models.PositiveSmallIntegerField(
        default=80, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    min_assignment_completion = models.PositiveSmallIntegerField(
        default=70, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    min_quiz_average = models.PositiveSmallIntegerField(
        default=75, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    objects = CourseQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "category"]),
            models.Index(fields=["teacher", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._build_unique_slug()
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def _build_unique_slug(self) -> str:
        base = slugify(self.title)[:200] or slugify(self.code)
        slug = base
        counter = 1
        while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            counter += 1
            slug = f"{base}-{counter}"
        return slug

    def get_absolute_url(self) -> str:
        return reverse("courses:detail", kwargs={"slug": self.slug})

    def __str__(self) -> str:
        return f"{self.code} - {self.title}"


class Enrollment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        DROPPED = "dropped", "Dropped"

    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="enrollments",
        limit_choices_to={"role": "student"},
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="enrollments"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    final_grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-enrolled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"], name="unique_student_course_enrollment"
            )
        ]
        indexes = [models.Index(fields=["course", "status"])]

    def clean(self):
        if self.student_id and self.student.role != "student":
            raise ValidationError({"student": "Only users with the student role can enroll."})

    def mark_completed(self, grade: Decimal | None = None):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if grade is not None:
            self.final_grade = grade
        self.save(update_fields=["status", "completed_at", "final_grade", "updated_at"])

    def __str__(self) -> str:
        return f"{self.student.full_name} -> {self.course.title}"


class PaymentMethod(models.Model):
    name = models.CharField(max_length=80, unique=True)
    code = models.SlugField(max_length=60, unique=True, blank=True)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "payment methods"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)[:60]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payments",
        limit_choices_to={"role": "student"},
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, null=True, blank=True, related_name="payments"
    )
    plan = models.ForeignKey(
        "courses.SubscriptionPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reference = models.CharField(max_length=100, blank=True, db_index=True)
    notes = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_payments",
    )
    verified_at = models.DateTimeField(blank=True, null=True)
    verification_notes = models.TextField(blank=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["course", "status"]),
            models.Index(fields=["status", "paid_at"]),
        ]

    def clean(self):
        if self.student_id and self.student.role != "student":
            raise ValidationError({"student": "Only students can make payments."})
        if not self.student_id:
            raise ValidationError({"student": "Select a student for this payment."})
        if not any([self.course_id, self.enrollment_id, self.plan_id]):
            raise ValidationError(
                {"course": "Select a course or subscription plan for this payment."}
            )

    def save(self, *args, **kwargs):
        if self.enrollment_id and (not self.student_id or not self.course_id):
            self.student_id = self.enrollment.student_id
            self.course_id = self.enrollment.course_id
        if self.status == self.Status.COMPLETED and self.paid_at is None:
            self.paid_at = timezone.now()
        super().save(*args, **kwargs)

    def verify(self, user, notes: str = "", reference: str | None = None):
        if self.enrollment_id and (not self.student_id or not self.course_id):
            self.student_id = self.enrollment.student_id
            self.course_id = self.enrollment.course_id
        if self.course_id:
            enrollment, _ = Enrollment.objects.get_or_create(
                student=self.student,
                course=self.course,
                defaults={"status": Enrollment.Status.ACTIVE},
            )
            if enrollment.status in (
                Enrollment.Status.PENDING,
                Enrollment.Status.DROPPED,
            ):
                enrollment.status = Enrollment.Status.ACTIVE
                enrollment.save(update_fields=["status", "updated_at"])
        else:
            enrollment = None
            if self.plan_id:
                StudentSubscription.objects.get_or_create(
                    student=self.student,
                    plan=self.plan,
                    payment=self,
                )
        self.status = self.Status.COMPLETED
        self.enrollment = enrollment
        self.verified_by = user
        self.verified_at = timezone.now()
        self.verification_notes = notes
        if reference is not None:
            self.reference = reference
        if self.paid_at is None:
            self.paid_at = self.verified_at
        self.save(
            update_fields=[
                "status",
                "student",
                "course",
                "plan",
                "enrollment",
                "verified_by",
                "verified_at",
                "verification_notes",
                "reference",
                "paid_at",
                "updated_at",
            ]
        )

    def reject(self, user, notes: str = ""):
        self.status = self.Status.REJECTED
        self.verified_by = user
        self.verified_at = timezone.now()
        self.verification_notes = notes
        self.save(
            update_fields=[
                "status",
                "verified_by",
                "verified_at",
                "verification_notes",
                "updated_at",
            ]
        )

    def mark_refunded(self):
        self.status = self.Status.REFUNDED
        self.save(update_fields=["status", "updated_at"])

    def __str__(self) -> str:
        if self.student_id and self.course_id:
            return f"{self.student.full_name} - {self.course.code} - {self.amount}"
        if self.student_id and self.plan_id:
            return f"{self.student.full_name} - {self.plan.name} - {self.amount}"
        return f"Payment #{self.pk or '-'} - {self.amount}"


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    duration_days = models.PositiveIntegerField(default=30)
    features = models.TextField(
        blank=True, help_text="One feature per line."
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class StudentSubscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="subscriptions",
        limit_choices_to={"role": "student"},
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions"
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["status", "end_date"]),
        ]

    def clean(self):
        if self.student_id and self.student.role != "student":
            raise ValidationError({"student": "Only students can subscribe."})

    def save(self, *args, **kwargs):
        if self.end_date is None:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)

    def cancel(self):
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.plan.name}"


class Invoice(models.Model):
    payment = models.OneToOneField(
        Payment, on_delete=models.CASCADE, related_name="invoice"
    )
    number = models.CharField(max_length=40, unique=True, blank=True)
    issued_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at"]

    def save(self, *args, **kwargs):
        if not self.number:
            super().save(*args, **kwargs)
            self.number = f"INV-{timezone.now().year}-{uuid4().hex[:8].upper()}"
            super().save(update_fields=["number"])
            return
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.number


class Refund(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed"

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="refunds"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True
    )
    requested_by = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="refund_requests"
    )
    processed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_refunds",
    )
    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["payment", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def clean(self):
        if self.payment_id and self.amount > self.payment.amount:
            raise ValidationError(
                {"amount": "Refund amount cannot exceed the payment amount."}
            )

    def _record_processing(self, user, status):
        self.status = status
        self.processed_by = user
        self.processed_at = timezone.now()
        self.save(
            update_fields=["status", "processed_by", "processed_at", "updated_at"]
        )

    def approve(self, user):
        self._record_processing(user, self.Status.APPROVED)

    def reject(self, user):
        self._record_processing(user, self.Status.REJECTED)

    def complete(self, user):
        if self.status != self.Status.APPROVED:
            raise ValidationError("Only approved refunds can be completed.")
        self._record_processing(user, self.Status.COMPLETED)
        self.payment.mark_refunded()

    def __str__(self) -> str:
        return f"{self.payment} - {self.amount} - {self.get_status_display()}"
