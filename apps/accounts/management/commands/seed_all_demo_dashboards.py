from datetime import time as datetime_time, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.academic.models import AcademicCalendar, ClassSchedule, ExamSchedule
from apps.accounts.models import StudentProfile, TeacherProfile, User
from apps.analytics.models import ActivityLog
from apps.assessments.models import Assignment, Grade, Submission
from apps.careers.models import (
    ApplicationMessage,
    CVDocument,
    CompanyProfile,
    Job,
    JobApplication,
)
from apps.certificates.models import Certificate, CertificateTemplate
from apps.core.models import Department, Faculty, Role, University, UserRole
from apps.courses.models import Category, Course, Enrollment
from apps.learning.models import AttendanceRecord, CourseProgress, LearningProgress, Lesson
from apps.live.models import LiveSession
from apps.notifications.models import Notification

DEMO_EMAILS = {
    "admin": "admin@smartlearning.local",
    "teacher": "teacher@smartlearning.local",
    "student": "student@smartlearning.local",
    "student_generated": "student0001@smartlearning.local",
    "teacher_generated": "teacher0001@smartlearning.local",
    "company": "company0001@smartlearning.local",
    "interview_company": "company0008@smartlearning.local",
    "university": "university0001@smartlearning.local",
    "school": "school0001@smartlearning.local",
}


