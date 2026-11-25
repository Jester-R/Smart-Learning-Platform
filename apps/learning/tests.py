from decimal import Decimal
import json
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.courses.models import Course, Enrollment

from .models import (
    AttendanceRecord,
    CourseProgress,
    LearningProgress,
    Lesson,
    extract_youtube_video_id,
)


class YouTubeExtractionTests(TestCase):
    """Tests for validating and extracting YouTube video IDs from all supported URL formats."""

    def test_standard_watch_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_watch_url_with_parameters(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&feature=share"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_short_youtu_be_url(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_short_youtu_be_url_with_params(self):
        url = "https://youtu.be/dQw4w9WgXcQ?si=abcdef12345&t=15"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_embed_url(self):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_shorts_url(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_live_stream_url(self):
        url = "https://www.youtube.com/live/dQw4w9WgXcQ?feature=share"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_mobile_youtube_url(self):
        url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_nocookie_embed_url(self):
        url = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_url_without_protocol(self):
        url = "youtu.be/dQw4w9WgXcQ"
        self.assertEqual(extract_youtube_video_id(url), "dQw4w9WgXcQ")

    def test_non_youtube_urls_rejected(self):
        self.assertIsNone(extract_youtube_video_id("https://vimeo.com/123456789"))
        self.assertIsNone(extract_youtube_video_id("https://example.com/video.mp4"))
        self.assertIsNone(extract_youtube_video_id("https://dailymotion.com/video/x7abc"))

    def test_malformed_ids_rejected(self):
        # Too short
        self.assertIsNone(extract_youtube_video_id("https://www.youtube.com/watch?v=short"))
        # Too long
        self.assertIsNone(extract_youtube_video_id("https://www.youtube.com/watch?v=this_id_is_too_long_123"))
        # Invalid characters
        self.assertIsNone(extract_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXc!"))
        # Empty
        self.assertIsNone(extract_youtube_video_id(""))
        self.assertIsNone(extract_youtube_video_id(None))


class LessonModelTests(TestCase):
    """Tests for the Lesson model, YouTube fields, validation, and properties."""

    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(
            email="teacher_model@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Jane",
            last_name="Doe",
        )
        cls.course = Course.objects.create(
            code="PY101",
            title="Python Mastery",
            teacher=cls.teacher,
            description="Learn Python from scratch.",
            status=Course.Status.PUBLISHED,
        )

    def test_lesson_creation_with_valid_youtube_url(self):
        lesson = Lesson.objects.create(
            course=self.course,
            title="Introduction to Functions",
            chapter="Chapter 1: Basics",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            duration_minutes=25,
            order=1,
            is_published=True,
        )
        lesson.refresh_from_db()
        self.assertEqual(lesson.youtube_video_id, "dQw4w9WgXcQ")
        self.assertTrue(lesson.has_youtube)
        self.assertIn("dQw4w9WgXcQ", lesson.youtube_embed_url)
        self.assertEqual(lesson.youtube_watch_url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(lesson.youtube_thumbnail_url, "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg")
        self.assertEqual(lesson.duration, 25)
        self.assertEqual(lesson.duration_display, "25 min")

    def test_duration_display_hours_and_minutes(self):
        lesson = Lesson.objects.create(
            course=self.course,
            title="Deep Dive",
            youtube_url="https://youtu.be/dQw4w9WgXcQ",
            duration_minutes=75,
            order=2,
        )
        self.assertEqual(lesson.duration_display, "1h 15m")

    def test_duration_display_exact_hours(self):
        lesson = Lesson.objects.create(
            course=self.course,
            title="Two Hour Lecture",
            youtube_url="https://youtu.be/dQw4w9WgXcQ",
            duration_minutes=120,
            order=3,
        )
        self.assertEqual(lesson.duration_display, "2h")

    def test_invalid_youtube_url_fails_clean(self):
        lesson = Lesson(
            course=self.course,
            title="Invalid Link Lesson",
            youtube_url="https://vimeo.com/99999",
            order=4,
        )
        with self.assertRaises(ValidationError):
            lesson.full_clean()

    def test_clearing_youtube_url_clears_video_id(self):
        lesson = Lesson.objects.create(
            course=self.course,
            title="Temporary Video",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            order=5,
        )
        self.assertEqual(lesson.youtube_video_id, "dQw4w9WgXcQ")
        lesson.youtube_url = ""
        lesson.save()
        lesson.refresh_from_db()
        self.assertEqual(lesson.youtube_video_id, "")
        self.assertFalse(lesson.has_youtube)


class LearningProgressTests(TestCase):
    """Tests for learning and course progress tracking."""

    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Teacher",
            last_name="One",
        )
        cls.student = User.objects.create_user(
            email="student@example.com",
            password="StrongPass123!",
            first_name="Student",
            last_name="One",
        )
        cls.course = Course.objects.create(
            code="CS101",
            title="Intro to Programming",
            teacher=cls.teacher,
            description="Programming fundamentals.",
            status=Course.Status.PUBLISHED,
        )
        cls.lesson_one = Lesson.objects.create(
            course=cls.course,
            title="Variables",
            chapter="Chapter 1",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            order=1,
            is_published=True,
        )
        cls.lesson_two = Lesson.objects.create(
            course=cls.course,
            title="Loops",
            chapter="Chapter 2",
            youtube_url="https://youtu.be/dQw4w9WgXcQ",
            order=2,
            is_published=True,
        )

    def test_progress_requires_enrollment(self):
        progress = LearningProgress(student=self.student, lesson=self.lesson_one)
        with self.assertRaises(ValidationError):
            progress.full_clean()

    def test_course_progress_recalculates_percentage(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        progress = LearningProgress.objects.create(
            student=self.student, lesson=self.lesson_one
        )
        progress.mark_completed()

        course_progress = CourseProgress.objects.create(
            student=self.student, course=self.course
        )
        result = course_progress.recalculate()
        self.assertEqual(result, Decimal("50"))
        course_progress.refresh_from_db()
        self.assertEqual(course_progress.progress_percent, Decimal("50.00"))

    def test_only_one_progress_record_per_lesson(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        LearningProgress.objects.create(student=self.student, lesson=self.lesson_one)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LearningProgress.objects.create(
                    student=self.student, lesson=self.lesson_one
                )


class YouTubeLessonViewsTests(TestCase):
    """End-to-end tests for teacher and student YouTube video workflows."""

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            email="teacher_flow@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Prof",
            last_name="Smith",
        )
        self.other_teacher = User.objects.create_user(
            email="other_teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Prof",
            last_name="Other",
        )
        self.student = User.objects.create_user(
            email="student_flow@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Alex",
            last_name="Student",
        )
        self.course = Course.objects.create(
            code="DEV101",
            title="Web Development with Django",
            teacher=self.teacher,
            description="Complete full-stack guide.",
            status=Course.Status.PUBLISHED,
        )
        self.lesson_1 = Lesson.objects.create(
            course=self.course,
            title="Getting Started",
            chapter="Module 1: Setup",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            duration_minutes=15,
            order=1,
            is_published=True,
        )
        self.lesson_2 = Lesson.objects.create(
            course=self.course,
            title="Django MVT",
            chapter="Module 1: Setup",
            youtube_url="https://youtu.be/dQw4w9WgXcQ",
            duration_minutes=20,
            order=2,
            is_published=False,  # Draft
        )

    # ----------------- TEACHER WORKFLOW TESTS -----------------

    def test_teacher_can_create_video_lesson(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("learning:lesson_create", kwargs={"slug": self.course.slug}),
            data={
                "title": "Django Views & URLs",
                "chapter": "Module 2: Core",
                "youtube_url": "https://www.youtube.com/shorts/dQw4w9WgXcQ",
                "duration_minutes": 18,
                "order": 3,
                "is_published": True,
                "description": "Learn URL routing.",
            },
        )
        self.assertEqual(response.status_code, 302)
        new_lesson = Lesson.objects.get(title="Django Views & URLs")
        self.assertEqual(new_lesson.youtube_video_id, "dQw4w9WgXcQ")
        self.assertEqual(new_lesson.order, 3)
        self.assertTrue(new_lesson.is_published)

    def test_teacher_can_update_lesson(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("learning:lesson_edit", kwargs={"slug": self.course.slug, "pk": self.lesson_1.pk}),
            data={
                "title": "Getting Started Updated",
                "chapter": "Module 1: Setup",
                "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
                "duration_minutes": 22,
                "order": 1,
                "is_published": True,
                "description": "Updated summary.",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.lesson_1.refresh_from_db()
        self.assertEqual(self.lesson_1.title, "Getting Started Updated")
        self.assertEqual(self.lesson_1.duration_minutes, 22)

    def test_teacher_can_toggle_publish(self):
        self.client.force_login(self.teacher)
        # Toggle lesson_2 from draft (False) to published (True)
        response = self.client.post(
            reverse("learning:lesson_toggle_publish", kwargs={"slug": self.course.slug, "pk": self.lesson_2.pk}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["is_published"])
        self.lesson_2.refresh_from_db()
        self.assertTrue(self.lesson_2.is_published)

    def test_teacher_can_view_video_management_dashboard(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("learning:teacher_videos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "YouTube Video Lessons")
        self.assertContains(response, self.lesson_1.title)

    def test_unauthorized_teacher_cannot_manage_another_teachers_lesson(self):
        self.client.force_login(self.other_teacher)
        response = self.client.post(
            reverse("learning:lesson_edit", kwargs={"slug": self.course.slug, "pk": self.lesson_1.pk}),
            data={"title": "Hacked Title", "order": 1, "youtube_url": "https://youtu.be/dQw4w9WgXcQ"},
        )
        self.assertEqual(response.status_code, 403)

    # ----------------- STUDENT WORKFLOW TESTS -----------------

    def test_enrolled_student_can_watch_published_video_lesson(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("learning:lesson", kwargs={"slug": self.course.slug, "pk": self.lesson_1.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lesson_1.title)
        self.assertContains(response, f"/embed/{self.lesson_1.youtube_video_id}")
        self.assertContains(response, "Mark as Completed")

    def test_student_cannot_access_draft_lesson(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("learning:lesson", kwargs={"slug": self.course.slug, "pk": self.lesson_2.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_unenrolled_student_denied_access(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("learning:lesson", kwargs={"slug": self.course.slug, "pk": self.lesson_1.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_student_mark_lesson_complete_via_ajax(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("learning:mark_complete", kwargs={"slug": self.course.slug, "pk": self.lesson_1.pk}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertTrue(data["is_completed"])
        # Only lesson_1 is published in the course so completed count should be 1 of 1 published
        self.assertEqual(data["completed_count"], 1)

        progress = LearningProgress.objects.get(student=self.student, lesson=self.lesson_1)
        self.assertTrue(progress.is_completed)

        course_progress = CourseProgress.objects.get(student=self.student, course=self.course)
        self.assertEqual(course_progress.progress_percent, Decimal("100.00"))

    # ----------------- YOUTUBE VALIDATION API TESTS -----------------

    def test_youtube_validation_api_valid(self):
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("learning:youtube_validate_api"),
            {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["valid"])
        self.assertEqual(data["video_id"], "dQw4w9WgXcQ")
        self.assertIn("dQw4w9WgXcQ", data["embed_url"])

    def test_youtube_validation_api_invalid(self):
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("learning:youtube_validate_api"),
            {"url": "https://vimeo.com/123456"},
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data["valid"])


class AttendanceViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Tina",
            last_name="Teacher",
        )
        cls.other_teacher = User.objects.create_user(
            email="teacher2@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Tom",
            last_name="Other",
        )
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
        cls.admin = User.objects.create_user(
            email="admin@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
            first_name="Site",
            last_name="Admin",
        )
        cls.course = Course.objects.create(
            code="CS101",
            title="Intro to Programming",
            teacher=cls.teacher,
            description="Programming fundamentals.",
        )
        cls.other_course = Course.objects.create(
            code="CS102",
            title="Data Structures",
            teacher=cls.other_teacher,
            description="Data structures.",
        )

        AttendanceRecord.objects.create(
            student=cls.student,
            course=cls.course,
            date=date(2026, 1, 5),
            status=AttendanceRecord.Status.PRESENT,
            recorded_by=cls.teacher,
        )
        AttendanceRecord.objects.create(
            student=cls.student,
            course=cls.course,
            date=date(2026, 1, 6),
            status=AttendanceRecord.Status.PRESENT,
            recorded_by=cls.teacher,
        )
        AttendanceRecord.objects.create(
            student=cls.student,
            course=cls.course,
            date=date(2026, 1, 7),
            status=AttendanceRecord.Status.LATE,
            recorded_by=cls.teacher,
        )
        AttendanceRecord.objects.create(
            student=cls.student,
            course=cls.course,
            date=date(2026, 1, 8),
            status=AttendanceRecord.Status.ABSENT,
            recorded_by=cls.teacher,
        )
        AttendanceRecord.objects.create(
            student=cls.other_student,
            course=cls.other_course,
            date=date(2026, 1, 5),
            status=AttendanceRecord.Status.ABSENT,
            recorded_by=cls.other_teacher,
        )

    def test_attendance_requires_login(self):
        response = self.client.get(reverse("learning:attendance"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_student_sees_only_own_attendance(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("learning:attendance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My attendance")
        self.assertContains(response, self.course.code)
        self.assertContains(response, "75.0%")
        self.assertNotContains(response, self.other_course.code)
        self.assertNotContains(response, self.other_student.full_name)

    def test_student_sees_status_totals(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("learning:attendance"))

        self.assertEqual(response.context["totals"]["present"], 2)
        self.assertEqual(response.context["totals"]["late"], 1)
        self.assertEqual(response.context["totals"]["absent"], 1)
        self.assertEqual(response.context["totals"]["excused"], 0)
        self.assertEqual(response.context["attendance_rate"], 75.0)
        self.assertEqual(response.context["total_sessions"], 4)

    def test_teacher_sees_attendance_for_own_courses_only(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("learning:attendance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Course attendance")
        self.assertContains(response, self.course.code)
        self.assertContains(response, self.student.full_name)
        self.assertNotContains(response, self.other_course.code)
        self.assertNotContains(response, self.other_student.full_name)

    def test_admin_sees_all_attendance(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("learning:attendance"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.code)
        self.assertContains(response, self.other_course.code)
        self.assertContains(response, self.student.full_name)
        self.assertContains(response, self.other_student.full_name)

    def test_attendance_record_is_unique_per_student_course_and_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AttendanceRecord.objects.create(
                    student=self.student,
                    course=self.course,
                    date=date(2026, 1, 5),
                    status=AttendanceRecord.Status.ABSENT,
                )

    def test_is_present_includes_late_records(self):
        present = AttendanceRecord(
            student=self.student,
            course=self.course,
            date=date(2026, 1, 9),
            status=AttendanceRecord.Status.PRESENT,
        )
        late = AttendanceRecord(
            student=self.student,
            course=self.course,
            date=date(2026, 1, 12),
            status=AttendanceRecord.Status.LATE,
        )
        absent = AttendanceRecord(
            student=self.student,
            course=self.course,
            date=date(2026, 1, 13),
            status=AttendanceRecord.Status.ABSENT,
        )

        self.assertTrue(present.is_present)
        self.assertTrue(late.is_present)
        self.assertFalse(absent.is_present)

    def test_attendance_export_requires_login(self):
        response = self.client.get(reverse("learning:attendance_export_pdf"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_student_can_export_own_attendance_pdf(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("learning:attendance_export_pdf"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("my-attendance", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 1000)

    def test_teacher_export_uses_course_attendance_filename(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("learning:attendance_export_pdf"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("course-attendance", response["Content-Disposition"])

    def test_admin_export_uses_all_attendance_filename(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("learning:attendance_export_pdf"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("all-attendance", response["Content-Disposition"])

    def test_export_handles_users_without_attendance(self):
        self.client.force_login(self.other_student)
        AttendanceRecord.objects.filter(student=self.other_student).delete()

        response = self.client.get(reverse("learning:attendance_export_pdf"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_attendance_page_shows_export_button(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("learning:attendance"))

        self.assertContains(
            response, reverse("learning:attendance_export_pdf")
        )
        self.assertContains(response, "Export PDF")

