from django.urls import path

from . import payment_views as payments
from . import views

app_name = "courses"

urlpatterns = [
    path("", views.course_list, name="list"),
    path("payments/", payments.payment_history, name="payment_history"),
    path("pay/<slug:slug>/", payments.checkout, name="checkout"),
    path("plans/", payments.subscription_plans, name="subscription_plans"),
    path(
        "plans/<slug:slug>/pay/",
        payments.subscription_checkout,
        name="subscription_checkout",
    ),
    path(
        "payments/verification/",
        payments.verification_queue,
        name="verification_queue",
    ),
    path(
        "payments/<int:pk>/verify/",
        payments.verify_payment,
        name="verify_payment",
    ),
    path(
        "payments/<int:pk>/reject/",
        payments.reject_payment,
        name="reject_payment",
    ),
    path("payments/<int:pk>/invoice/", payments.invoice_pdf, name="invoice_pdf"),
    path("payments/<int:pk>/receipt/", payments.receipt_pdf, name="receipt_pdf"),
    path("refunds/", payments.refund_list, name="refund_list"),
    path(
        "refunds/<int:pk>/request/",
        payments.request_refund,
        name="request_refund",
    ),
    path(
        "refunds/<int:pk>/<str:action>/",
        payments.process_refund,
        name="process_refund",
    ),
    path("mine/", views.my_courses, name="my_courses"),
    path("new/", views.CourseCreateView.as_view(), name="create"),
    path("<slug:slug>/", views.course_detail, name="detail"),
    path("<slug:slug>/edit/", views.CourseUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", views.CourseDeleteView.as_view(), name="delete"),
    path("<slug:slug>/enroll/", views.enroll, name="enroll"),
    path("<slug:slug>/students/", views.course_students, name="students"),
]