class Command(BaseCommand):
    help = "Populate data for every named demo account so each dashboard has content."

    @transaction.atomic
    def handle(self, *args, **options):
        users = {
            key: User.objects.get(email=email) for key, email in DEMO_EMAILS.items()
        }
        category, _ = Category.objects.get_or_create(
            name="Programming",
            defaults={"description": "Programming courses and resources."},
        )

        template, _ = CertificateTemplate.objects.get_or_create(
            name="Classic Completion",
            defaults={
                "description": "Clean default certificate for completed courses.",
                "is_default": True,
                "created_by": users["admin"],
            },
        )

        teacher_courses = self._ensure_teacher_data(
            users["teacher"], "DEMO-TCH", "Teacher Demo", category, template
        )
        school_courses = self._ensure_teacher_data(
            users["school"], "DEMO-SCH", "School Demo", category, template
        )

        existing_courses = list(
            Course.objects.filter(status=Course.Status.PUBLISHED).order_by("id")[:8]
        )
        student_courses = []
        for course in teacher_courses[:2] + school_courses[:2] + existing_courses:
            if course not in student_courses:
                student_courses.append(course)
        student_courses = student_courses[:5]

        self._ensure_student_data(
            users["student"], student_courses, users["teacher"], template
        )
        self._ensure_live_sessions(teacher_courses, school_courses)
        self._ensure_notification(
            users["teacher"],
            "Your demo courses are ready",
            "Review your demo courses, assignments, and recent submissions.",
            "/dashboard/",
            Notification.Kind.SUCCESS,
        )
        self._ensure_notification(
            users["school"],
            "School dashboard data is ready",
            "Your demo courses and student submissions are available.",
            "/dashboard/",
            Notification.Kind.SUCCESS,
        )
        self._ensure_notification(
            users["student_generated"],
            "Your demo learning data is ready",
            "Continue your enrolled courses and check your progress.",
            "/dashboard/",
            Notification.Kind.INFO,
        )
        self._ensure_notification(
            users["teacher_generated"],
            "Your demo courses are ready",
            "Open your dashboard to review courses and submissions.",
            "/dashboard/",
            Notification.Kind.SUCCESS,
        )

        cv = self._ensure_cv(users["student"])
        self._ensure_company_data(users["company"], users["student"], cv, "PPD")
        self._ensure_company_data(
            users["interview_company"], users["student"], cv, "FSA"
        )
        self._ensure_university_data(users["university"], users["teacher"])
        self._ensure_activity(users["admin"])

        self.stdout.write(self.style.SUCCESS("All demo dashboard data is ready."))
        self.stdout.write(f"  Teacher courses: {len(teacher_courses)}")
        self.stdout.write(f"  School courses: {len(school_courses)}")
        self.stdout.write(f"  Student courses: {len(student_courses)}")
        self.stdout.write(
            "  Company applications: "
            f"{JobApplication.objects.filter(applicant=users['student']).count()}"
        )
        self.stdout.write(
            f"  University schedules: {ClassSchedule.objects.filter(university__isnull=False).count()}"
        )

    def _ensure_profile(self, user, kind):
        if kind == "student":
            StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    "program": "BS Information Technology",
                    "year_level": StudentProfile.YearLevel.SECOND,
                    "section": "A",
                },
            )
        else:
            TeacherProfile.objects.get_or_create(
                user=user,
                defaults={
                    "department": "Information Technology",
                    "specialization": "Web Development",
                    "qualification": "Master's degree",
                    "office_location": "IT Faculty Room",
                },
            )

    def _ensure_teacher_data(self, teacher, code_prefix, title_prefix, category, template):
        self._ensure_profile(teacher, "teacher")
        courses = []
        for index in range(1, 4):
            code = f"{code_prefix}-{index:02d}"
            course, _ = Course.objects.get_or_create(
                code=code,
                defaults={
                    "title": f"{title_prefix} Course {index}",
                    "slug": f"{code.lower()}-{title_prefix.lower().replace(' ', '-')}-course-{index}",
                    "category": category,
                    "teacher": teacher,
                    "description": (
                        f"{title_prefix} Course {index} demonstrates a populated "
                        "teacher dashboard with lessons, assignments, and submissions."
                    ),
                    "objectives": "Understand key concepts\nApply them in practice",
                    "status": Course.Status.PUBLISHED,
                    "difficulty": Course.Difficulty.BEGINNER,
                    "duration_hours": 12 + index * 2,
                    "certificate_enabled": True,
                    "published_at": timezone.now() - timedelta(days=30 - index),
                },
            )
            courses.append(course)
            self._ensure_lessons(course, index)
            self._ensure_teacher_submissions(course, teacher, template)
        return courses

    def _ensure_lessons(self, course, count):
        for order in range(1, count + 1):
            lesson, created = Lesson.objects.get_or_create(
                course=course,
                order=order,
                defaults={
                    "title": f"Demo lesson {order}",
                    "description": f"Lesson {order} for {course.code}.",
                    "content": f"Study notes for demo lesson {order}.",
                    "chapter": "Introduction",
                    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "duration_minutes": 18 + order * 4,
                    "is_published": True,
                },
            )
            if not created and not lesson.youtube_video_id:
                lesson.youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                lesson.is_published = True
                lesson.save()

    def _ensure_teacher_submissions(self, course, teacher, template):
        assignment, _ = Assignment.objects.get_or_create(
            course=course,
            title="Demo assignment",
            defaults={
                "description": f"Demonstration assignment for {course.code}.",
                "instructions": "Review the lesson and submit a short response.",
                "due_at": timezone.now() + timedelta(days=7),
                "max_points": Decimal("100"),
                "allow_late_submission": True,
                "is_published": True,
                "created_by": teacher,
            },
        )
        for email, status, score in (
            (DEMO_EMAILS["student"], Submission.Status.GRADED, Decimal("92")),
            (DEMO_EMAILS["student_generated"], Submission.Status.SUBMITTED, None),
        ):
            student = User.objects.get(email=email)
            Enrollment.objects.get_or_create(
                student=student,
                course=course,
                defaults={"status": Enrollment.Status.ACTIVE},
            )
            Submission.objects.update_or_create(
                assignment=assignment,
                student=student,
                defaults={
                    "text_response": f"Demo response for {assignment.title}.",
                    "status": status,
                    "score": score,
                    "feedback": "Good work." if score is not None else "",
                    "graded_by": teacher if score is not None else None,
                    "graded_at": timezone.now() if score is not None else None,
                },
            )

    def _ensure_student_data(self, student, courses, teacher, template):
        self._ensure_profile(student, "student")
        for index, course in enumerate(courses):
            status = (
                Enrollment.Status.COMPLETED
                if index == len(courses) - 1
                else Enrollment.Status.ACTIVE
            )
            Enrollment.objects.get_or_create(
                student=student,
                course=course,
                defaults={"status": status},
            )
            CourseProgress.objects.update_or_create(
                student=student,
                course=course,
                defaults={
                    "progress_percent": Decimal(35 + index * 12),
                    "last_accessed_at": timezone.now() - timedelta(hours=index),
                },
            )
            lesson = course.lessons.filter(is_published=True).order_by("order").first()
            if lesson:
                LearningProgress.objects.update_or_create(
                    student=student,
                    lesson=lesson,
                    defaults={
                        "is_completed": index % 2 == 0,
                        "completed_at": timezone.now() if index % 2 == 0 else None,
                        "last_position_seconds": 120,
                    },
                )
            Grade.objects.update_or_create(
                student=student,
                course=course,
                component=Grade.Component.OVERALL,
                title="Course performance",
                defaults={
                    "score": Decimal(82 + index * 2),
                    "max_score": Decimal("100"),
                    "weight": Decimal("100"),
                    "feedback": "Solid progress.",
                    "graded_by": course.teacher,
                },
            )
            AttendanceRecord.objects.get_or_create(
                student=student,
                course=course,
                date=timezone.localdate() - timedelta(days=1),
                defaults={
                    "status": AttendanceRecord.Status.PRESENT,
                    "recorded_by": course.teacher,
                },
            )
            Certificate.objects.get_or_create(
                student=student,
                course=course,
                defaults={
                    "template": template,
                    "grade_at_issue": Decimal("90"),
                    "issued_by": course.teacher or teacher,
                    "status": Certificate.Status.VALID,
                    "issued_at": timezone.now() - timedelta(days=10),
                },
            )

    def _ensure_cv(self, student):
        cv, _ = CVDocument.objects.get_or_create(
            student=student,
            title="Demo CV",
            defaults={
                "file": ContentFile(
                    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF",
                    name="demo-student-cv.pdf",
                )
            },
        )
        return cv

    def _ensure_company_data(self, company_user, student, cv, code_prefix):
        company, _ = CompanyProfile.objects.get_or_create(
            user=company_user,
            defaults={
                "company_name": company_user.full_name,
                "description": "Demo employer with published jobs and interviews.",
                "contact_email": company_user.email,
                "is_approved": True,
            },
        )
        jobs = list(
            Job.objects.filter(company=company, status=Job.Status.PUBLISHED).order_by("id")[:3]
        )
        if not jobs:
            for index in range(1, 4):
                job, _ = Job.objects.get_or_create(
                    company=company,
                    title=f"{code_prefix} Demo Role {index}",
                    defaults={
                        "description": "Demo role for the company dashboard.",
                        "responsibilities": "Collaborate with the product team.",
                        "requirements": "Problem solving and communication skills.",
                        "location": "Phnom Penh",
                        "job_type": Job.JobType.FULL_TIME,
                        "salary_min": 600,
                        "salary_max": 1200,
                        "application_deadline": timezone.now() + timedelta(days=30),
                        "status": Job.Status.PUBLISHED,
                        "is_approved": True,
                    },
                )
                jobs.append(job)

        statuses = [
            JobApplication.Status.APPLIED,
            JobApplication.Status.REVIEWING,
            JobApplication.Status.SHORTLISTED,
        ]
        for index, job in enumerate(jobs):
            application, _ = JobApplication.objects.get_or_create(
                job=job,
                applicant=student,
                defaults={
                    "cv_document": cv,
                    "cover_letter": f"Demo application for {job.title}.",
                    "status": statuses[index % len(statuses)],
                },
            )
            ApplicationMessage.objects.get_or_create(
                application=application,
                sender=student,
                body=f"Hello, I am interested in the {job.title} role.",
            )
            ApplicationMessage.objects.get_or_create(
                application=application,
                sender=company_user,
                body=f"Thanks for applying. Let us schedule an interview for {job.title}.",
            )
        self._ensure_notification(
            company_user,
            "New demo applications",
            "Review your demo candidates and continue the interview conversations.",
            "/careers/applications/all/",
            Notification.Kind.INFO,
        )

    def _ensure_university_data(self, admin, teacher):
        university = University.objects.filter(email_domain="smartlearning.local").first()
        if university is None:
            university = University.objects.filter(is_active=True).order_by("id").first()
        if university is None:
            university, _ = University.objects.get_or_create(
                code="demo-university",
                defaults={
                    "name": "Smart Learning Demo University",
                    "short_name": "SLDU",
                    "email_domain": "smartlearning.local",
                },
            )

        role, _ = Role.objects.get_or_create(
            code="university_admin",
            defaults={"name": "University Administrator", "level": 50},
        )
        UserRole.objects.update_or_create(
            user=admin,
            role=role,
            defaults={"university": university, "is_primary": True},
        )

        faculty, _ = Faculty.objects.get_or_create(
            university=university,
            code="demo-fit",
            defaults={"name": "Faculty of Information Technology"},
        )
        Department.objects.get_or_create(
            faculty=faculty,
            code="demo-cs",
            defaults={"name": "Department of Computer Science"},
        )

        courses = list(
            Course.objects.filter(status=Course.Status.PUBLISHED).order_by("id")[:4]
        )
        for index, course in enumerate(courses):
            ClassSchedule.objects.update_or_create(
                course=course,
                day_of_week=index % 5,
                start_time=datetime_time(8 + index, 0),
                defaults={
                    "lecturer": teacher,
                    "university": university,
                    "end_time": datetime_time(10 + index, 0),
                    "room": f"Room {index + 1}",
                    "is_active": True,
                },
            )
            ExamSchedule.objects.get_or_create(
                course=course,
                title="Demo Midterm Examination",
                defaults={
                    "start_at": timezone.now() + timedelta(days=14 + index),
                    "end_at": timezone.now() + timedelta(days=14 + index, hours=2),
                    "venue": f"Exam Hall {index + 1}",
                    "is_published": True,
                },
            )

        for index, title in enumerate(
            ["Semester registration", "Midterm break", "Final project deadline"]
        ):
            start = timezone.localdate() + timedelta(days=7 + index * 10)
            AcademicCalendar.objects.get_or_create(
                university=university,
                title=f"Demo: {title}",
                defaults={
                    "event_type": AcademicCalendar.EventType.REGISTRATION
                    if index == 0
                    else AcademicCalendar.EventType.DEADLINE,
                    "start_date": start,
                    "end_date": start + timedelta(days=2),
                    "description": f"Demo calendar event: {title}.",
                    "is_published": True,
                },
            )
        self._ensure_notification(
            admin,
            "University dashboard data is ready",
            "Your faculties, schedules, calendar events, and exams are available.",
            "/dashboard/",
            Notification.Kind.SUCCESS,
        )

    def _ensure_notification(self, user, title, message, link, kind):
        Notification.objects.get_or_create(
            recipient=user,
            title=title,
            defaults={"message": message, "link": link, "kind": kind, "is_read": False},
        )

    def _ensure_activity(self, admin):
        for index, action in enumerate(
            [
                ActivityLog.Action.LOGIN,
                ActivityLog.Action.CREATE,
                ActivityLog.Action.GRADE,
                ActivityLog.Action.CERTIFICATE,
            ]
        ):
            ActivityLog.objects.get_or_create(
                user=admin,
                action=action,
                model_name="User",
                object_id=admin.pk,
                description=f"Demo admin activity {index + 1}.",
            )

    def _ensure_live_sessions(self, teacher_courses, school_courses):
        now = timezone.now()
        youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        plans = [
            (
                teacher_courses[0],
                "Live: Course Q&A",
                now - timedelta(minutes=20),
                now + timedelta(minutes=40),
                LiveSession.Status.LIVE,
            ),
            (
                teacher_courses[1],
                "Live: Building Your First Project",
                now + timedelta(days=1),
                now + timedelta(days=1, hours=2),
                LiveSession.Status.SCHEDULED,
            ),
            (
                school_courses[0],
                "Live: Introduction to Programming",
                now + timedelta(days=2),
                now + timedelta(days=2, hours=2),
                LiveSession.Status.SCHEDULED,
            ),
            (
                school_courses[1],
                "Replay: Design Fundamentals",
                now - timedelta(days=3, hours=2),
                now - timedelta(days=3),
                LiveSession.Status.ENDED,
            ),
        ]
        for course, title, starts_at, ends_at, status in plans:
            LiveSession.objects.get_or_create(
                course=course,
                title=title,
                defaults={
                    "teacher": course.teacher,
                    "description": f"Demo live session for {course.code}.",
                    "youtube_url": youtube_url,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "status": status,
                    "is_published": True,
                },
            )
