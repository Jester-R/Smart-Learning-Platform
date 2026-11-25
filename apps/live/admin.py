from django.contrib import admin

from .models import LiveSession


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "teacher",
        "starts_at",
        "ends_at",
        "status",
        "is_published",
    )
    list_filter = ("status", "is_published", "starts_at")
    search_fields = ("title", "description", "course__code", "teacher__email")
