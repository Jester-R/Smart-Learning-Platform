import shutil
import tempfile

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.courses.models import Course

from .models import Certificate, CertificateTemplate


class CertificateModelTests(TestCase):
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
        )

    def test_certificate_identifiers_are_generated(self):
        certificate = Certificate.objects.create(
            student=self.student, course=self.course, issued_by=self.teacher
        )
        self.assertTrue(certificate.certificate_id.startswith("CERT-"))
        self.assertEqual(len(certificate.verification_code), 32)

    def test_duplicate_certificate_is_rejected(self):
        Certificate.objects.create(
            student=self.student, course=self.course, issued_by=self.teacher
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Certificate.objects.create(
                    student=self.student, course=self.course, issued_by=self.teacher
                )

    def test_revoke_certificate(self):
        certificate = Certificate.objects.create(
            student=self.student, course=self.course, issued_by=self.teacher
        )
        certificate.revoke("Issued in error.")
        certificate.refresh_from_db()
        self.assertEqual(certificate.status, Certificate.Status.REVOKED)
        self.assertIsNotNone(certificate.revoked_at)

    def test_only_one_default_template(self):
        first = CertificateTemplate.objects.create(name="Classic", is_default=True)
        second = CertificateTemplate.objects.create(name="Modern", is_default=True)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

    def test_admin_certificate_list_shows_all_certificates(self):
        call_command("seed_roles", verbosity=0)
        admin = User.objects.create_superuser(
            email="cert-admin@example.com",
            password="StrongPass123!",
            first_name="Cert",
            last_name="Admin",
        )
        certificate = Certificate.objects.create(
            student=self.student, course=self.course, issued_by=self.teacher
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("certificates:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 certificates")
        self.assertContains(response, certificate.certificate_id)


class CertificateDownloadTests(TestCase):
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
        cls.other_student = User.objects.create_user(
            email="other@example.com",
            password="StrongPass123!",
            first_name="Other",
            last_name="Student",
        )
        cls.course = Course.objects.create(
            code="CS101",
            title="Intro to Programming",
            teacher=cls.teacher,
            description="Programming fundamentals.",
        )
        cls.certificate = Certificate.objects.create(
            student=cls.student,
            course=cls.course,
            issued_by=cls.teacher,
        )

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def _download(self):
        return self.client.get(
            reverse("certificates:download", args=[self.certificate.pk])
        )

    def test_owner_can_save_pdf_and_pdf_is_generated_on_demand(self):
        self.assertFalse(self.certificate.pdf_file)
        self.client.force_login(self.student)

        response = self._download()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(self.certificate.certificate_id, response["Content-Disposition"])
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 1000)

        self.certificate.refresh_from_db()
        self.assertTrue(self.certificate.pdf_file)

    def test_second_download_reuses_stored_pdf(self):
        self.client.force_login(self.student)
        self._download()
        self.certificate.refresh_from_db()
        stored_name = self.certificate.pdf_file.name

        response = self._download()

        self.assertEqual(response.status_code, 200)
        self.certificate.refresh_from_db()
        self.assertEqual(self.certificate.pdf_file.name, stored_name)

    def test_teacher_can_save_certificate_for_own_course(self):
        self.client.force_login(self.teacher)

        response = self._download()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_other_student_cannot_download_certificate(self):
        self.client.force_login(self.other_student)

        response = self._download()

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self._download()

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_certificate_pages_show_save_pdf_button(self):
        self.client.force_login(self.student)

        list_response = self.client.get(reverse("certificates:list"))
        detail_response = self.client.get(
            reverse("certificates:detail", args=[self.certificate.pk])
        )

        download_url = reverse(
            "certificates:download", args=[self.certificate.pk]
        )
        self.assertContains(list_response, download_url)
        self.assertContains(detail_response, download_url)
        self.assertContains(detail_response, "Save PDF")

