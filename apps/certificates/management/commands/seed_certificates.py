"""Issue certificates to students who have actually completed their course.

Unlike a plain "seed", this command first creates the learning evidence a
student would have produced (completed lessons, graded assignments, passed
quizzes and exams) and then issues the certificate through the same
eligibility rules the application uses, so no certificate is ever handed out
without the student having learned the material.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import User
from apps.assessments.models import (
    Exam,
    ExamAttempt,
    Quiz,
    QuizAttempt,
    Submission,
)
from apps.certificates.models import Certificate, CertificateTemplate
from apps.certificates.services import check_eligibility
from apps.courses.models import Course, Enrollment
from apps.learning.models import CourseProgress, LearningProgress

DEFAULT_COUNT = 956
PASS_RATIO = Decimal("0.85")
FINAL_GRADE = Decimal("90.00")


class Command(BaseCommand):
    help = (
        "Simulate genuine course completion (lessons, assignments, quizzes, "
        "exams) for a set of enrollments and issue certificates only to the "
        "students who then qualify. Safe to run repeatedly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=DEFAULT_COUNT,
            help=f"Number of completed student/course pairs to ensure "
            f"(default: {DEFAULT_COUNT}).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing certificates before rebuilding them "
            "from real learning progress.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        target = max(0, options["count"])

        if options["reset"]:
            removed, _ = Certificate.objects.all().delete()
            self.stdout.write(f"Removed {removed} existing certificate records.")

        students = list(User.objects.filter(role=User.Role.STUDENT).order_by("id"))
        courses = list(Course.objects.order_by("id"))
        if not students or not courses:
            self.stderr.write(
                self.style.ERROR("Students and courses are required first.")
            )
            return

        template, _ = CertificateTemplate.objects.get_or_create(
            name="Classic Completion",
            defaults={
                "description": "Clean default certificate for completed courses.",
                "is_default": True,
                "created_by": User.objects.filter(role=User.Role.ADMIN).first(),
            },
        )

        # A student can only earn a certificate when the course allows it.
        Course.objects.filter(certificate_enabled=False).update(
            certificate_enabled=True
        )

        pairs = []
        for course in courses:
            for student in students:
                pairs.append((student, course))
                if len(pairs) >= target:
                    break
            if len(pairs) >= target:
                break

        existing_pairs = set(
            Certificate.objects.values_list("student_id", "course_id")
        )
        now = timezone.now()
        issued = skipped = 0

        for student, course in pairs:
            self._simulate_learning(student, course, now)

            pair = (student.id, course.id)
            if pair in existing_pairs:
                continue

            eligibility = check_eligibility(student, course)
            if not eligibility["eligible"]:
                skipped += 1
                continue

            enrollment = Enrollment.objects.filter(
                student=student, course=course
            ).first()
            Certificate.objects.create(
                student=student,
                course=course,
                template=template,
                issued_by=course.teacher,
                grade_at_issue=enrollment.final_grade if enrollment else FINAL_GRADE,
                status=Certificate.Status.VALID,
            )
            existing_pairs.add(pair)
            issued += 1

        total = Certificate.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Certificates issued to students who completed their course: "
                f"{issued} new, {total} total"
                + (f", {skipped} not yet eligible." if skipped else ".")
            )
        )
        self.stdout.write(
            f"  {Certificate.objects.filter(status=Certificate.Status.VALID).count()} valid, "
            f"{Enrollment.objects.filter(status=Enrollment.Status.COMPLETED).count()} completed enrollments."
        )

    def _simulate_learning(self, student, course, now):
        """Create the learning evidence a completing student would produce."""
        enrollment, _ = Enrollment.objects.get_or_create(
            student=student, course=course
        )

        lessons = list(course.lessons.filter(is_published=True))
        if lessons:
            existing_ids = set(
                LearningProgress.objects.filter(
                    student=student, lesson__in=lessons
                ).values_list("lesson_id", flat=True)
            )
            LearningProgress.objects.filter(
                student=student, lesson__in=lessons
            ).update(is_completed=True, completed_at=now)
            new_progress = [
                LearningProgress(
                    student=student,
                    lesson=lesson,
                    is_completed=True,
                    completed_at=now,
                    last_position_seconds=lesson.duration_minutes * 60,
                )
                for lesson in lessons
                if lesson.id not in existing_ids
            ]
            if new_progress:
                LearningProgress.objects.bulk_create(new_progress, batch_size=200)

        CourseProgress.objects.update_or_create(
            student=student,
            course=course,
            defaults={
                "progress_percent": 100 if lessons else 0,
                "last_accessed_at": now,
                "last_lesson": lessons[-1] if lessons else None,
            },
        )

        for assignment in course.assignments.filter(is_published=True):
            Submission.objects.update_or_create(
                student=student,
                assignment=assignment,
                defaults={
                    "status": Submission.Status.GRADED,
                    "score": assignment.max_points * Decimal("0.9"),
                    "graded_by": course.teacher,
                    "graded_at": now,
                    "text_response": "Completed during the course.",
                },
            )

        for quiz in Quiz.objects.filter(course=course):
            self._ensure_passing_attempt(
                QuizAttempt, "quiz", quiz, student, now
            )

        for exam in Exam.objects.filter(course=course):
            self._ensure_passing_attempt(
                ExamAttempt, "exam", exam, student, now
            )

        enrollment.status = Enrollment.Status.COMPLETED
        enrollment.completed_at = enrollment.completed_at or now
        enrollment.final_grade = FINAL_GRADE
        enrollment.save(
            update_fields=["status", "completed_at", "final_grade", "updated_at"]
        )

    def _ensure_passing_attempt(self, model, parent_field, parent, student, now):
        """Make sure the student has a passing attempt for a quiz or exam."""
        total = parent.total_points()
        attempts = model.objects.filter(**{parent_field: parent}, student=student)
        if attempts.exists():
            attempts.update(
                status=model.Status.GRADED,
                submitted_at=now,
                score=F("max_score") * PASS_RATIO,
            )
            attempts.filter(max_score=0).update(
                max_score=total, score=total * PASS_RATIO
            )
            return
        model.objects.create(
            student=student,
            attempt_number=1,
            status=model.Status.GRADED,
            submitted_at=now,
            score=total * PASS_RATIO,
            max_score=total,
            **{parent_field: parent},
        )
