from django.db import models


class Conversation(models.Model):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="ai_conversations"
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_conversations",
    )
    lesson = models.ForeignKey(
        "learning.Lesson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_conversations",
    )
    title = models.CharField(max_length=200, default="New conversation")
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["user", "is_archived"])]

    def __str__(self) -> str:
        return f"{self.user.full_name} - {self.title}"


class Message(models.Model):
    class Role(models.TextChoices):
        SYSTEM = "system", "System"
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    is_ai_generated = models.BooleanField(default=False)
    token_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        self.is_ai_generated = self.role == self.Role.ASSISTANT
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:60]}"
