from django.contrib import admin

from .models import Event, EventCategory, EventRegistration


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_at", "ends_at", "location", "is_published", "is_exclusive")
    list_filter = ("is_published", "is_exclusive")
    search_fields = ("title", "description", "location")


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "status", "registered_at")
    list_filter = ("status",)
