from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import is_admin, is_student, is_teacher
from apps.assessments.models import Assignment, Quiz, QuizAttempt, Submission
from apps.certificates.models import Certificate
from apps.courses.models import (
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

from .permissions import IsAdminRole, IsStudentRole
from .serializers import (
    AssignmentSerializer,
    CertificateSerializer,
    CourseSerializer,
    EnrollmentSerializer,
    InvoiceSerializer,
    LessonSerializer,
    MaterialSerializer,
    PaymentMethodSerializer,
    PaymentSerializer,
    QuizSerializer,
    RefundSerializer,
    StudentSubscriptionSerializer,
    SubmissionSerializer,
    SubscriptionPlanSerializer,
)


def accessible_course_ids(user):
    if is_admin(user):
        return Course.objects.values_list("id", flat=True)
    if is_teacher(user):
        return Course.objects.filter(teacher=user).values_list("id", flat=True)
    return Enrollment.objects.filter(student=user).values_list(
        "course_id", flat=True
    )


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Course.objects.select_related(
            "teacher", "category"
        ).annotate(student_count=Count("enrollments", distinct=True))
        user = self.request.user
        if is_student(user):
            queryset = queryset.filter(status=Course.Status.PUBLISHED)
        elif is_teacher(user):
            queryset = queryset.filter(teacher=user)
        elif not is_admin(user):
            return queryset.none()
        query = self.request.query_params.get("q")
        if query:
            queryset = queryset.filter(title__icontains=query)
        return queryset


class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Lesson.objects.select_related("course").filter(is_published=True)
        user = self.request.user
        queryset = queryset.filter(course_id__in=accessible_course_ids(user))
        course_id = self.request.query_params.get("course")
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset


class MaterialViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = LearningMaterial.objects.select_related("course")
        user = self.request.user
        queryset = queryset.filter(course_id__in=accessible_course_ids(user))
        course_id = self.request.query_params.get("course")
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset


class EnrollmentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Enrollment.objects.select_related("student", "course")
        user = self.request.user
        if is_student(user):
            return queryset.filter(student=user)
        if is_teacher(user):
            return queryset.filter(course__teacher=user)
        if is_admin(user):
            return queryset
        return queryset.none()

    def perform_create(self, serializer):
        if not is_student(self.request.user):
            raise PermissionDenied("Only student accounts can enroll.")
        course = serializer.validated_data["course"]
        if course.status != Course.Status.PUBLISHED:
            raise ValidationError("This course is not open for enrollment.")
        if Enrollment.objects.filter(
            student=self.request.user, course=course
        ).exists():
            raise ValidationError("You are already enrolled in this course.")
        serializer.save(student=self.request.user)


class AssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Assignment.objects.select_related("course").filter(
            is_published=True
        )
        user = self.request.user
        queryset = queryset.filter(course_id__in=accessible_course_ids(user))
        course_id = self.request.query_params.get("course")
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset


class SubmissionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Submission.objects.select_related("assignment", "student")
        user = self.request.user
        if is_student(user):
            return queryset.filter(student=user)
        if is_teacher(user):
            return queryset.filter(assignment__course__teacher=user)
        if is_admin(user):
            return queryset
        return queryset.none()

    def perform_create(self, serializer):
        if not is_student(self.request.user):
            raise PermissionDenied("Only students can submit assignments.")
        assignment = serializer.validated_data["assignment"]
        if not Enrollment.objects.filter(
            student=self.request.user, course=assignment.course
        ).exists():
            raise ValidationError("Enroll in the course before submitting.")
        if assignment.is_past_due and not assignment.allow_late_submission:
            raise ValidationError("The deadline has passed.")
        if Submission.objects.filter(
            assignment=assignment, student=self.request.user
        ).exists():
            raise ValidationError(
                "A submission already exists. Use the web form to resubmit."
            )
        serializer.save(
            student=self.request.user,
            is_late=assignment.is_past_due,
            status=Submission.Status.SUBMITTED,
        )


class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = QuizSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Quiz.objects.select_related("course").prefetch_related(
            "questions__choices"
        )
        user = self.request.user
        if is_student(user):
            return queryset.filter(
                is_published=True, course_id__in=accessible_course_ids(user)
            )
        if is_teacher(user):
            return queryset.filter(course__teacher=user)
        if is_admin(user):
            return queryset
        return queryset.none()

    @action(detail=True, methods=["post"], permission_classes=[IsStudentRole])
    def start(self, request, pk=None):
        quiz = self.get_object()
        if not quiz.is_available:
            raise ValidationError("This quiz is not currently available.")
        if not quiz.questions.exists():
            raise ValidationError("This quiz has no questions yet.")
        in_progress = quiz.attempts.filter(
            student=request.user, status=QuizAttempt.Status.IN_PROGRESS
        ).first()
        if in_progress:
            return Response({"attempt_id": in_progress.pk, "resumed": True})
        used = quiz.attempts.filter(student=request.user).count()
        if used >= quiz.max_attempts:
            raise ValidationError("No attempts remaining.")
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=request.user,
            attempt_number=used + 1,
            max_score=quiz.total_points(),
        )
        return Response(
            {"attempt_id": attempt.pk, "started_at": attempt.started_at},
            status=status.HTTP_201_CREATED,
        )


