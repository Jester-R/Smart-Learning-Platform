from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "is_ai_generated", "token_count", "created_at")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "course", "lesson", "is_archived", "updated_at")
    list_filter = ("is_archived", "course")
    search_fields = (
        "title",
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    autocomplete_fields = ("user", "course", "lesson")
    readonly_fields = ("created_at", "updated_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "is_ai_generated", "created_at")
    list_filter = ("role", "is_ai_generated")
    search_fields = ("content", "conversation__user__email", "conversation__title")
    autocomplete_fields = ("conversation",)
    readonly_fields = ("created_at",)
