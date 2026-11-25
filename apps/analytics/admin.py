from django.contrib import admin

from .models import ActivityLog, GradeAuditLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "model_name", "description", "ip_address", "created_at")
    list_filter = ("action", "model_name")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "description",
        "model_name",
    )
    readonly_fields = (
        "user",
        "action",
        "model_name",
        "object_id",
        "description",
        "ip_address",
        "user_agent",
        "metadata",
        "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GradeAuditLog)
class GradeAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "grade",
        "changed_by",
        "old_score",
        "new_score",
        "changed_at",
    )
    list_filter = ("grade__component",)
    search_fields = (
        "grade__student__email",
        "grade__course__code",
        "changed_by__email",
    )
    readonly_fields = (
        "grade",
        "changed_by",
        "old_score",
        "new_score",
        "old_feedback",
        "new_feedback",
        "reason",
        "changed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
