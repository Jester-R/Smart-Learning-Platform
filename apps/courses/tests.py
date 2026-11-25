from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .models import (
    Category,
    Course,
    Enrollment,
    Invoice,
    Payment,
    PaymentMethod,
    Refund,
    StudentSubscription,
    SubscriptionPlan,
)


class CourseModelTests(TestCase):
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
        cls.category = Category.objects.create(name="Programming")
        cls.course = Course.objects.create(
            code="CS101",
            title="Intro to Programming",
            category=cls.category,
            teacher=cls.teacher,
            description="Programming fundamentals.",
            status=Course.Status.PUBLISHED,
        )

    def test_course_slug_is_generated_and_unique(self):
        second = Course.objects.create(
            code="CS102",
            title="Intro to Programming",
            teacher=self.teacher,
            description="Second course.",
        )
        self.assertEqual(self.course.slug, "intro-to-programming")
        self.assertNotEqual(second.slug, self.course.slug)

    def test_publishing_sets_published_at(self):
        self.assertIsNotNone(self.course.published_at)

    def test_duplicate_enrollment_is_rejected(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Enrollment.objects.create(student=self.student, course=self.course)

    def test_enrollment_requires_student_role(self):
        enrollment = Enrollment(student=self.teacher, course=self.course)
        with self.assertRaises(ValidationError):
            enrollment.full_clean()

    def test_mark_completed_updates_status_and_grade(self):
        enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        enrollment.mark_completed(grade=88)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.Status.COMPLETED)
        self.assertEqual(str(enrollment.final_grade), "88.00")
        self.assertIsNotNone(enrollment.completed_at)


class PaymentModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = User.objects.create_user(
            email="pay-teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
            first_name="Teacher",
            last_name="Two",
        )
        cls.student = User.objects.create_user(
            email="pay-student@example.com",
            password="StrongPass123!",
            first_name="Student",
            last_name="Two",
        )
        cls.method = PaymentMethod.objects.create(name="Test Bank Transfer")
        cls.course = Course.objects.create(
            code="PAY101",
            title="Introduction to Payments",
            teacher=cls.teacher,
            description="Payment basics.",
            price=Decimal("1500.00"),
        )
        cls.plan = SubscriptionPlan.objects.create(
            name="Monthly Access", price=Decimal("500.00"), duration_days=30
        )

    def _payment(self, **kwargs):
        return Payment.objects.create(
            student=self.student,
            course=self.course,
            amount=self.course.price,
            method=self.method,
            **kwargs,
        )

    def test_verify_creates_enrollment_and_marks_payment_completed(self):
        payment = self._payment(reference="TXN-12345")
        payment.verify(self.teacher, notes="Verified", reference="TXN-99999")
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.COMPLETED)
        self.assertEqual(payment.reference, "TXN-99999")
        self.assertEqual(payment.verified_by, self.teacher)
        self.assertIsNotNone(payment.paid_at)
        self.assertTrue(
            Enrollment.objects.filter(student=self.student, course=self.course).exists()
        )

    def test_verify_plan_payment_creates_subscription(self):
        payment = Payment.objects.create(
            student=self.student,
            plan=self.plan,
            amount=self.plan.price,
            method=self.method,
        )
        payment.verify(self.teacher)
        self.assertTrue(
            StudentSubscription.objects.filter(
                student=self.student, plan=self.plan, payment=payment
            ).exists()
        )

    def test_reject_records_verification_details(self):
        payment = self._payment()
        payment.reject(self.teacher, notes="Invalid reference")
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REJECTED)
        self.assertEqual(payment.verification_notes, "Invalid reference")

    def test_invoice_number_is_generated(self):
        invoice = Invoice.objects.create(payment=self._payment())
        self.assertTrue(invoice.number.startswith("INV-"))

    def test_completed_refund_marks_payment_refunded(self):
        payment = self._payment()
        payment.verify(self.teacher)
        refund = Refund.objects.create(
            payment=payment,
            amount=payment.amount,
            reason="Duplicate payment",
            requested_by=self.student,
        )
        refund.approve(self.teacher)
        refund.complete(self.teacher)
        payment.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.COMPLETED)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)

    def test_amount_must_be_positive(self):
        payment = Payment(
            student=self.student,
            course=self.course,
            amount=Decimal("0"),
        )
        with self.assertRaises(ValidationError):
            payment.full_clean()


class PaymentWebFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            email="pay-admin@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
        )
        cls.teacher = User.objects.create_user(
            email="pay-web-teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
        )
        cls.student = User.objects.create_user(
            email="pay-web-student@example.com",
            password="StrongPass123!",
            first_name="Web",
            last_name="Student",
        )
        cls.method = PaymentMethod.objects.create(name="Test GCash", code="test-gcash")
        cls.course = Course.objects.create(
            code="WEB201",
            title="Paid Web Course",
            teacher=cls.teacher,
            description="Paid course.",
            status=Course.Status.PUBLISHED,
            price=Decimal("999.00"),
        )
        cls.plan = SubscriptionPlan.objects.create(
            name="Yearly Plan", price=Decimal("1000.00"), duration_days=365
        )

    def test_checkout_creates_pending_payment_and_invoice(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("courses:checkout", args=[self.course.slug]),
            {"method": self.method.pk, "reference": "REF-100"},
        )
        self.assertRedirects(response, reverse("courses:payment_history"))
        payment = Payment.objects.get(student=self.student, course=self.course)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertTrue(Invoice.objects.filter(payment=payment).exists())

    def test_admin_verification_activates_enrollment(self):
        payment = Payment.objects.create(
            student=self.student,
            course=self.course,
            amount=self.course.price,
            method=self.method,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("courses:verify_payment", args=[payment.pk]),
            {"reference": "REF-200", "notes": "Verified"},
        )
        self.assertRedirects(response, reverse("courses:verification_queue"))
        self.assertTrue(
            Enrollment.objects.filter(student=self.student, course=self.course).exists()
        )

    def test_invoice_pdf_is_restricted_to_owner(self):
        payment = Payment.objects.create(
            student=self.student,
            course=self.course,
            amount=self.course.price,
            method=self.method,
        )
        other = User.objects.create_user(
            email="pay-other@example.com", password="StrongPass123!"
        )
        self.client.force_login(other)
        response = self.client.get(reverse("courses:invoice_pdf", args=[payment.pk]))
        self.assertEqual(response.status_code, 403)

    def test_student_can_request_refund(self):
        payment = Payment.objects.create(
            student=self.student,
            course=self.course,
            amount=self.course.price,
            method=self.method,
        )
        payment.verify(self.admin)
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("courses:request_refund", args=[payment.pk]),
            {"reason": "Course cancelled"},
        )
        self.assertRedirects(response, reverse("courses:refund_list"))
        self.assertTrue(Refund.objects.filter(payment=payment).exists())
