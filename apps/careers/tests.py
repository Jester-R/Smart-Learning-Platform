from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .models import ApplicationMessage, CVDocument, CompanyProfile, Job, JobApplication


class CareersPhaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0, skip_user_assignment=True)
        cls.student = User.objects.create_user(
            email="phase4-career-student@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Career",
            last_name="Student",
        )
        cls.company = User.objects.create_user(
            email="phase4-career-company@example.com",
            password="StrongPass123!",
            role=User.Role.COMPANY,
            first_name="Career",
            last_name="Company",
        )
        cls.profile = CompanyProfile.objects.create(
            user=cls.company,
            company_name="Cambodia Tech",
            contact_email="hr@example.com",
            is_approved=True,
        )
        cls.job = Job.objects.create(
            company=cls.profile,
            title="Django Developer",
            description="Build learning products.",
            job_type=Job.JobType.FULL_TIME,
            status=Job.Status.PUBLISHED,
            is_approved=True,
        )

    def test_only_published_approved_jobs_are_listed(self):
        Job.objects.create(
            company=self.profile,
            title="Hidden Job",
            description="Not approved.",
            job_type=Job.JobType.FULL_TIME,
            status=Job.Status.PUBLISHED,
            is_approved=False,
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("careers:job_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Django Developer")
        self.assertNotContains(response, "Hidden Job")

    def test_company_can_submit_job_for_approval(self):
        self.client.force_login(self.company)
        response = self.client.post(
            reverse("careers:job_create"),
            {
                "title": "Backend Intern",
                "description": "Internship role.",
                "job_type": Job.JobType.INTERNSHIP,
            },
        )
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(title="Backend Intern")
        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertFalse(job.is_approved)

    def test_student_can_apply_once(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("careers:job_apply", args=[self.job.pk]),
            {"cover_letter": "I am interested."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(JobApplication.objects.filter(job=self.job, applicant=self.student).exists())

        response = self.client.get(reverse("careers:job_apply", args=[self.job.pk]))
        self.assertRedirects(response, reverse("careers:job_detail", args=[self.job.pk]))

    def test_student_without_company_role_cannot_post_job(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("careers:job_create"))
        self.assertEqual(response.status_code, 403)

    def test_public_job_list_renders_for_anonymous_visitor(self):
        response = self.client.get(reverse("careers:job_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Django Developer")

    def test_seed_careers_data_is_idempotent_and_lists_all_positions(self):
        call_command("seed_careers_data", verbosity=0)
        first_count = Job.objects.count()
        call_command("seed_careers_data", verbosity=0)
        self.assertEqual(Job.objects.count(), first_count)
        self.assertGreaterEqual(
            Job.objects.filter(job_type=Job.JobType.INTERNSHIP, is_approved=True).count(), 16
        )
        response = self.client.get(reverse("careers:job_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Frontend Developer")
        self.assertContains(response, f"{first_count} open positions")

    def test_student_can_upload_cv_and_select_it_when_applying(self):
        self.client.force_login(self.student)
        upload = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
        response = self.client.post(
            reverse("careers:my_cvs"), {"title": "My CV", "file": upload}
        )
        self.assertEqual(response.status_code, 302)
        cv = CVDocument.objects.get(student=self.student, title="My CV")
        self.assertTrue(cv.file.name.startswith("cvs/"))
        page = self.client.get(reverse("careers:job_apply", args=[self.job.pk]))
        self.assertContains(page, "My CV")
        self.assertContains(page, reverse("careers:my_cvs"))

    def test_cv_upload_rejects_unsupported_file_type(self):
        self.client.force_login(self.student)
        upload = SimpleUploadedFile("cv.exe", b"binary", content_type="application/octet-stream")
        response = self.client.post(
            reverse("careers:my_cvs"), {"title": "Invalid", "file": upload}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PDF, DOC, or DOCX")
        self.assertFalse(CVDocument.objects.filter(student=self.student).exists())

    def test_cv_delete_is_post_only_and_limited_to_owner(self):
        cv = CVDocument.objects.create(
            student=self.student,
            title="Old CV",
            file=SimpleUploadedFile("old.pdf", b"%PDF-1.4 old"),
        )
        other = User.objects.create_user(
            email="other-cv-student@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Other",
            last_name="Student",
        )
        self.client.force_login(other)
        url = reverse("careers:cv_delete", args=[cv.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(CVDocument.objects.filter(pk=cv.pk).exists())
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(CVDocument.objects.filter(pk=cv.pk).exists())

    def test_apply_with_direct_cv_upload(self):
        self.client.force_login(self.student)
        upload = SimpleUploadedFile("apply.pdf", b"%PDF-1.4 apply", content_type="application/pdf")
        response = self.client.post(
            reverse("careers:job_apply", args=[self.job.pk]),
            {"cover_letter": "I am interested.", "cv_file": upload},
        )
        self.assertEqual(response.status_code, 302)
        application = JobApplication.objects.get(job=self.job, applicant=self.student)
        self.assertIsNotNone(application.cv_document)
        self.assertEqual(application.cv_document.student, self.student)
        self.assertTrue(application.cv_document.file.name.startswith("cvs/"))

    def test_admin_and_hr_can_review_applications_and_chat_about_interview(self):
        application = JobApplication.objects.create(job=self.job, applicant=self.student)
        admin = User.objects.create_superuser(
            email="careers-admin@example.com",
            password="StrongPass123!",
            first_name="Careers",
            last_name="Admin",
        )
        chat_url = reverse("careers:application_conversation", args=[application.pk])

        self.client.force_login(admin)
        self.assertContains(
            self.client.get(reverse("careers:all_applications")), self.student.email
        )
        self.assertEqual(self.client.get(chat_url).status_code, 200)
        self.client.post(chat_url, {"body": "Interview scheduled for Friday."})
        self.assertTrue(
            ApplicationMessage.objects.filter(application=application, sender=admin).exists()
        )

        self.client.force_login(self.company)
        self.assertContains(
            self.client.get(reverse("careers:all_applications")), self.job.title
        )
        self.client.post(chat_url, {"body": "Please confirm your availability."})

        self.client.force_login(self.student)
        response = self.client.get(chat_url)
        self.assertContains(response, "Interview scheduled for Friday.")
        self.assertContains(response, "Please confirm your availability.")

        other = User.objects.create_user(
            email="other-applicant@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
            first_name="Other",
            last_name="Applicant",
        )
        self.client.force_login(other)
        self.assertEqual(self.client.get(chat_url).status_code, 403)
        self.assertEqual(self.client.get(reverse("careers:all_applications")).status_code, 403)
