from django.contrib import admin
from django.utils.html import format_html

from .models import (
    AttendanceRecord,
    CourseProgress,
    LearningMaterial,
    LearningProgress,
    Lesson,
)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "chapter",
        "has_youtube_badge",
        "duration_display",
        "order",
        "is_published",
        "video_downloadable",
        "created_at",
    )
    list_filter = ("is_published", "video_downloadable", "course", ("youtube_video_id", admin.EmptyFieldListFilter))
    search_fields = (
        "title",
        "description",
        "chapter",
        "youtube_video_id",
        "content",
        "course__code",
        "course__title",
    )
    autocomplete_fields = ("course",)
    readonly_fields = ("youtube_video_id", "youtube_preview", "created_at", "updated_at")
    ordering = ("course", "order")

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("course", "title", "chapter", "order", "is_published"),
            },
        ),
        (
            "YouTube Video Integration",
            {
                "fields": ("youtube_url", "youtube_video_id", "youtube_preview"),
                "description": "Provide a YouTube URL (watch, youtu.be, embed, or shorts link).",
            },
        ),
        (
            "Content & Duration",
            {
                "fields": ("duration_minutes", "description", "content"),
            },
        ),
        (
            "Alternative Video Sources",
            {
                "classes": ("collapse",),
                "fields": ("video_url", "video_file", "video_downloadable"),
            },
        ),
        (
            "System Information",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    @admin.display(description="YouTube", boolean=True)
    def has_youtube_badge(self, obj):
        return obj.has_youtube

    @admin.display(description="Duration")
    def duration_display(self, obj):
        return obj.duration_display

    @admin.display(description="Video Preview")
    def youtube_preview(self, obj):
        if not obj.has_youtube:
            return format_html('<span style="color: #6c757d;">No YouTube video attached</span>')
        return format_html(
            '<div style="max-width: 480px;">'
            '<iframe width="100%" height="270" src="{}" '
            'frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
            'allowfullscreen style="border-radius: 8px;"></iframe><br/>'
            '<a href="{}" target="_blank" rel="noopener" style="font-size: 12px;">Watch on YouTube (ID: {})</a>'
            '</div>',
            obj.youtube_embed_url,
            obj.youtube_watch_url,
            obj.youtube_video_id,
        )


@admin.register(LearningMaterial)
class LearningMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "lesson",
        "material_type",
        "is_downloadable",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("material_type", "is_downloadable", "course")
    search_fields = ("title", "description", "course__code", "course__title")
    autocomplete_fields = ("course", "lesson", "uploaded_by")
    readonly_fields = ("created_at",)
    list_select_related = ("course", "lesson", "uploaded_by")


@admin.register(LearningProgress)
class LearningProgressAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "lesson",
        "is_completed",
        "completed_at",
        "last_position_seconds",
        "updated_at",
    )
    list_filter = ("is_completed", "lesson__course")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "lesson__title",
    )
    autocomplete_fields = ("student", "lesson")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("student", "lesson")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "course",
        "student",
        "status",
        "recorded_by",
        "updated_at",
    )
    list_filter = ("status", "course", "date")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "course__code",
        "course__title",
    )
    autocomplete_fields = ("student", "course", "recorded_by")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "date"
    list_select_related = ("student", "course", "recorded_by")


@admin.register(CourseProgress)
class CourseProgressAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "course",
        "progress_percent",
        "last_lesson",
        "last_accessed_at",
        "updated_at",
    )
    list_filter = ("course",)
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "course__code",
        "course__title",
    )
    autocomplete_fields = ("student", "course", "last_lesson")
    readonly_fields = ("updated_at",)
    list_select_related = ("student", "course", "last_lesson")
