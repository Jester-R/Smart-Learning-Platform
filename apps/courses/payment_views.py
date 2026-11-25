from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import is_admin, is_student, is_teacher, role_required

from .models import (
    Course,
    Enrollment,
    Invoice,
    Payment,
    PaymentMethod,
    Refund,
    SubscriptionPlan,
)
from .payment_pdf import build_payment_pdf


def _visible_payments(user):
    payments = Payment.objects.select_related(
        "student", "course", "plan", "method", "enrollment", "verified_by"
    )
    if is_admin(user):
        return payments
    if is_student(user):
        return payments.filter(student=user)
    if is_teacher(user):
        return payments.filter(course__teacher=user)
    return payments.none()


def _visible_refunds(user):
    refunds = Refund.objects.select_related(
        "payment", "payment__student", "requested_by", "processed_by"
    )
    if is_admin(user):
        return refunds
    if is_student(user):
        return refunds.filter(requested_by=user)
    if is_teacher(user):
        return refunds.filter(payment__course__teacher=user)
    return refunds.none()


def _can_view_payment(user, payment):
    if is_admin(user):
        return True
    if is_student(user):
        return payment.student_id == user.pk
    if is_teacher(user):
        return payment.course_id and payment.course.teacher_id == user.pk
    return False


@login_required
def payment_history(request):
    return render(
        request,
        "courses/payment_history.html",
        {"payments": _visible_payments(request.user)},
    )


@role_required("student")
def checkout(request, slug):
    course = get_object_or_404(
        Course, slug=slug, status=Course.Status.PUBLISHED
    )
    if Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.info(request, "You are already enrolled in this course.")
        return redirect(course.get_absolute_url())
    if course.price <= 0:
        Enrollment.objects.get_or_create(
            student=request.user,
            course=course,
            defaults={"status": Enrollment.Status.ACTIVE},
        )
        messages.success(request, f"You are now enrolled in {course.title}.")
        return redirect(course.get_absolute_url())

    methods = PaymentMethod.objects.filter(is_active=True).order_by(
        "sort_order", "name"
    )
    if request.method == "POST":
        method_id = request.POST.get("method")
        method = methods.filter(pk=method_id).first()
        if method is None:
            messages.error(request, "Select a valid payment method.")
        else:
            payment = Payment.objects.create(
                student=request.user,
                course=course,
                amount=course.price,
                method=method,
                reference=request.POST.get("reference", "").strip(),
                notes=request.POST.get("notes", "").strip(),
            )
            Invoice.objects.create(payment=payment)
            messages.success(
                request,
                "Payment submitted. Your enrollment will be active after verification.",
            )
            return redirect("courses:payment_history")

    return render(
        request,
        "courses/checkout.html",
        {"course": course, "amount": course.price, "methods": methods},
    )


@login_required
def subscription_plans(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by(
        "sort_order", "name"
    )
    return render(
        request, "courses/subscription_plans.html", {"plans": plans}
    )


@role_required("student")
def subscription_checkout(request, slug):
    plan = get_object_or_404(SubscriptionPlan, slug=slug, is_active=True)
    methods = PaymentMethod.objects.filter(is_active=True).order_by(
        "sort_order", "name"
    )
    if request.method == "POST":
        method_id = request.POST.get("method")
        method = methods.filter(pk=method_id).first()
        if method is None:
            messages.error(request, "Select a valid payment method.")
        else:
            payment = Payment.objects.create(
                student=request.user,
                plan=plan,
                amount=plan.price,
                method=method,
                reference=request.POST.get("reference", "").strip(),
                notes=request.POST.get("notes", "").strip(),
            )
            Invoice.objects.create(payment=payment)
            messages.success(
                request,
                "Subscription payment submitted. It will be active after verification.",
            )
            return redirect("courses:payment_history")

    return render(
        request,
        "courses/subscription_checkout.html",
        {"plan": plan, "amount": plan.price, "methods": methods},
    )


@role_required("admin")
def verification_queue(request):
    payments = Payment.objects.filter(
        status=Payment.Status.PENDING
    ).select_related("student", "course", "plan", "method")
    return render(
        request, "courses/verification_queue.html", {"payments": payments}
    )


@role_required("admin")
@require_POST
def verify_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if payment.status != Payment.Status.PENDING:
        messages.info(request, "This payment has already been processed.")
    else:
        payment.verify(
            request.user,
            notes=request.POST.get("notes", "").strip(),
            reference=request.POST.get("reference", "").strip() or None,
        )
        Invoice.objects.get_or_create(payment=payment)
        messages.success(request, f"Payment #{payment.pk} verified.")
    return redirect("courses:verification_queue")


@role_required("admin")
@require_POST
def reject_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if payment.status != Payment.Status.PENDING:
        messages.info(request, "This payment has already been processed.")
    else:
        payment.reject(request.user, notes=request.POST.get("notes", "").strip())
        messages.success(request, f"Payment #{payment.pk} rejected.")
    return redirect("courses:verification_queue")


@login_required
def invoice_pdf(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if not _can_view_payment(request.user, payment):
        return HttpResponseForbidden("You cannot view this document.")
    invoice, _ = Invoice.objects.get_or_create(payment=payment)
    return build_payment_pdf(payment, "invoice")


@login_required
def receipt_pdf(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if not _can_view_payment(request.user, payment):
        return HttpResponseForbidden("You cannot view this document.")
    if payment.status not in (Payment.Status.COMPLETED, Payment.Status.REFUNDED):
        messages.error(request, "A receipt is available for completed payments only.")
        return redirect("courses:payment_history")
    return build_payment_pdf(payment, "receipt")


@role_required("student")
def request_refund(request, pk):
    payment = get_object_or_404(Payment, pk=pk, student=request.user)
    if payment.status != Payment.Status.COMPLETED:
        messages.error(request, "Only completed payments can be refunded.")
        return redirect("courses:payment_history")
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "Provide a reason for the refund request.")
        else:
            Refund.objects.create(
                payment=payment,
                amount=payment.amount,
                reason=reason,
                requested_by=request.user,
            )
            messages.success(request, "Refund request submitted.")
            return redirect("courses:refund_list")
    return render(
        request, "courses/request_refund.html", {"payment": payment}
    )


@login_required
def refund_list(request):
    return render(
        request,
        "courses/refund_list.html",
        {"refunds": _visible_refunds(request.user)},
    )


@role_required("admin")
@require_POST
def process_refund(request, pk, action):
    refund = get_object_or_404(Refund, pk=pk)
    actions = {
        "approve": refund.approve,
        "reject": refund.reject,
        "complete": refund.complete,
    }
    handler = actions.get(action)
    if handler is None:
        return HttpResponseForbidden("Unknown refund action.")
    try:
        handler(request.user)
        messages.success(request, f"Refund #{refund.pk} {action}d.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("courses:refund_list")
