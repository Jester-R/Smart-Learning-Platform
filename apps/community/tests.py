from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .models import ForumLike, ForumPost, ForumReport


class CommunityPhaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0, skip_user_assignment=True)
        cls.student = User.objects.create_user(
            email="phase4-forum-student@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Forum",
            last_name="Student",
        )
        cls.admin = User.objects.create_user(
            email="phase4-forum-admin@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            first_name="Forum",
            last_name="Admin",
        )
        cls.post = ForumPost.objects.create(
            author=cls.student,
            title="Study group",
            body="Who wants to join?",
        )

    def test_student_can_create_post_and_comment(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("community:post_create"),
            {"title": "Exam tips", "body": "Share your revision plan."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ForumPost.objects.filter(title="Exam tips").exists())

        response = self.client.post(
            reverse("community:comment_create", args=[self.post.pk]),
            {"body": "I am interested."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.post.comments.count(), 1)

    def test_like_can_be_toggled(self):
        self.client.force_login(self.student)
        url = reverse("community:toggle_like", args=[self.post.pk])
        self.client.get(url)
        self.assertTrue(ForumLike.objects.filter(post=self.post, user=self.student).exists())
        self.client.get(url)
        self.assertFalse(ForumLike.objects.filter(post=self.post, user=self.student).exists())

    def test_report_and_moderate_post(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("community:report_post", args=[self.post.pk]),
            {"reason": "Spam"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ForumReport.objects.count(), 1)

        self.client.force_login(self.admin)
        response = self.client.get(reverse("community:moderate_post", args=[self.post.pk]))
        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertTrue(self.post.is_hidden)

    def test_student_cannot_moderate(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("community:moderation"))
        self.assertEqual(response.status_code, 403)

    def test_public_forum_list_renders_for_anonymous_visitor(self):
        response = self.client.get(reverse("community:forum_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Study group")

    def test_seed_community_data_adds_organisation_discussions(self):
        call_command("seed_community_data", verbosity=0)
        first_count = ForumPost.objects.count()
        call_command("seed_community_data", verbosity=0)
        self.assertEqual(ForumPost.objects.count(), first_count)
        self.assertGreaterEqual(first_count, 15)

        response = self.client.get(reverse("community:forum_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Companies")
        self.assertContains(response, "Universities")
        self.assertContains(response, "Schools")
        self.assertContains(response, "University Administrator")

        filtered = self.client.get(
            reverse("community:forum_list"), {"category": "companies"}
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertTrue(
            all(post.category.slug == "companies" for post in filtered.context["posts"])
        )
