from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register("courses", views.CourseViewSet, basename="course")
router.register("lessons", views.LessonViewSet, basename="lesson")
router.register("materials", views.MaterialViewSet, basename="material")
router.register("enrollments", views.EnrollmentViewSet, basename="enrollment")
router.register("assignments", views.AssignmentViewSet, basename="assignment")
router.register("submissions", views.SubmissionViewSet, basename="submission")
router.register("quizzes", views.QuizViewSet, basename="quiz")
router.register("certificates", views.CertificateViewSet, basename="certificate")
router.register("payment-methods", views.PaymentMethodViewSet, basename="paymentmethod")
router.register("subscription-plans", views.SubscriptionPlanViewSet, basename="subscriptionplan")
router.register("subscriptions", views.StudentSubscriptionViewSet, basename="studentsubscription")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("refunds", views.RefundViewSet, basename="refund")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include(router.urls)),
]
