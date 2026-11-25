from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.analytics.models import ActivityLog, GradeAuditLog
from apps.assessments.models import Assignment, Grade, Submission
from apps.assessments.services import calculate_gpa, weighted_percentage
from apps.courses.models import Course, Enrollment
from apps.learning.models import AttendanceRecord

from .models import AcademicCalendar, ClassSchedule, ExamSchedule


class AcademicPhaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0, skip_user_assignment=True)
        cls.teacher = User.objects.create_user(
            email="phase3-teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Phase3",
            last_name="Teacher",
        )
        cls.student = User.objects.create_user(
            email="phase3-student@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Phase3",
            last_name="Student",
        )
        cls.company = User.objects.create_user(
            email="phase3-company@example.com",
            password="StrongPass123!",
            role=User.Role.COMPANY,
            first_name="Phase3",
            last_name="Company",
        )
        cls.course = Course.objects.create(
            code="PHASE301",
            title="Academic Operations",
            teacher=cls.teacher,
            description="Phase 3 verification course.",
        )
        Enrollment.objects.create(student=cls.student, course=cls.course)

    def test_student_can_view_timetable_and_company_cannot(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("academic:timetable")).status_code, 200)

        self.client.force_login(self.company)
        self.assertEqual(self.client.get(reverse("academic:timetable")).status_code, 403)

    def test_teacher_can_create_schedule(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("academic:schedule_create"),
            {
                "course": self.course.pk,
                "day_of_week": ClassSchedule.Weekday.MONDAY,
                "start_time": "09:00",
                "end_time": "10:30",
                "room": "Room 101",
                "notes": "Weekly lecture",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        schedule = ClassSchedule.objects.get(course=self.course)
        self.assertEqual(schedule.room, "Room 101")
        self.assertTrue(schedule.is_active)

    def test_calendar_event_can_be_created(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("academic:calendar_event_create"),
            {
                "title": "Midterm Week",
                "event_type": AcademicCalendar.EventType.EXAM,
                "start_date": "2026-12-01",
                "end_date": "2026-12-05",
                "description": "Midterm examinations.",
                "is_published": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(AcademicCalendar.objects.filter(title="Midterm Week").exists())

    def test_weighted_average_and_gpa(self):
        grades = [
            Grade(
                student=self.student,
                course=self.course,
                component=Grade.Component.QUIZ,
                title="Quiz 1",
                score=Decimal("90"),
                max_score=Decimal("100"),
                weight=Decimal("30"),
                graded_by=self.teacher,
            ),
            Grade(
                student=self.student,
                course=self.course,
                component=Grade.Component.ASSIGNMENT,
                title="Assignment 1",
                score=Decimal("80"),
                max_score=Decimal("100"),
                weight=Decimal("70"),
                graded_by=self.teacher,
            ),
        ]

        self.assertAlmostEqual(float(weighted_percentage(grades)), 83.0, places=2)
        self.assertEqual(calculate_gpa(grades), Decimal("3.30"))

    def test_official_grade_entry_creates_audit_log(self):
        assignment = Assignment.objects.create(
            course=self.course,
            title="Exercise 1",
            description="Submit the exercise.",
            max_points=Decimal("10"),
            created_by=self.teacher,
            is_published=True,
        )
        submission = Submission.objects.create(
            assignment=assignment,
            student=self.student,
            text_response="Completed.",
        )
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("assessments:submission_grade", args=[submission.pk]),
            {
                "score": "8.00",
                "feedback": "Good work",
                "status": Submission.Status.GRADED,
                "reason": "Official entry",
            },
        )

        self.assertEqual(response.status_code, 302)
        grade = Grade.objects.get(
            student=self.student, course=self.course, title=assignment.title
        )
        audit = GradeAuditLog.objects.get(grade=grade)
        self.assertEqual(audit.new_score, Decimal("8.00"))
        self.assertEqual(audit.reason, "Official entry")

    def test_teacher_can_record_attendance_with_audit(self):
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("learning:attendance_record"),
            {
                "student": self.student.pk,
                "course": self.course.pk,
                "date": "2026-11-20",
                "status": AttendanceRecord.Status.PRESENT,
                "remarks": "On time",
            },
        )

        self.assertEqual(response.status_code, 302)
        record = AttendanceRecord.objects.get(student=self.student, course=self.course)
        self.assertEqual(record.date, date(2026, 11, 20))
        self.assertEqual(record.recorded_by, self.teacher)
        log = ActivityLog.objects.get(model_name="AttendanceRecord")
        self.assertTrue(log.metadata["created"])

    def test_student_cannot_record_attendance(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("learning:attendance_record"),
            {
                "student": self.student.pk,
                "course": self.course.pk,
                "date": "2026-11-20",
                "status": AttendanceRecord.Status.PRESENT,
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_exam_schedule_is_grouped_across_many_days(self):
        Course.objects.filter(pk=self.course.pk).update(status=Course.Status.PUBLISHED)
        call_command("seed_course_content", verbosity=0)
        call_command("seed_exam_schedule", verbosity=0)
        first_count = ExamSchedule.objects.count()
        call_command("seed_exam_schedule", verbosity=0)
        self.assertEqual(ExamSchedule.objects.count(), first_count)
        self.assertGreaterEqual(first_count, 30)
        exam_dates = {
            timezone.localtime(item.start_at).date() for item in ExamSchedule.objects.all()
        }
        self.assertGreaterEqual(len(exam_dates), 10)

        admin = User.objects.create_superuser(
            email="exam-admin@example.com",
            password="StrongPass123!",
            first_name="Exam",
            last_name="Admin",
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("academic:exam_schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["days"]), 12)
        self.assertContains(response, "exams across")
        self.assertContains(response, "Monday,")
