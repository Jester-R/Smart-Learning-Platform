from django.contrib import admin

from .models import Announcement, Notification


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "audience",
        "course",
        "created_by",
        "is_published",
        "published_at",
        "created_at",
    )
    list_filter = ("audience", "is_published")
    search_fields = ("title", "content", "course__code", "course__title")
    autocomplete_fields = ("course", "created_by")
    readonly_fields = ("created_at", "updated_at", "published_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")
    search_fields = (
        "title",
        "message",
        "recipient__email",
        "recipient__first_name",
        "recipient__last_name",
    )
    autocomplete_fields = ("recipient",)
    readonly_fields = ("created_at", "read_at")
    list_select_related = ("recipient",)

    @admin.action(description="Mark selected notifications as read")
    def mark_as_read(self, request, queryset):
        for notification in queryset.filter(is_read=False):
            notification.mark_read()

    actions = ["mark_as_read"]