class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Certificate.objects.select_related("student", "course")
        user = self.request.user
        if is_student(user):
            return queryset.filter(student=user)
        if is_teacher(user):
            return queryset.filter(course__teacher=user)
        if is_admin(user):
            return queryset
        return queryset.none()


class PaymentMethodViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    queryset = PaymentMethod.objects.filter(is_active=True)


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]
    queryset = SubscriptionPlan.objects.filter(is_active=True)


class StudentSubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StudentSubscription.objects.select_related("student", "plan")
        user = self.request.user
        if is_student(user):
            return queryset.filter(student=user)
        if is_teacher(user):
            return queryset.none()
        if is_admin(user):
            return queryset
        return queryset.none()


class PaymentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Payment.objects.select_related(
            "student", "course", "plan", "method", "enrollment", "verified_by"
        )
        user = self.request.user
        if is_admin(user):
            return queryset
        if is_student(user):
            return queryset.filter(student=user)
        if is_teacher(user):
            return queryset.filter(course__teacher=user)
        return queryset.none()

    def perform_create(self, serializer):
        if not is_student(self.request.user):
            raise PermissionDenied("Only students can create payments.")
        course = serializer.validated_data.get("course")
        plan = serializer.validated_data.get("plan")
        if bool(course) == bool(plan):
            raise ValidationError("Provide exactly one of course or plan.")
        if course and Enrollment.objects.filter(
            student=self.request.user, course=course
        ).exists():
            raise ValidationError("You are already enrolled in this course.")
        amount = course.price if course else plan.price
        if amount <= 0:
            raise ValidationError("Free items do not require payment.")
        payment = serializer.save(student=self.request.user, amount=amount)
        Invoice.objects.create(payment=payment)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def verify(self, request, pk=None):
        payment = self.get_object()
        if payment.status != Payment.Status.PENDING:
            raise ValidationError("This payment has already been processed.")
        payment.verify(
            request.user,
            notes=request.data.get("notes", ""),
            reference=request.data.get("reference") or None,
        )
        Invoice.objects.get_or_create(payment=payment)
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def reject(self, request, pk=None):
        payment = self.get_object()
        if payment.status != Payment.Status.PENDING:
            raise ValidationError("This payment has already been processed.")
        payment.reject(request.user, notes=request.data.get("notes", ""))
        return Response(self.get_serializer(payment).data)

    @action(detail=True, methods=["post"], permission_classes=[IsStudentRole])
    def refund(self, request, pk=None):
        payment = self.get_object()
        if payment.student_id != request.user.pk:
            raise PermissionDenied("You can only refund your own payments.")
        if payment.status != Payment.Status.COMPLETED:
            raise ValidationError("Only completed payments can be refunded.")
        reason = request.data.get("reason", "")
        if not reason:
            raise ValidationError({"reason": "This field is required."})
        refund = Refund.objects.create(
            payment=payment,
            amount=payment.amount,
            reason=reason,
            requested_by=request.user,
        )
        return Response(RefundSerializer(refund).data, status=status.HTTP_201_CREATED)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Invoice.objects.select_related(
            "payment", "payment__student", "payment__course"
        )
        user = self.request.user
        if is_admin(user):
            return queryset
        if is_student(user):
            return queryset.filter(payment__student=user)
        if is_teacher(user):
            return queryset.filter(payment__course__teacher=user)
        return queryset.none()


class RefundViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Refund.objects.select_related(
            "payment", "payment__student", "requested_by", "processed_by"
        )
        user = self.request.user
        if is_admin(user):
            return queryset
        if is_student(user):
            return queryset.filter(requested_by=user)
        if is_teacher(user):
            return queryset.filter(payment__course__teacher=user)
        return queryset.none()

    def perform_create(self, serializer):
        if not is_student(self.request.user):
            raise PermissionDenied("Only students can request refunds.")
        payment = serializer.validated_data.get("payment")
        if payment.student_id != self.request.user.pk:
            raise PermissionDenied("You can only refund your own payments.")
        if payment.status != Payment.Status.COMPLETED:
            raise ValidationError("Only completed payments can be refunded.")
        serializer.save(amount=payment.amount, requested_by=self.request.user)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def approve(self, request, pk=None):
        refund = self.get_object()
        refund.approve(request.user)
        return Response(self.get_serializer(refund).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def reject(self, request, pk=None):
        refund = self.get_object()
        refund.reject(request.user)
        return Response(self.get_serializer(refund).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def complete(self, request, pk=None):
        refund = self.get_object()
        try:
            refund.complete(request.user)
        except DjangoValidationError as exc:
            raise ValidationError(str(exc))
        return Response(self.get_serializer(refund).data)
