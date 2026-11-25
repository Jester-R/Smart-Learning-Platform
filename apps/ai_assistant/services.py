import json
import logging
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.assessments.models import ExamAttempt, QuizAttempt
from apps.analytics.models import ActivityLog
from apps.accounts.models import PlatformConfiguration
from apps.courses.models import Category, Course

logger = logging.getLogger(__name__)

HOURLY_LIMIT = 30
RETRYABLE_STATUS_CODES = {404, 429, 500, 502, 503, 504}


class AIUnavailable(Exception):
    pass


class AIRateLimited(Exception):
    pass


class _GeminiModelError(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def student_has_active_assessment(user) -> bool:
    return (
        QuizAttempt.objects.filter(
            student=user, status=QuizAttempt.Status.IN_PROGRESS
        ).exists()
        or ExamAttempt.objects.filter(
            student=user, status=ExamAttempt.Status.IN_PROGRESS
        ).exists()
    )


def check_rate_limit(user):
    since = timezone.now() - timedelta(hours=1)
    used = ActivityLog.objects.filter(
        user=user, action=ActivityLog.Action.AI_QUERY, created_at__gte=since
    ).count()
    if used >= HOURLY_LIMIT:
        raise AIRateLimited(
            "You have reached the AI assistant limit for this hour. Try again later."
        )


def _catalog_context() -> str:
    entries = []
    categories = Category.objects.filter(is_active=True).order_by("name")
    for category in categories:
        published = category.courses.filter(status=Course.Status.PUBLISHED)
        count = published.count()
        samples = list(
            published.order_by("title").values_list("code", "title")[:3]
        )
        sample_text = ", ".join(f"{code} - {title}" for code, title in samples)
        label = "published course" if count == 1 else "published courses"
        entry = f"{category.name} ({count} {label})"
        if sample_text:
            entry += f": e.g. {sample_text}"
        entries.append(entry)
    if not entries:
        return ""
    return (
        " Available course categories (use them to recommend relevant courses): "
        + "; ".join(entries)
        + "."
    )


def _system_prompt(user, conversation) -> str:
    role = getattr(user, "role", "student")
    context = []
    if conversation and conversation.course:
        context.append(f"Course: {conversation.course.title}")
    if conversation and conversation.lesson:
        context.append(f"Lesson: {conversation.lesson.title}")

    if role == "teacher":
        instructions = (
            "You are a teaching assistant for a learning management system. "
            "Help the teacher draft lesson plans, explanations, quiz questions, "
            "rubrics, and feedback. Always remind the teacher to review any "
            "generated content before publishing or using it for grading. "
            "Do not invent student records or private data."
        )
    else:
        instructions = (
            "You are a patient learning assistant for a student. Explain concepts "
            "clearly, ask guiding questions, suggest study strategies, and point to "
            "relevant lessons. Do not simply provide answers to live exams or "
            "quizzes. Encourage the student to attempt the work themselves. "
            "Clearly say when information should be verified."
        )
    if context:
        instructions += " Current context: " + "; ".join(context) + "."
    instructions += _catalog_context()
    instructions += " Identify AI-generated content as a draft when appropriate."
    return instructions


def _history_messages(conversation, limit=12):
    messages = conversation.messages.order_by("-created_at")[:limit]
    contents = []
    for message in reversed(messages):
        if message.role == "user":
            contents.append({"role": "user", "parts": [{"text": message.content}]})
        elif message.role == "assistant":
            contents.append({"role": "model", "parts": [{"text": message.content}]})
    return contents


def _candidate_models():
    models = [settings.GEMINI_MODEL, *settings.GEMINI_FALLBACK_MODELS]
    seen = set()
    return [model for model in models if not (model in seen or seen.add(model))]


def _generation_config(model) -> dict:
    config = {"temperature": 0.6, "maxOutputTokens": 1024}
    if "lite" not in model:
        config["thinkingConfig"] = {"thinkingBudget": 0}
    return config


def _request_model(model, payload, api_key):
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise _GeminiModelError(exc.code, detail) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("Gemini connection error for %s: %s", model, exc)
        raise AIUnavailable(
            "The AI service is unavailable right now. Please try again later."
        ) from exc
    except json.JSONDecodeError as exc:
        raise AIUnavailable("The AI service returned an unreadable response.") from exc


def _extract_reply(data):
    candidates = data.get("candidates") or []
    if not candidates:
        return "", 0
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(part.get("text", "") for part in parts).strip()
    usage = data.get("usageMetadata", {})
    tokens = int(usage.get("totalTokenCount", 0) or 0)
    return text, tokens


def generate_reply(user, conversation, prompt: str) -> tuple[str, int]:
    configuration = PlatformConfiguration.get_solo()
    if not configuration.ai_assistant_enabled:
        raise AIUnavailable("The AI assistant has been disabled by an administrator.")
    api_key = configuration.get_gemini_api_key() or settings.GEMINI_API_KEY
    if not api_key:
        raise AIUnavailable(
            "The AI assistant is not configured yet. Ask an administrator to add a Gemini API token."
        )
    check_rate_limit(user)

    contents = _history_messages(conversation)
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    last_error = None
    for model in _candidate_models():
        payload = {
            "systemInstruction": {
                "parts": [{"text": _system_prompt(user, conversation)}]
            },
            "contents": contents,
            "generationConfig": _generation_config(model),
        }
        try:
            data = _request_model(model, payload, api_key)
        except _GeminiModelError as exc:
            logger.warning("Gemini HTTP error %s for %s: %s", exc.status, model, exc.detail)
            last_error = exc
            if exc.status in RETRYABLE_STATUS_CODES:
                continue
            break
        except AIUnavailable as exc:
            logger.warning("Gemini unavailable for %s: %s", model, exc)
            last_error = exc
            continue

        text, tokens = _extract_reply(data)
        if text:
            return text, tokens
        logger.warning("Gemini returned an empty response for %s", model)

    raise AIUnavailable(
        "The AI service returned an error. Please try again shortly."
    ) from last_error
