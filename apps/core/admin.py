from django.contrib import admin

from .models import (
    Department,
    EmailVerificationToken,
    Faculty,
    PasswordResetToken,
    Permission,
    Role,
    RolePermission,
    University,
    UserPermissionOverride,
    UserRole,
)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "level", "is_system", "is_active")
    list_filter = ("is_system", "is_active")
    search_fields = ("code", "name", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "created_at")
    list_filter = ("role", "permission__category")
    search_fields = ("role__code", "permission__code")
    autocomplete_fields = ("role", "permission")
    readonly_fields = ("created_at",)


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "short_name", "email_domain", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "short_name", "email_domain")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "university", "is_active")
    list_filter = ("university", "is_active")
    search_fields = ("code", "name", "university__name")
    autocomplete_fields = ("university",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "faculty", "is_active")
    list_filter = ("faculty__university", "is_active")
    search_fields = ("code", "name", "faculty__name")
    autocomplete_fields = ("faculty",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "university", "is_primary", "expires_at")
    list_filter = ("role", "is_primary", "university")
    search_fields = ("user__email", "user__first_name", "user__last_name", "role__code")
    autocomplete_fields = ("role", "university")
    readonly_fields = ("assigned_at",)


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ("user", "permission", "is_granted", "created_at")
    list_filter = ("is_granted", "permission__category")
    search_fields = ("user__email", "permission__code")
    autocomplete_fields = ("permission",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at")
    search_fields = ("user__email",)
    readonly_fields = ("token", "created_at")


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at")
    search_fields = ("user__email",)
    readonly_fields = ("token", "created_at")
