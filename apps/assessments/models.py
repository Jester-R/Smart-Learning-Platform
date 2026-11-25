from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.courses.models import Course


class QuestionType(models.TextChoices):
    MULTIPLE_CHOICE = "multiple_choice", "Multiple Choice"
    TRUE_FALSE = "true_false", "True / False"
    SHORT_ANSWER = "short_answer", "Short Answer"
    ESSAY = "essay", "Essay"


class ResultRelease(models.TextChoices):
    IMMEDIATELY = "immediately", "Immediately after submission"
    AFTER_CLOSE = "after_close", "After the assessment closes"
    MANUAL = "manual", "When released by the teacher"
    NEVER = "never", "Never show results"


class AssessmentMixin(models.Model):
    """Shared configuration for quizzes and midterm examinations."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(600)]
    )
    passing_score = models.PositiveSmallIntegerField(
        default=75, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    max_attempts = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    opens_at = models.DateTimeField(blank=True, null=True)
    closes_at = models.DateTimeField(blank=True, null=True)
    is_published = models.BooleanField(default=False, db_index=True)
    show_results = models.CharField(
        max_length=20, choices=ResultRelease.choices, default=ResultRelease.IMMEDIATELY
    )
    shuffle_questions = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def clean(self):
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValidationError({"closes_at": "Closing time must be after opening time."})

    @property
    def is_available(self) -> bool:
        if not self.is_published:
            return False
        now = timezone.now()
        if self.opens_at and now < self.opens_at:
            return False
        if self.closes_at and now > self.closes_at:
            return False
        return True

    def total_points(self) -> Decimal:
        raise NotImplementedError


class Assignment(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="assignments"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    instructions = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to="assignments/attachments/", blank=True, null=True
    )
    due_at = models.DateTimeField(blank=True, null=True)
    max_points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(Decimal("1"))],
    )
    allow_late_submission = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["course", "is_published", "due_at"])]

    @property
    def is_past_due(self) -> bool:
        return self.due_at is not None and timezone.now() > self.due_at

    def __str__(self) -> str:
        return f"{self.course.code} - {self.title}"


class Submission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        GRADED = "graded", "Graded"
        RETURNED = "returned", "Returned for revision"

    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="submissions",
        limit_choices_to={"role": "student"},
    )
    file = models.FileField(upload_to="submissions/", blank=True, null=True)
    text_response = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_late = models.BooleanField(default=False)
    resubmission_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True
    )
    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions",
    )
    graded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"],
                name="unique_assignment_submission_per_student",
            )
        ]
        indexes = [models.Index(fields=["assignment", "status"])]

    def clean(self):
        if self.score is not None and self.assignment_id:
            if self.score > self.assignment.max_points:
                raise ValidationError(
                    {"score": "Score cannot exceed the assignment's maximum points."}
                )

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.assignment.title}"


class Grade(models.Model):
    class Component(models.TextChoices):
        ASSIGNMENT = "assignment", "Assignment"
        QUIZ = "quiz", "Quiz"
        MIDTERM = "midterm", "Midterm Examination"
        FINAL = "final", "Final Examination"
        PARTICIPATION = "participation", "Participation"
        OVERALL = "overall", "Overall"

    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="grades",
        limit_choices_to={"role": "student"},
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="grades"
    )
    component = models.CharField(max_length=20, choices=Component.choices)
    title = models.CharField(max_length=200)
    score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    max_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(Decimal("1"))],
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="recorded_grades",
    )
    graded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-graded_at"]
        indexes = [models.Index(fields=["course", "student", "component"])]

    def clean(self):
        if self.score > self.max_score:
            raise ValidationError({"score": "Score cannot exceed the maximum score."})

    @property
    def percentage(self) -> Decimal:
        if not self.max_score:
            return Decimal("0")
        return (self.score / self.max_score) * Decimal("100")

    @property
    def weighted_contribution(self) -> Decimal:
        return self.percentage * Decimal(str(self.weight)) / Decimal("100")

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.title}: {self.score}/{self.max_score}"


class Quiz(AssessmentMixin):
    def total_points(self) -> Decimal:
        return self.questions.aggregate(total=models.Sum("points"))["total"] or Decimal("0")

    def __str__(self) -> str:
        return f"{self.course.code} - Quiz: {self.title}"


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.MULTIPLE_CHOICE
    )
    text = models.TextField()
    correct_answer = models.TextField(
        blank=True,
        help_text="Used for short-answer auto-grading. Never shown before submission.",
    )
    explanation = models.TextField(blank=True)
    points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["quiz", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "order"], name="unique_question_order_per_quiz"
            )
        ]

    def __str__(self) -> str:
        return f"Q{self.order}: {self.text[:60]}"


class Choice(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="choices"
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["question", "order"]

    def __str__(self) -> str:
        return self.text[:60]


class QuizAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        GRADED = "graded", "Graded"
        EXPIRED = "expired", "Expired"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
        limit_choices_to={"role": "student"},
    )
    attempt_number = models.PositiveSmallIntegerField(default=1)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS, db_index=True
    )

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "student", "attempt_number"],
                name="unique_quiz_attempt_number_per_student",
            )
        ]
        indexes = [models.Index(fields=["student", "quiz", "status"])]

    @property
    def is_expired(self) -> bool:
        if self.status != self.Status.IN_PROGRESS:
            return False
        deadline = self.started_at + timedelta(minutes=self.quiz.time_limit_minutes)
        return timezone.now() > deadline

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.quiz.title} (Attempt {self.attempt_number})"


class QuizAnswer(models.Model):
    attempt = models.ForeignKey(
        QuizAttempt, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="answers"
    )
    selected_choice = models.ForeignKey(
        Choice, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    text_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(blank=True, null=True)
    points_awarded = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="unique_quiz_answer_per_question",
            )
        ]

    def __str__(self) -> str:
        return f"{self.attempt} - {self.question}"


class Exam(AssessmentMixin):
    def total_points(self) -> Decimal:
        return self.questions.aggregate(total=models.Sum("points"))["total"] or Decimal("0")

    def __str__(self) -> str:
        return f"{self.course.code} - Midterm: {self.title}"


class ExamQuestion(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    question_type = models.CharField(
        max_length=20, choices=QuestionType.choices, default=QuestionType.MULTIPLE_CHOICE
    )
    text = models.TextField()
    correct_answer = models.TextField(
        blank=True,
        help_text="Used for short-answer auto-grading. Never shown before submission.",
    )
    explanation = models.TextField(blank=True)
    points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["exam", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "order"], name="unique_question_order_per_exam"
            )
        ]

    def __str__(self) -> str:
        return f"Q{self.order}: {self.text[:60]}"


class ExamChoice(models.Model):
    question = models.ForeignKey(
        ExamQuestion, on_delete=models.CASCADE, related_name="choices"
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["question", "order"]

    def __str__(self) -> str:
        return self.text[:60]


class ExamAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        GRADED = "graded", "Graded"
        EXPIRED = "expired", "Expired"

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="exam_attempts",
        limit_choices_to={"role": "student"},
    )
    attempt_number = models.PositiveSmallIntegerField(default=1)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS, db_index=True
    )

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "student", "attempt_number"],
                name="unique_exam_attempt_number_per_student",
            )
        ]
        indexes = [models.Index(fields=["student", "exam", "status"])]

    @property
    def is_expired(self) -> bool:
        if self.status != self.Status.IN_PROGRESS:
            return False
        deadline = self.started_at + timedelta(minutes=self.exam.time_limit_minutes)
        return timezone.now() > deadline

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.exam.title} (Attempt {self.attempt_number})"


class ExamAnswer(models.Model):
    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(
        ExamQuestion, on_delete=models.CASCADE, related_name="answers"
    )
    selected_choice = models.ForeignKey(
        ExamChoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    text_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(blank=True, null=True)
    points_awarded = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="unique_exam_answer_per_question",
            )
        ]

    def __str__(self) -> str:
        return f"{self.attempt} - {self.question}"
