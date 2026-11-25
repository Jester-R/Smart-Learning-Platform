from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.careers.models import CompanyProfile

from .models import StudentProfile, TeacherProfile, User


class UserModelTests(TestCase):
    def test_email_is_normalized_and_password_is_hashed(self):
        user = User.objects.create_user(
            email="Student.Name@Example.COM",
            password="StrongPass123!",
            first_name="Student",
            last_name="Name",
        )
        self.assertEqual(user.email, "student.name@example.com")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertEqual(user.full_name, "Student Name")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.is_student_role)
        self.assertFalse(user.is_teacher_role)

    def test_superuser_has_admin_role(self):
        admin = User.objects.create_superuser(
            email="admin@example.com",
            password="StrongPass123!",
            first_name="Site",
            last_name="Admin",
        )
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.is_admin_role)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(email="dup@example.com", password="StrongPass123!")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(email="dup@example.com", password="StrongPass123!")

    def test_profiles_generate_unique_identifiers(self):
        teacher = User.objects.create_user(
            email="teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="T",
            last_name="One",
        )
        student = User.objects.create_user(
            email="student@example.com",
            password="StrongPass123!",
            first_name="S",
            last_name="One",
        )
        teacher_profile = TeacherProfile.objects.create(user=teacher)
        student_profile = StudentProfile.objects.create(user=student)
        self.assertTrue(teacher_profile.employee_number.startswith("TCH-"))
        self.assertTrue(student_profile.student_number.startswith("STU-"))
        self.assertNotEqual(
            teacher_profile.employee_number, student_profile.student_number
        )


class DashboardRoleTests(TestCase):
    def test_company_account_gets_company_dashboard(self):
        company = User.objects.create_user(
            email="company@example.com",
            password="StrongPass123!",
            role=User.Role.COMPANY,
            first_name="Demo",
            last_name="Company",
        )
        CompanyProfile.objects.create(
            user=company, company_name="Demo Company", is_approved=True
        )
        self.client.force_login(company)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent applications")

    def test_university_admin_gets_university_dashboard(self):
        admin = User.objects.create_user(
            email="university@example.com",
            password="StrongPass123!",
            role=User.Role.UNIVERSITY_ADMIN,
            first_name="Demo",
            last_name="University",
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upcoming classes")
