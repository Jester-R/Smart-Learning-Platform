from django.contrib import admin

from .models import Scholarship, ScholarshipApplication, ScholarshipCategory


@admin.register(ScholarshipCategory)
class ScholarshipCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "university", "deadline", "is_published")
    list_filter = ("is_published", "category")
    search_fields = ("title", "description")


@admin.register(ScholarshipApplication)
class ScholarshipApplicationAdmin(admin.ModelAdmin):
    list_display = ("scholarship", "student", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("scholarship__title", "student__email")
