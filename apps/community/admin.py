from django.contrib import admin

from .models import ForumCategory, ForumComment, ForumPost, ForumReport


@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_pinned", "is_locked", "is_hidden")
    list_filter = ("is_pinned", "is_locked", "is_hidden")
    search_fields = ("title", "body")


@admin.register(ForumComment)
class ForumCommentAdmin(admin.ModelAdmin):
    list_display = ("post", "author", "is_hidden", "created_at")
    list_filter = ("is_hidden",)


@admin.register(ForumReport)
class ForumReportAdmin(admin.ModelAdmin):
    list_display = ("post", "reporter", "is_resolved", "created_at")
    list_filter = ("is_resolved",)
