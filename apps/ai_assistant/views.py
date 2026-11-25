import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.analytics.models import ActivityLog
from apps.accounts.models import PlatformConfiguration
from apps.courses.models import Course
from apps.learning.models import Lesson

from .models import Conversation, Message
from .services import (
    AIRateLimited,
    AIUnavailable,
    generate_reply,
    student_has_active_assessment,
)


def _conversation_for(request, conversation_id=None):
    if conversation_id:
        conversation = get_object_or_404(
            Conversation, pk=conversation_id, user=request.user
        )
        return conversation
    conversation = (
        Conversation.objects.filter(user=request.user, is_archived=False)
        .select_related("course", "lesson")
        .first()
    )
    if conversation is None:
        conversation = Conversation.objects.create(
            user=request.user, title="Learning assistant"
        )
    return conversation


@login_required
def chat(request):
    platform_configuration = PlatformConfiguration.get_solo()
    conversation = _conversation_for(
        request, request.GET.get("conversation") or None
    )
    conversations = Conversation.objects.filter(
        user=request.user, is_archived=False
    ).select_related("course")[:20]
    course = None
    lesson = None
    if request.GET.get("course"):
        course = get_object_or_404(Course, pk=request.GET["course"])
    if request.GET.get("lesson"):
        lesson = get_object_or_404(Lesson, pk=request.GET["lesson"])
    if course and not conversation.course_id:
        conversation.course = course
    if lesson and not conversation.lesson_id:
        conversation.lesson = lesson
    if course or lesson:
        conversation.save(update_fields=["course", "lesson", "updated_at"])

    return render(
        request,
        "ai_assistant/chat.html",
        {
            "conversation": conversation,
            "conversations": conversations,
            "course": course,
            "lesson": lesson,
            "messages": conversation.messages.all(),
            "is_enabled": platform_configuration.ai_assistant_enabled,
            "is_configured": bool(
                platform_configuration.encrypted_gemini_api_key
                or settings.GEMINI_API_KEY
            ),
        },
    )


@login_required
@require_POST
def new_conversation(request):
    conversation = Conversation.objects.create(
        user=request.user, title="New conversation"
    )
    return redirect(f"/assistant/?conversation={conversation.pk}")


@login_required
@require_POST
def clear_history(request):
    """Delete chat history for the current conversation (or all of them)."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    if payload.get("all"):
        conversations = Conversation.objects.filter(user=request.user)
        deleted, _ = Message.objects.filter(
            conversation__in=conversations
        ).delete()
        conversations.update(title="Learning assistant")
        return JsonResponse({"cleared": deleted})

    conversation_id = payload.get("conversation_id")
    if conversation_id:
        conversation = get_object_or_404(
            Conversation, pk=conversation_id, user=request.user
        )
    else:
        conversation = _conversation_for(request)

    deleted, _ = Message.objects.filter(conversation=conversation).delete()
    conversation.title = "Learning assistant"
    conversation.save(update_fields=["title", "updated_at"])
    return JsonResponse(
        {"cleared": deleted, "conversation_id": conversation.pk}
    )


@login_required
@require_POST
def send_message(request):
    if not PlatformConfiguration.get_solo().ai_assistant_enabled:
        return JsonResponse(
            {"error": "The AI assistant has been disabled by an administrator."},
            status=503,
        )
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request."}, status=400)

    prompt = (payload.get("message") or "").strip()
    if not prompt:
        return JsonResponse({"error": "Enter a message."}, status=400)
    if len(prompt) > 2000:
        return JsonResponse(
            {"error": "Messages must be 2,000 characters or fewer."}, status=400
        )

    if getattr(request.user, "role", None) == "student" and student_has_active_assessment(
        request.user
    ):
        return JsonResponse(
            {
                "error": (
                    "The assistant is unavailable during an active quiz or "
                    "examination. Submit your attempt first."
                )
            },
            status=403,
        )

    conversation = _conversation_for(request, payload.get("conversation_id"))
    user_message = Message.objects.create(
        conversation=conversation, role=Message.Role.USER, content=prompt
    )
    if conversation.title in ("Learning assistant", "New conversation"):
        conversation.title = prompt[:80]
        conversation.save(update_fields=["title", "updated_at"])

    try:
        reply, tokens = generate_reply(request.user, conversation, prompt)
    except AIRateLimited as exc:
        return JsonResponse({"error": str(exc)}, status=429)
    except AIUnavailable as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    assistant_message = Message.objects.create(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content=reply,
        token_count=tokens,
    )
    ActivityLog.objects.create(
        user=request.user,
        action=ActivityLog.Action.AI_QUERY,
        model_name="Conversation",
        object_id=conversation.pk,
        description=prompt[:200],
    )
    conversation.save(update_fields=["updated_at"])
    return JsonResponse(
        {
            "reply": reply,
            "conversation_id": conversation.pk,
            "message_id": assistant_message.pk,
            "tokens": tokens,
        }
    )
