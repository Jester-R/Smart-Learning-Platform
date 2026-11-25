from django.urls import reverse
from rest_framework import serializers

from apps.accounts.models import User
from apps.assessments.models import Assignment, Question, Quiz, Submission
from apps.certificates.models import Certificate
from apps.courses.models import (
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
from apps.learning.models import LearningMaterial, Lesson


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "full_name", "role")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description")


class CourseSerializer(serializers.ModelSerializer):
    teacher = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    student_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Course
        fields = (
            "id",
            "code",
            "title",
            "slug",
            "price",
            "teacher",
            "category",
            "description",
            "objectives",
            "status",
            "difficulty",
            "duration_hours",
            "passing_score",
            "certificate_enabled",
            "student_count",
            "created_at",
        )


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = (
            "id",
            "course",
            "title",
            "description",
            "content",
            "video_url",
            "duration_minutes",
            "order",
            "is_published",
        )


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningMaterial
        fields = (
            "id",
            "course",
            "lesson",
            "title",
            "description",
            "material_type",
            "file",
            "external_url",
            "is_downloadable",
            "created_at",
        )


class EnrollmentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = Enrollment
        fields = (
            "id",
            "student",
            "student_name",
            "course",
            "course_title",
            "status",
            "enrolled_at",
            "final_grade",
        )
        read_only_fields = ("student", "enrolled_at", "final_grade")


class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = (
            "id",
            "course",
            "title",
            "description",
            "instructions",
            "attachment",
            "due_at",
            "max_points",
            "allow_late_submission",
            "is_published",
            "created_at",
        )


class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = (
            "id",
            "assignment",
            "student",
            "file",
            "text_response",
            "submitted_at",
            "is_late",
            "status",
            "score",
            "feedback",
            "graded_at",
        )
        read_only_fields = (
            "student",
            "submitted_at",
            "is_late",
            "status",
            "score",
            "feedback",
            "graded_at",
        )


class PublicChoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    text = serializers.CharField()
    order = serializers.IntegerField()


class PublicQuestionSerializer(serializers.ModelSerializer):
    choices = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ("id", "question_type", "text", "points", "order", "choices")

    def get_choices(self, obj):
        return PublicChoiceSerializer(obj.choices.all(), many=True).data


class QuizSerializer(serializers.ModelSerializer):
    questions = PublicQuestionSerializer(many=True, read_only=True)
    total_points = serializers.DecimalField(
        max_digits=7, decimal_places=2, read_only=True
    )

    class Meta:
        model = Quiz
        fields = (
            "id",
            "course",
            "title",
            "description",
            "instructions",
            "time_limit_minutes",
            "passing_score",
            "max_attempts",
            "opens_at",
            "closes_at",
            "is_published",
            "show_results",
            "total_points",
            "questions",
        )


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ("id", "name", "code", "description", "is_active", "sort_order")


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "price",
            "duration_days",
            "features",
            "is_active",
        )


class StudentSubscriptionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = StudentSubscription
        fields = (
            "id",
            "student",
            "student_name",
            "plan",
            "plan_name",
            "payment",
            "start_date",
            "end_date",
            "status",
        )
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    invoice_url = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = ("id", "number", "payment", "issued_at", "notes", "invoice_url")
        read_only_fields = fields

    def get_invoice_url(self, obj):
        return reverse("courses:invoice_pdf", args=[obj.payment_id])


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    method_name = serializers.CharField(source="method.name", read_only=True)
    invoice_url = serializers.SerializerMethodField()
    receipt_url = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id",
            "student",
            "student_name",
            "course",
            "course_title",
            "plan",
            "plan_name",
            "amount",
            "method",
            "method_name",
            "enrollment",
            "status",
            "reference",
            "notes",
            "verified_by",
            "verified_at",
            "paid_at",
            "created_at",
            "invoice_url",
            "receipt_url",
        )
        read_only_fields = (
            "student",
            "amount",
            "enrollment",
            "status",
            "verified_by",
            "verified_at",
            "paid_at",
            "created_at",
        )

    def get_invoice_url(self, obj):
        return reverse("courses:invoice_pdf", args=[obj.pk])

    def get_receipt_url(self, obj):
        return reverse("courses:receipt_pdf", args=[obj.pk])


class RefundSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(
        source="payment.reference", read_only=True
    )

    class Meta:
        model = Refund
        fields = (
            "id",
            "payment",
            "payment_reference",
            "amount",
            "reason",
            "status",
            "requested_by",
            "processed_by",
            "processed_at",
            "created_at",
        )
        read_only_fields = (
            "amount",
            "status",
            "requested_by",
            "processed_by",
            "processed_at",
            "created_at",
        )


class CertificateSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = Certificate
        fields = (
            "id",
            "certificate_id",
            "verification_code",
            "student",
            "student_name",
            "course",
            "course_title",
            "status",
            "grade_at_issue",
            "issued_at",
            "pdf_file",
        )
        read_only_fields = fields
