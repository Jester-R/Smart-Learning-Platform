from django.contrib import admin

from .models import (
    ApplicationMessage,
    CVDocument,
    CompanyProfile,
    Job,
    JobApplication,
    JobPostingPackage,
)


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "contact_email", "is_approved")
    list_filter = ("is_approved",)
    search_fields = ("company_name", "contact_email")


@admin.register(JobPostingPackage)
class JobPostingPackageAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "price", "duration_days", "is_active")
    list_filter = ("is_active",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "job_type", "status", "is_approved")
    list_filter = ("status", "is_approved", "job_type")
    search_fields = ("title", "description", "company__company_name")


@admin.register(CVDocument)
class CVDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "created_at")
    search_fields = ("title", "student__email")


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("job", "applicant", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("job__title", "applicant__email")


@admin.register(ApplicationMessage)
class ApplicationMessageAdmin(admin.ModelAdmin):
    list_display = ("application", "sender", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("application__job__title", "sender__email", "body")
