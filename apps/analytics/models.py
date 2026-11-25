from django.db import models


class ActivityLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        VIEW = "view", "View"
        ENROLL = "enroll", "Enrollment"
        SUBMIT = "submit", "Submission"
        GRADE = "grade", "Grading"
        AI_QUERY = "ai_query", "AI Query"
        CERTIFICATE = "certificate", "Certificate"

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    model_name = models.CharField(max_length=80, blank=True)
    object_id = models.PositiveBigIntegerField(blank=True, null=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=300, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        actor = self.user.full_name if self.user else "Anonymous"
        return f"{actor} - {self.get_action_display()} - {self.created_at:%Y-%m-%d %H:%M}"


class GradeAuditLog(models.Model):
    grade = models.ForeignKey(
        "assessments.Grade", on_delete=models.CASCADE, related_name="audit_logs"
    )
    changed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="grade_changes",
    )
    old_score = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    new_score = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    old_feedback = models.TextField(blank=True)
    new_feedback = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self) -> str:
        return f"{self.grade} changed at {self.changed_at:%Y-%m-%d %H:%M}"
