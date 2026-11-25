from django.conf import settings
from django.db import models


class ForumCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "forum categories"

    def __str__(self) -> str:
        return self.name


class ForumPost(models.Model):
    category = models.ForeignKey(
        ForumCategory, on_delete=models.SET_NULL, related_name="posts", null=True, blank=True
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_posts"
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        indexes = [models.Index(fields=["is_hidden", "created_at"])]

    def __str__(self) -> str:
        return self.title

    @property
    def like_count(self) -> int:
        return self.likes.count()

    @property
    def comment_count(self) -> int:
        return self.comments.filter(is_hidden=False).count()


class ForumComment(models.Model):
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_comments"
    )
    body = models.TextField()
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.author.full_name} - {self.post.title}"


class ForumLike(models.Model):
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="community_unique_like")]

    def __str__(self) -> str:
        return f"{self.user.full_name} likes {self.post.title}"


class ForumSave(models.Model):
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="saves")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_saves"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="community_unique_save")]

    def __str__(self) -> str:
        return f"{self.user.full_name} saved {self.post.title}"


class ForumReport(models.Model):
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="forum_reports"
    )
    reason = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Report on {self.post.title}"
