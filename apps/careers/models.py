from django.conf import settings
from django.db import models


class CompanyProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="company_profile"
    )
    company_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    contact_email = models.EmailField()
    logo = models.ImageField(upload_to="company-logos/", blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self) -> str:
        return self.company_name


class JobPostingPackage(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price"]

    def __str__(self) -> str:
        return self.name


class Job(models.Model):
    class JobType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        INTERNSHIP = "internship", "Internship"
        CONTRACT = "contract", "Contract"
        REMOTE = "remote", "Remote"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending approval"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    company = models.ForeignKey(
        CompanyProfile, on_delete=models.CASCADE, related_name="jobs"
    )
    package = models.ForeignKey(
        JobPostingPackage,
        on_delete=models.SET_NULL,
        related_name="jobs",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    responsibilities = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    location = models.CharField(max_length=150, blank=True)
    job_type = models.CharField(max_length=20, choices=JobType.choices)
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    application_deadline = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "is_approved"])]

    def __str__(self) -> str:
        return f"{self.title} - {self.company.company_name}"


class CVDocument(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cv_documents"
    )
    title = models.CharField(max_length=150)
    file = models.FileField(upload_to="cvs/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class JobApplication(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        REVIEWING = "reviewing", "Reviewing"
        SHORTLISTED = "shortlisted", "Shortlisted"
        REJECTED = "rejected", "Rejected"
        HIRED = "hired", "Hired"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_applications"
    )
    cover_letter = models.TextField(blank=True)
    cv_document = models.ForeignKey(
        CVDocument, on_delete=models.SET_NULL, related_name="applications", null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPLIED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "applicant"], name="careers_unique_application")
        ]

    def __str__(self) -> str:
        return f"{self.applicant.full_name} - {self.job.title}"


class ApplicationMessage(models.Model):
    application = models.ForeignKey(
        JobApplication, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="application_messages"
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.sender.full_name} - {self.application.job.title}"
