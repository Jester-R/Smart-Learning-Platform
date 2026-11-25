"""Populate the platform with demo users, courses, announcements, and certificates."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import StudentProfile, TeacherProfile, User
from apps.assessments.models import Assignment, Submission
from apps.certificates.models import Certificate, CertificateTemplate
from apps.courses.models import Category, Course, Enrollment
from apps.learning.models import AttendanceRecord
from apps.notifications.models import Announcement, Notification

STUDENT_TARGET = 920
TEACHER_TARGET = 96
ANNOUNCEMENT_TARGET = 6
NOTIFICATION_TARGET = 43
COURSE_TARGET = 89
CERTIFICATE_TARGET = 560
SUBMISSIONS_PER_ASSIGNMENT = 12
ATTENDANCE_SESSIONS = 10
ENROLLMENTS_PER_STUDENT = 5

STUDENT_PASSWORD = "Student@12345"
TEACHER_PASSWORD = "Teacher@12345"

FIRST_NAMES = [
    "Aaliyah", "Aaron", "Abigail", "Adrian", "Aisha", "Alejandro", "Alexa",
    "Amara", "Andre", "Angela", "Aria", "Benjamin", "Bianca", "Caleb",
    "Camila", "Carlos", "Carmen", "Chloe", "Daniel", "Daniella", "David",
    "Diego", "Elena", "Elijah", "Ella", "Emmanuel", "Ethan", "Fatima",
    "Gabriel", "Grace", "Hannah", "Haruto", "Isaac", "Isabella", "Jasmine",
    "Javier", "Joanna", "John", "Jose", "Joshua", "Julia", "Kai", "Karen",
    "Kevin", "Laila", "Leo", "Liam", "Lucas", "Lucia", "Maria", "Mark",
    "Mateo", "Maya", "Miguel", "Mila", "Nathan", "Nia", "Noah", "Olivia",
    "Omar", "Paolo", "Patricia", "Paul", "Rafael", "Rebecca", "Riley",
    "Robert", "Samantha", "Samuel", "Sara", "Sofia", "Sophia", "Teresa",
    "Thomas", "Valentina", "Victor", "Victoria", "William", "Zara", "Zoe",
]

LAST_NAMES = [
    "Abad", "Aguilar", "Alvarez", "Aquino", "Bautista", "Bernardo", "Bonifacio",
    "Castro", "Cruz", "Dela Cruz", "Diaz", "Domingo", "Estrada", "Flores",
    "Garcia", "Gonzales", "Hernandez", "Jimenez", "Lopez", "Lorenzo", "Magsaysay",
    "Manalo", "Mendoza", "Mercado", "Nolasco", "Ocampo", "Pascual", "Perez",
    "Quinto", "Ramos", "Reyes", "Rivera", "Rizal", "Rodriguez", "Romero",
    "Salazar", "Sanchez", "Santiago", "Santos", "Sison", "Soriano", "Suarez",
    "Tan", "Torres", "Vargas", "Velasco", "Villanueva", "Yap", "Zamora",
]

SUBJECTS = [
    "Python Programming", "Web Development", "Data Structures", "Algorithms",
    "Database Systems", "Computer Networking", "Cybersecurity", "Cloud Computing",
    "Machine Learning", "Data Science", "Statistics", "Calculus",
    "Linear Algebra", "Discrete Mathematics", "Software Engineering",
    "Mobile Development", "Game Development", "UI/UX Design",
    "Digital Marketing", "Business Analytics", "Project Management",
    "English Communication", "Academic Writing", "Physics", "Chemistry",
    "Biology", "Economics", "Accounting", "Multimedia Arts", "Information Systems",
]

PROGRAMS = [
    "BS Information Technology",
    "BS Computer Science",
    "BS Information Systems",
    "BS Business Administration",
    "BS Accountancy",
    "BS Psychology",
]

SECTIONS = ["A", "B", "C", "D"]

DEPARTMENTS = [
    "Information Technology",
    "Computer Science",
    "Business",
    "Mathematics",
    "Languages",
    "Science",
]


class Command(BaseCommand):
    help = (
        "Create demo data so the administrator dashboard shows a populated platform: "
        "920 students, 96 teachers, 89 courses, 6 announcements, 43 notifications, "
        "560 certificates, assignments with student submissions, and attendance "
        "records. Safe to run more than once."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Only print the final summary.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        quiet = options["quiet"]
        self.stdout.write("Seeding administrator dashboard demo data...")

        student_users = self._ensure_users(
            role=User.Role.STUDENT,
            target=STUDENT_TARGET,
            prefix="student",
            password=STUDENT_PASSWORD,
            profile="student",
            quiet=quiet,
        )
        teacher_users = self._ensure_users(
            role=User.Role.TEACHER,
            target=TEACHER_TARGET,
            prefix="teacher",
            password=TEACHER_PASSWORD,
            profile="teacher",
            quiet=quiet,
        )
        self._ensure_courses(quiet=quiet)
        self._ensure_announcements(quiet=quiet)
        self._ensure_notifications(quiet=quiet)
        self._ensure_certificates_and_enrollments(quiet=quiet)
        self._ensure_assignments_and_submissions(quiet=quiet)
        self._ensure_attendance(quiet=quiet)

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write(
            "  Users:          "
            f"{User.objects.filter(role=User.Role.STUDENT).count()} students, "
            f"{User.objects.filter(role=User.Role.TEACHER).count()} teachers"
        )
        self.stdout.write(f"  Courses:        {Course.objects.count()}")
        self.stdout.write(f"  Announcements:  {Announcement.objects.count()}")
        self.stdout.write(f"  Notifications:  {Notification.objects.count()}")
        self.stdout.write(f"  Certificates:   {Certificate.objects.count()}")
        self.stdout.write(f"  Enrollments:    {Enrollment.objects.count()}")
        self.stdout.write(f"  Assignments:    {Assignment.objects.count()}")
        self.stdout.write(f"  Submissions:    {Submission.objects.count()}")
        self.stdout.write(f"  Attendance:     {AttendanceRecord.objects.count()}")
        self.stdout.write("")
        self.stdout.write("Login credentials for the generated accounts:")
        self.stdout.write(f"  Students: {STUDENT_PASSWORD}")
        self.stdout.write(f"  Teachers: {TEACHER_PASSWORD}")

    def _ensure_users(self, role, target, prefix, password, profile, quiet):
        current = User.objects.filter(role=role).count()
        needed = max(0, target - current)
        if needed == 0:
            if not quiet:
                self.stdout.write(
                    f"  {role.title()}s already at {current}; nothing to add."
                )
            return list(User.objects.filter(role=role).order_by("id"))

        existing_emails = set(User.objects.values_list("email", flat=True))
        hashed_password = make_password(password)
        now = timezone.now()
        users = []
        sequence = 1

        while len(users) < needed:
            email = f"{prefix}{sequence:04d}@smartlearning.local"
            sequence += 1
            if email in existing_emails:
                continue

            index = len(users)
            first_name = FIRST_NAMES[index % len(FIRST_NAMES)]
            last_name = LAST_NAMES[(index * 7) % len(LAST_NAMES)]
            joined = now - timedelta(days=(index % 240) + 1, hours=(index * 5) % 24)

            users.append(
                User(
                    email=email,
                    password=hashed_password,
                    role=role,
                    first_name=first_name,
                    last_name=last_name,
                    is_verified=True,
                    date_joined=joined,
                )
            )

        User.objects.bulk_create(users, batch_size=500)
        created = list(
            User.objects.filter(email__in=[user.email for user in users]).order_by("id")
        )

        if profile == "student":
            rows = []
            for index, user in enumerate(created):
                rows.append(
                    StudentProfile(
                        user=user,
                        program=PROGRAMS[index % len(PROGRAMS)],
                        year_level=(index % 4) + 1,
                        section=SECTIONS[index % len(SECTIONS)],
                        enrollment_date=user.date_joined.date(),
                    )
                )
            StudentProfile.objects.bulk_create(rows, batch_size=500, ignore_conflicts=True)
        else:
            rows = []
            for index, user in enumerate(created):
                department = DEPARTMENTS[index % len(DEPARTMENTS)]
                rows.append(
                    TeacherProfile(
                        user=user,
                        department=department,
                        specialization=SUBJECTS[index % len(SUBJECTS)],
                        qualification="Master's degree",
                        office_location=f"{department} Faculty Room",
                    )
                )
            TeacherProfile.objects.bulk_create(rows, batch_size=500, ignore_conflicts=True)

        if not quiet:
            self.stdout.write(
                f"  Added {len(created)} {role}s "
                f"(total {User.objects.filter(role=role).count()})."
            )
        return list(User.objects.filter(role=role).order_by("id"))

    def _ensure_courses(self, quiet):
        current = Course.objects.count()
        needed = max(0, COURSE_TARGET - current)
        if needed == 0:
            if not quiet:
                self.stdout.write(f"  Courses already at {current}; nothing to add.")
            return

        teachers = list(User.objects.filter(role=User.Role.TEACHER).order_by("id"))
        if not teachers:
            raise RuntimeError("Teachers are required before creating courses.")

        category_names = [
            "Programming",
            "Data and AI",
            "Design",
            "Business",
            "Mathematics",
            "Communication",
        ]
        categories = [
            Category.objects.get_or_create(
                name=name,
                defaults={"description": f"{name} courses and resources."},
            )[0]
            for name in category_names
        ]

        existing_codes = set(Course.objects.values_list("code", flat=True))
        existing_slugs = set(Course.objects.values_list("slug", flat=True))
        now = timezone.now()
        courses = []
        sequence = 1

        while len(courses) < needed:
            code = f"CRS{sequence:03d}"
            sequence += 1
            if code in existing_codes:
                continue

            index = len(courses)
            subject = SUBJECTS[index % len(SUBJECTS)]
            level = ["Introduction to", "Intermediate", "Advanced"][
                (index // len(SUBJECTS)) % 3
            ]
            title = f"{level} {subject}"
            slug = slugify(f"{title}-{code}")
            suffix = 2
            while slug in existing_slugs:
                slug = slugify(f"{title}-{code}-{suffix}")
                suffix += 1
            existing_slugs.add(slug)

            if index < 65:
                status = Course.Status.PUBLISHED
                published_at = now - timedelta(days=index * 2)
            elif index < 80:
                status = Course.Status.DRAFT
                published_at = None
            else:
                status = Course.Status.ARCHIVED
                published_at = now - timedelta(days=300 + index)

            courses.append(
                Course(
                    code=code,
                    title=title,
                    slug=slug,
                    category=categories[index % len(categories)],
                    teacher=teachers[index % len(teachers)],
                    description=(
                        f"{title} builds practical skills through guided lessons, "
                        "hands-on activities, and authentic assessments."
                    ),
                    objectives=(
                        "Understand the core concepts\n"
                        "Apply skills in practical exercises\n"
                        "Complete a final project"
                    ),
                    status=status,
                    difficulty=[
                        Course.Difficulty.BEGINNER,
                        Course.Difficulty.INTERMEDIATE,
                        Course.Difficulty.ADVANCED,
                    ][index % 3],
                    duration_hours=8 + (index % 25),
                    certificate_enabled=status == Course.Status.PUBLISHED,
                    is_featured=index < 6 and status == Course.Status.PUBLISHED,
                    published_at=published_at,
                )
            )

        Course.objects.bulk_create(courses, batch_size=300)
        if not quiet:
            self.stdout.write(
                f"  Added {len(courses)} courses (total {Course.objects.count()})."
            )

    def _ensure_announcements(self, quiet):
        current = Announcement.objects.count()
        needed = max(0, ANNOUNCEMENT_TARGET - current)
        if needed == 0:
            if not quiet:
                self.stdout.write(
                    f"  Announcements already at {current}; nothing to add."
                )
            return

        admin = User.objects.filter(role=User.Role.ADMIN).order_by("id").first()
        courses = list(Course.objects.order_by("id"))
        now = timezone.now()
        existing_titles = set(Announcement.objects.values_list("title", flat=True))
        titles = [
            "Midterm examination schedule",
            "New video lessons are now available",
            "Scheduled platform maintenance",
            "Scholarship applications are open",
            "Welcome to the new semester",
            "Reminder: update your profile",
            "Course registration deadline",
        ]
        audiences = [
            Announcement.Audience.EVERYONE,
            Announcement.Audience.STUDENTS,
            Announcement.Audience.TEACHERS,
            Announcement.Audience.COURSE,
            Announcement.Audience.STUDENTS,
            Announcement.Audience.EVERYONE,
            Announcement.Audience.TEACHERS,
        ]
        announcements = []
        index = 0
        while len(announcements) < needed:
            title = titles[index % len(titles)]
            if title in existing_titles:
                title = f"{title} ({len(announcements) + 2})"
            audience = audiences[index % len(audiences)]
            announcements.append(
                Announcement(
                    title=title,
                    content=(
                        f"{title}. Please review the details in your dashboard and "
                        "contact your instructor if you have questions."
                    ),
                    audience=audience,
                    course=(
                        courses[index % len(courses)]
                        if audience == Announcement.Audience.COURSE and courses
                        else None
                    ),
                    created_by=admin,
                    is_published=True,
                    published_at=now - timedelta(days=index * 3),
                )
            )
            existing_titles.add(title)
            index += 1

        Announcement.objects.bulk_create(announcements)
        if not quiet:
            self.stdout.write(
                f"  Added {len(announcements)} announcements "
                f"(total {Announcement.objects.count()})."
            )

    def _ensure_notifications(self, quiet):
        current = Notification.objects.count()
        needed = max(0, NOTIFICATION_TARGET - current)
        if needed == 0:
            if not quiet:
                self.stdout.write(
                    f"  Notifications already at {current}; nothing to add."
                )
            return

        admin = User.objects.filter(role=User.Role.ADMIN).order_by("id").first()
        teacher = User.objects.filter(role=User.Role.TEACHER).order_by("id").first()
        student = User.objects.filter(role=User.Role.STUDENT).order_by("id").first()
        planned_recipients = (
            [admin] * 12 + [student] * 21 + [teacher] * 10
        )
        recipients = [user for user in planned_recipients if user]
        if not recipients:
            return

        templates = [
            (
                Notification.Kind.ANNOUNCEMENT,
                "New platform announcement",
                "A new announcement has been posted. Open the announcements page to read it.",
                "/notifications/announcements/",
            ),
            (
                Notification.Kind.ASSIGNMENT,
                "Assignment reminder",
                "You have an upcoming assignment. Review the deadline and submit on time.",
                "/courses/",
            ),
            (
                Notification.Kind.GRADE,
                "Grade posted",
                "A grade has been released for one of your assessments.",
                "/reports/reports/",
            ),
            (
                Notification.Kind.CERTIFICATE,
                "Certificate available",
                "A certificate is ready to view and download from your certificates page.",
                "/certificates/",
            ),
            (
                Notification.Kind.QUIZ,
                "Quiz update",
                "A quiz in one of your courses has new information.",
                "/courses/",
            ),
            (
                Notification.Kind.INFO,
                "Welcome to Smart Learning",
                "Explore your dashboard, courses, and learning tools.",
                "/dashboard/",
            ),
            (
                Notification.Kind.SUCCESS,
                "Profile updated",
                "Your account profile was updated successfully.",
                "/accounts/profile/",
            ),
        ]

        now = timezone.now()
        notifications = []
        for index in range(needed):
            kind, title, message, link = templates[index % len(templates)]
            is_read = index % 4 == 0
            notifications.append(
                Notification(
                    recipient=recipients[index % len(recipients)],
                    title=title,
                    message=message,
                    kind=kind,
                    link=link,
                    is_read=is_read,
                    read_at=now - timedelta(hours=index) if is_read else None,
                )
            )

        Notification.objects.bulk_create(notifications, batch_size=200)
        if not quiet:
            self.stdout.write(
                f"  Added {len(notifications)} notifications "
                f"(total {Notification.objects.count()})."
            )

    def _ensure_certificates_and_enrollments(self, quiet):
        students = list(User.objects.filter(role=User.Role.STUDENT).order_by("id"))
        courses = list(Course.objects.order_by("id"))
        if not students or not courses:
            return

        template, _ = CertificateTemplate.objects.get_or_create(
            name="Classic Completion",
            defaults={
                "description": "Clean default certificate for completed courses.",
                "is_default": True,
                "created_by": User.objects.filter(role=User.Role.ADMIN).first(),
            },
        )

        existing_certificate_pairs = set(
            Certificate.objects.values_list("student_id", "course_id")
        )
        existing_enrollment_pairs = set(
            Enrollment.objects.values_list("student_id", "course_id")
        )

        current_certificates = Certificate.objects.count()
        needed_certificates = max(0, CERTIFICATE_TARGET - current_certificates)
        now = timezone.now()
        certificates = []
        new_certificate_pairs = set()
        certificate_grades = {}
        index = 0

        while (
            len(certificates) < needed_certificates
            and index < len(students) * max(1, len(courses))
        ):
            student = students[index % len(students)]
            course = courses[(index * 7) % len(courses)]
            pair = (student.id, course.id)

            if pair not in existing_certificate_pairs and pair not in new_certificate_pairs:
                grade = Decimal(80 + (index % 20))
                certificates.append(
                    Certificate(
                        student=student,
                        course=course,
                        template=template,
                        grade_at_issue=grade,
                        issued_by=course.teacher,
                        status=Certificate.Status.VALID,
                        issued_at=now - timedelta(days=index % 180),
                    )
                )
                new_certificate_pairs.add(pair)
                certificate_grades[pair] = grade

            index += 1
            if index > len(students) * len(courses):
                break

        if certificates:
            Certificate.objects.bulk_create(certificates, batch_size=500)
        if not quiet:
            self.stdout.write(
                f"  Added {len(certificates)} certificates "
                f"(total {Certificate.objects.count()})."
            )

        enrollments = []
        for certificate in certificates:
            pair = (certificate.student_id, certificate.course_id)
            if pair in existing_enrollment_pairs:
                continue
            grade = certificate_grades[pair]
            enrollments.append(
                Enrollment(
                    student_id=certificate.student_id,
                    course_id=certificate.course_id,
                    status=Enrollment.Status.COMPLETED,
                    completed_at=now - timedelta(days=index % 150),
                    final_grade=grade,
                )
            )
            existing_enrollment_pairs.add(pair)

        enrolled_student_ids = {
            student_id for student_id, _ in existing_enrollment_pairs
        }
        for student in students:
            if student.id in enrolled_student_ids:
                continue
            course = courses[student.id % len(courses)]
            pair = (student.id, course.id)
            if pair in existing_enrollment_pairs:
                continue
            enrollments.append(
                Enrollment(
                    student_id=student.id,
                    course_id=course.id,
                    status=Enrollment.Status.ACTIVE,
                )
            )
            existing_enrollment_pairs.add(pair)
            enrolled_student_ids.add(student.id)

        if enrollments:
            Enrollment.objects.bulk_create(enrollments, batch_size=500)
        if not quiet:
            self.stdout.write(
                f"  Added {len(enrollments)} enrollments "
                f"(total {Enrollment.objects.count()})."
            )

        # Every student should be studying at least five courses.
        existing_pairs = set(Enrollment.objects.values_list("student_id", "course_id"))
        enrollment_counts = {}
        for student_id, _ in existing_pairs:
            enrollment_counts[student_id] = enrollment_counts.get(student_id, 0) + 1

        extra_enrollments = []
        for index, student in enumerate(students):
            needed = ENROLLMENTS_PER_STUDENT - enrollment_counts.get(student.id, 0)
            offset = 0
            while needed > 0 and offset < len(courses):
                course = courses[(index + offset) % len(courses)]
                offset += 1
                pair = (student.id, course.id)
                if pair in existing_pairs:
                    continue
                extra_enrollments.append(
                    Enrollment(
                        student_id=student.id,
                        course_id=course.id,
                        status=Enrollment.Status.ACTIVE,
                    )
                )
                existing_pairs.add(pair)
                enrollment_counts[student.id] = (
                    enrollment_counts.get(student.id, 0) + 1
                )
                needed -= 1

        if extra_enrollments:
            Enrollment.objects.bulk_create(extra_enrollments, batch_size=500)
        if not quiet:
            self.stdout.write(
                f"  Added {len(extra_enrollments)} course enrollments so every "
                f"student studies {ENROLLMENTS_PER_STUDENT} courses "
                f"(total {Enrollment.objects.count()})."
            )

    def _ensure_assignments_and_submissions(self, quiet):
        """Give every course an assignment with student submissions.

        This fills the teacher dashboard's "Recent submissions" and "Awaiting
        grading" panels with a realistic mix of submitted, graded, and returned
        work.
        """
        courses = list(
            Course.objects.select_related("teacher").order_by("id")
        )
        if not courses:
            return

        now = timezone.now()
        assignment_titles = [
            "Reflection activity",
            "Hands-on exercise",
            "Weekly project task",
            "Case study analysis",
            "Practice worksheet",
        ]
        assignments = []
        created_assignments = 0

        for index, course in enumerate(courses):
            assignment = Assignment.objects.filter(course=course).order_by("id").first()
            if assignment is None:
                assignment = Assignment.objects.create(
                    course=course,
                    title=assignment_titles[index % len(assignment_titles)],
                    description=(
                        f"Apply what you learned in {course.code} by completing "
                        "this assignment and submitting your work."
                    ),
                    instructions=(
                        "Review the lesson materials, complete the activity, and "
                        "submit your response before the deadline."
                    ),
                    due_at=now + timedelta(days=7 + (index % 14)),
                    max_points=100,
                    allow_late_submission=True,
                    is_published=True,
                    created_by=course.teacher,
                )
                created_assignments += 1
            assignments.append(assignment)

        students_by_course = {}
        for enrollment in (
            Enrollment.objects.filter(
                course__in=courses,
                status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED],
            )
            .select_related("student")
            .order_by("id")
        ):
            students_by_course.setdefault(enrollment.course_id, []).append(
                enrollment.student
            )

        existing_pairs = set(
            Submission.objects.filter(assignment__in=assignments).values_list(
                "assignment_id", "student_id"
            )
        )
        existing_counts = {
            row["assignment_id"]: row["total"]
            for row in Submission.objects.filter(assignment__in=assignments)
            .values("assignment_id")
            .annotate(total=Count("id"))
        }

        submissions = []
        submitted_at_values = []
        index = 0
        for assignment in assignments:
            students = students_by_course.get(assignment.course_id, [])
            if not students:
                continue

            remaining = SUBMISSIONS_PER_ASSIGNMENT - existing_counts.get(
                assignment.id, 0
            )
            if remaining <= 0:
                continue
            take = min(remaining, len(students))
            offset = (assignment.id * 7) % len(students)
            chosen = [students[(offset + position) % len(students)] for position in range(take)]

            for student in chosen:
                pair = (assignment.id, student.id)
                if pair in existing_pairs:
                    continue
                existing_pairs.add(pair)
                existing_counts[assignment.id] = (
                    existing_counts.get(assignment.id, 0) + 1
                )
                index += 1

                cycle = index % 10
                if cycle < 6:
                    status = Submission.Status.SUBMITTED
                    score = None
                elif cycle < 9:
                    status = Submission.Status.GRADED
                    score = Decimal(80 + (index % 20))
                else:
                    status = Submission.Status.RETURNED
                    score = None

                graded = status != Submission.Status.SUBMITTED
                submissions.append(
                    Submission(
                        assignment=assignment,
                        student=student,
                        text_response=(
                            f"Submitted work for {assignment.title} in "
                            f"{assignment.course.code}."
                        ),
                        status=status,
                        is_late=index % 7 == 0,
                        resubmission_count=1 if status == Submission.Status.RETURNED else 0,
                        score=score,
                        feedback=(
                            "Good work. Review the feedback notes and keep going."
                            if graded
                            else ""
                        ),
                        graded_by=assignment.course.teacher if graded else None,
                        graded_at=(
                            now - timedelta(hours=index) if graded else None
                        ),
                    )
                )
                submitted_at_values.append(
                    now - timedelta(hours=index * 2, minutes=index % 60)
                )

        if submissions:
            # Save individually so every row gets a primary key even when the
            # database cannot return bulk-inserted keys.
            for submission in submissions:
                submission.save()
            # ``submitted_at`` uses auto_now_add, so set realistic timestamps
            # afterwards to keep the "Recent submissions" feed varied.
            for submission, submitted_at in zip(submissions, submitted_at_values):
                submission.submitted_at = submitted_at
            Submission.objects.bulk_update(
                submissions, ["submitted_at"], batch_size=500
            )

        if not quiet:
            self.stdout.write(
                f"  Added {created_assignments} assignments "
                f"(total {Assignment.objects.count()})."
            )
            self.stdout.write(
                f"  Added {len(submissions)} submissions "
                f"(total {Submission.objects.count()})."
            )

    def _ensure_attendance(self, quiet):
        """Seed attendance for enrolled students so students have a report."""
        enrollments = list(
            Enrollment.objects.filter(
                status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED]
            )
            .select_related("student", "course__teacher")
            .order_by("id")
        )
        if not enrollments:
            return

        existing_pairs = set(
            AttendanceRecord.objects.values_list("student_id", "course_id")
        )

        session_dates = []
        day = timezone.localdate()
        while len(session_dates) < ATTENDANCE_SESSIONS:
            if day.weekday() < 5:  # Monday to Friday
                session_dates.append(day)
            day -= timedelta(days=1)

        statuses = AttendanceRecord.Status
        records = []
        index = 0
        for enrollment in enrollments:
            pair = (enrollment.student_id, enrollment.course_id)
            if pair in existing_pairs:
                continue
            for session_date in session_dates:
                index += 1
                cycle = index % 20
                if cycle == 0:
                    status = statuses.ABSENT
                    remarks = "Missed class."
                elif cycle in (7, 15):
                    status = statuses.LATE
                    remarks = "Arrived late."
                elif cycle == 3:
                    status = statuses.EXCUSED
                    remarks = "Excused absence."
                else:
                    status = statuses.PRESENT
                    remarks = ""

                records.append(
                    AttendanceRecord(
                        student_id=enrollment.student_id,
                        course_id=enrollment.course_id,
                        date=session_date,
                        status=status,
                        remarks=remarks,
                        recorded_by=enrollment.course.teacher,
                    )
                )

        if records:
            AttendanceRecord.objects.bulk_create(records, batch_size=1000)

        if not quiet:
            self.stdout.write(
                f"  Added {len(records)} attendance records "
                f"(total {AttendanceRecord.objects.count()})."
            )
