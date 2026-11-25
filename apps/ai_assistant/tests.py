import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import PlatformConfiguration, User

from .models import Conversation, Message
from .services import (
    AIUnavailable,
    AIRateLimited,
    _GeminiModelError,
    generate_reply,
)


class AssistantViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            email="student@example.com",
            password="StrongPass123!",
            first_name="Sam",
            last_name="Student",
        )
        cls.other_student = User.objects.create_user(
            email="other@example.com",
            password="StrongPass123!",
            first_name="Olive",
            last_name="Other",
        )
        cls.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Tina",
            last_name="Teacher",
        )
        cls.admin = User.objects.create_user(
            email="admin@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            first_name="Site",
            last_name="Admin",
        )

    def _post_message(self, payload):
        return self.client.post(
            reverse("ai_assistant:send"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_chat_requires_login(self):
        response = self.client.get(reverse("ai_assistant:chat"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_chat_page_creates_a_conversation_for_the_user(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("ai_assistant:chat"))

        self.assertEqual(response.status_code, 200)
        conversation = Conversation.objects.get(user=self.student)
        self.assertEqual(response.context["conversation"], conversation)
        self.assertContains(response, "AI Assistant")
        self.assertContains(response, "Conversations")

    def test_chat_page_reopens_the_most_recent_conversation(self):
        older = Conversation.objects.create(user=self.student, title="Older")
        newer = Conversation.objects.create(user=self.student, title="Newer")
        self.client.force_login(self.student)

        response = self.client.get(reverse("ai_assistant:chat"))

        self.assertEqual(response.context["conversation"], newer)
        self.assertNotEqual(response.context["conversation"], older)

    def test_user_cannot_open_another_users_conversation(self):
        conversation = Conversation.objects.create(
            user=self.other_student, title="Private"
        )
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("ai_assistant:chat"),
            {"conversation": conversation.pk},
        )

        self.assertEqual(response.status_code, 404)

    def test_new_conversation_creates_and_redirects(self):
        self.client.force_login(self.student)

        response = self.client.post(reverse("ai_assistant:new"))

        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get(user=self.student)
        self.assertEqual(response.url, f"/assistant/?conversation={conversation.pk}")

    def test_new_conversation_requires_post(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("ai_assistant:new"))

        self.assertEqual(response.status_code, 405)

    @patch("apps.ai_assistant.views.generate_reply")
    def test_send_message_persists_user_and_assistant_messages(self, generate_reply):
        generate_reply.return_value = ("Photosynthesis converts light into energy.", 21)
        self.client.force_login(self.student)
        conversation = Conversation.objects.create(
            user=self.student, title="New conversation"
        )

        response = self._post_message(
            {"message": "Explain photosynthesis", "conversation_id": conversation.pk}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reply"], "Photosynthesis converts light into energy.")
        self.assertEqual(data["conversation_id"], conversation.pk)
        self.assertEqual(data["tokens"], 21)

        conversation.refresh_from_db()
        self.assertEqual(conversation.title, "Explain photosynthesis")
        user_message = conversation.messages.get(role=Message.Role.USER)
        assistant_message = conversation.messages.get(role=Message.Role.ASSISTANT)
        self.assertEqual(user_message.content, "Explain photosynthesis")
        self.assertEqual(
            assistant_message.content, "Photosynthesis converts light into energy."
        )
        self.assertTrue(assistant_message.is_ai_generated)
        self.assertEqual(assistant_message.token_count, 21)

    @patch("apps.ai_assistant.views.generate_reply")
    def test_send_message_uses_the_newest_conversation_when_none_is_given(
        self, generate_reply
    ):
        generate_reply.return_value = ("Sure.", 1)
        self.client.force_login(self.student)
        conversation = Conversation.objects.create(
            user=self.student, title="Existing"
        )

        response = self._post_message({"message": "Hello"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["conversation_id"], conversation.pk)

    def test_send_message_rejects_blank_messages(self):
        self.client.force_login(self.student)

        response = self._post_message({"message": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_send_message_rejects_long_messages(self):
        self.client.force_login(self.student)

        response = self._post_message({"message": "x" * 2001})

        self.assertEqual(response.status_code, 400)
        self.assertIn("2,000", response.json()["error"])
        self.assertEqual(Message.objects.count(), 0)

    def test_send_message_rejects_invalid_json(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("ai_assistant:send"),
            data="not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_send_message_is_unavailable_when_assistant_is_disabled(self):
        configuration = PlatformConfiguration.get_solo()
        configuration.ai_assistant_enabled = False
        configuration.save()
        self.client.force_login(self.student)

        response = self._post_message({"message": "Hello"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("disabled", response.json()["error"])
        self.assertEqual(Message.objects.count(), 0)

    @override_settings(GEMINI_API_KEY="")
    def test_send_message_reports_missing_api_key(self):
        configuration = PlatformConfiguration.get_solo()
        configuration.set_gemini_api_key("")
        configuration.save()
        self.client.force_login(self.student)

        response = self._post_message({"message": "Hello"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["error"])
        self.assertEqual(
            Message.objects.filter(role=Message.Role.ASSISTANT).count(), 0
        )

    @patch("apps.ai_assistant.views.generate_reply")
    def test_send_message_reports_rate_limit(self, generate_reply):
        generate_reply.side_effect = AIRateLimited("Too many requests.")
        self.client.force_login(self.student)

        response = self._post_message({"message": "Hello"})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"], "Too many requests.")

    @patch("apps.ai_assistant.views.generate_reply")
    def test_send_message_reports_service_failure(self, generate_reply):
        generate_reply.side_effect = AIUnavailable("Service down.")
        self.client.force_login(self.student)

        response = self._post_message({"message": "Hello"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "Service down.")

    @patch("apps.ai_assistant.views.student_has_active_assessment", return_value=True)
    def test_student_is_blocked_during_an_active_assessment(self, _active):
        self.client.force_login(self.student)

        response = self._post_message({"message": "Help me with the exam"})

        self.assertEqual(response.status_code, 403)
        self.assertIn("active quiz", response.json()["error"])
        self.assertEqual(Message.objects.count(), 0)

    def test_teacher_is_not_blocked_by_the_assessment_guard(self):
        with patch(
            "apps.ai_assistant.views.student_has_active_assessment",
            return_value=True,
        ):
            with patch(
                "apps.ai_assistant.views.generate_reply",
                return_value=("Here is a rubric.", 4),
            ):
                self.client.force_login(self.teacher)
                response = self._post_message({"message": "Draft a rubric"})

        self.assertEqual(response.status_code, 200)


class GenerateReplyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            email="student@example.com",
            password="StrongPass123!",
            first_name="Sam",
            last_name="Student",
        )

    def setUp(self):
        self.conversation = Conversation.objects.create(
            user=self.student, title="Test conversation"
        )

    @override_settings(GEMINI_API_KEY="")
    def test_missing_api_key_raises_unavailable(self):
        configuration = PlatformConfiguration.get_solo()
        configuration.set_gemini_api_key("")
        configuration.save()

        with self.assertRaises(AIUnavailable) as context:
            generate_reply(self.student, self.conversation, "Hello")

        self.assertIn("not configured", str(context.exception))

    @override_settings(GEMINI_API_KEY="")
    def test_disabled_assistant_raises_unavailable(self):
        configuration = PlatformConfiguration.get_solo()
        configuration.ai_assistant_enabled = False
        configuration.save()

        with self.assertRaises(AIUnavailable) as context:
            generate_reply(self.student, self.conversation, "Hello")

        self.assertIn("disabled", str(context.exception))

    @patch("apps.ai_assistant.services.check_rate_limit")
    @patch("apps.ai_assistant.services._request_model")
    def test_saved_platform_key_is_used_and_reply_is_extracted(
        self, request_model, _rate_limit
    ):
        request_model.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "A helpful answer."}]}}
            ],
            "usageMetadata": {"totalTokenCount": 42},
        }
        configuration = PlatformConfiguration.get_solo()
        configuration.set_gemini_api_key("saved-test-key")
        configuration.save()

        reply, tokens = generate_reply(self.student, self.conversation, "Hello")

        self.assertEqual(reply, "A helpful answer.")
        self.assertEqual(tokens, 42)
        args = request_model.call_args
        self.assertEqual(args.args[2], "saved-test-key")

    @override_settings(GEMINI_API_KEY="env-test-key")
    @patch("apps.ai_assistant.services.check_rate_limit")
    @patch("apps.ai_assistant.services._request_model")
    def test_environment_key_is_used_when_no_saved_key(
        self, request_model, _rate_limit
    ):
        request_model.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hi."}]}}]
        }

        reply, _tokens = generate_reply(self.student, self.conversation, "Hello")

        self.assertEqual(reply, "Hi.")
        self.assertEqual(request_model.call_args.args[2], "env-test-key")

    @patch("apps.ai_assistant.services.check_rate_limit")
    @patch("apps.ai_assistant.services._request_model")
    def test_retryable_error_falls_back_to_the_next_model(
        self, request_model, _rate_limit
    ):
        configuration = PlatformConfiguration.get_solo()
        configuration.set_gemini_api_key("saved-test-key")
        configuration.save()
        request_model.side_effect = [
            _GeminiModelError(503, "busy"),
            {"candidates": [{"content": {"parts": [{"text": "Fallback reply."}]}}]},
        ]

        with override_settings(
            GEMINI_MODEL="primary-model", GEMINI_FALLBACK_MODELS=["fallback-model"]
        ):
            reply, _tokens = generate_reply(self.student, self.conversation, "Hello")

        self.assertEqual(reply, "Fallback reply.")
        self.assertEqual(request_model.call_count, 2)

    @patch("apps.ai_assistant.services.check_rate_limit")
    @patch("apps.ai_assistant.services._request_model")
    def test_non_retryable_error_raises_unavailable(
        self, request_model, _rate_limit
    ):
        configuration = PlatformConfiguration.get_solo()
        configuration.set_gemini_api_key("saved-test-key")
        configuration.save()
        request_model.side_effect = _GeminiModelError(400, "bad key")

        with self.assertRaises(AIUnavailable):
            generate_reply(self.student, self.conversation, "Hello")

        self.assertEqual(request_model.call_count, 1)
