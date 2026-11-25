from django.contrib import admin

from .models import FAQ, FAQCategory, Feedback, SupportTicket, TicketMessage


@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "is_published", "order")
    list_filter = ("is_published", "category")
    search_fields = ("question", "answer")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "user", "category", "priority", "status")
    list_filter = ("category", "priority", "status")


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "is_staff_reply", "created_at")
    list_filter = ("is_staff_reply",)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("subject", "user", "rating", "created_at")
    list_filter = ("rating",)
