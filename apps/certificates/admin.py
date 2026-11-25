from django.contrib import admin

from .models import Certificate, CertificateTemplate


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "issuer_name", "is_default", "created_by", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("name", "description", "issuer_name")
    autocomplete_fields = ("created_by",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "certificate_id",
        "student",
        "course",
        "status",
        "grade_at_issue",
        "issued_by",
        "issued_at",
    )
    list_filter = ("status", "course")
    search_fields = (
        "certificate_id",
        "verification_code",
        "student__email",
        "student__first_name",
        "student__last_name",
        "course__code",
        "course__title",
    )
    autocomplete_fields = ("student", "course", "template", "issued_by")
    readonly_fields = (
        "certificate_id",
        "verification_code",
        "issued_at",
        "revoked_at",
        "pdf_file",
    )
    list_select_related = ("student", "course", "issued_by")
