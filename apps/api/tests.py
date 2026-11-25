from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.courses.models import (
    Course,
    Enrollment,
    Invoice,
    Payment,
    PaymentMethod,
    Refund,
)


class PaymentApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            email="api-admin@example.com",
            password="StrongPass123!",
            role=User.Role.ADMIN,
        )
        cls.teacher = User.objects.create_user(
            email="api-teacher@example.com",
            password="StrongPass123!",
            role=User.Role.TEACHER,
        )
        cls.student = User.objects.create_user(
            email="api-student@example.com",
            password="StrongPass123!",
        )
        cls.other_student = User.objects.create_user(
            email="api-other@example.com",
            password="StrongPass123!",
        )
        cls.method = PaymentMethod.objects.create(name="Test Card", code="test-card")
        cls.course = Course.objects.create(
            code="API101",
            title="API Course",
            teacher=cls.teacher,
            description="Paid course.",
            price=Decimal("750.00"),
        )

    def _payment(self, student=None):
        return Payment.objects.create(
            student=student or self.student,
            course=self.course,
            amount=self.course.price,
            method=self.method,
        )

    def test_student_can_create_payment_and_invoice(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            reverse("payment-list"),
            {
                "course": self.course.pk,
                "method": self.method.pk,
                "reference": "API-REF-1",
                "notes": "Paid online",
                "status": "completed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(pk=response.data["id"])
        self.assertEqual(payment.student, self.student)
        self.assertEqual(str(payment.amount), "750.00")
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertTrue(Invoice.objects.filter(payment=payment).exists())

    def test_admin_can_verify_payment(self):
        payment = self._payment()
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("payment-verify", args=[payment.pk]),
            {"reference": "API-REF-2"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.COMPLETED)
        self.assertTrue(
            Enrollment.objects.filter(student=self.student, course=self.course).exists()
        )

    def test_student_cannot_view_another_students_payment(self):
        payment = self._payment(student=self.other_student)
        self.client.force_authenticate(self.student)
        response = self.client.get(reverse("payment-detail", args=[payment.pk]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_refund_flow(self):
        payment = self._payment()
        payment.verify(self.admin)
        self.client.force_authenticate(self.student)
        response = self.client.post(
            reverse("payment-refund", args=[payment.pk]),
            {"reason": "Duplicate charge"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        refund = Refund.objects.get(pk=response.data["id"])
        self.client.force_authenticate(self.admin)
        self.client.post(reverse("refund-approve", args=[refund.pk]))
        response = self.client.post(reverse("refund-complete", args=[refund.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
