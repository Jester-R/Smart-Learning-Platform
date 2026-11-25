from django.contrib import admin
from django.db.models import Count

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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "course_count", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_course_count=Count("courses"))

    @admin.display(description="Courses", ordering="_course_count")
    def course_count(self, obj):
        return obj._course_count


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "price",
        "teacher",
        "category",
        "status",
        "difficulty",
        "certificate_enabled",
        "created_at",
    )
    list_filter = ("status", "difficulty", "category", "certificate_enabled")
    search_fields = ("code", "title", "description", "teacher__email", "teacher__first_name", "teacher__last_name")
    autocomplete_fields = ("teacher",)
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at", "published_at")
    fieldsets = (
        (
            "Course information",
            {
                "fields": (
                    "code",
                    "title",
                    "price",
                    "slug",
                    "category",
                    "teacher",
                    "description",
                    "objectives",
                    "thumbnail",
                )
            },
        ),
        (
            "Delivery",
            {
                "fields": (
                    "status",
                    "difficulty",
                    "duration_hours",
                    "is_featured",
                )
            },
        ),
        (
            "Completion and certificates",
            {
                "fields": (
                    "passing_score",
                    "certificate_enabled",
                    "min_lesson_completion",
                    "min_assignment_completion",
                    "min_quiz_average",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at", "published_at")}),
    )


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "course",
        "status",
        "final_grade",
        "enrolled_at",
        "completed_at",
    )
    list_filter = ("status", "course")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "course__code",
        "course__title",
    )
    autocomplete_fields = ("student", "course")
    readonly_fields = ("enrolled_at", "updated_at")
    list_select_related = ("student", "course")


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "sort_order", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "description")
    prepopulated_fields = {"code": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "course",
        "plan",
        "amount",
        "method",
        "status",
        "reference",
        "verified_by",
        "paid_at",
        "created_at",
    )
    list_filter = ("status", "method")
    search_fields = (
        "reference",
        "student__email",
        "student__first_name",
        "student__last_name",
        "course__code",
        "course__title",
    )
    autocomplete_fields = (
        "student",
        "course",
        "plan",
        "enrollment",
        "method",
        "verified_by",
    )
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("student", "course", "method", "verified_by")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "is_active",
        "sort_order",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "description", "features")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(StudentSubscription)
class StudentSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "plan",
        "start_date",
        "end_date",
        "status",
        "payment",
    )
    list_filter = ("status", "plan")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "plan__name",
    )
    autocomplete_fields = ("student", "plan", "payment")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("student", "plan", "payment")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "payment", "issued_at", "created_at")
    search_fields = ("number", "payment__reference", "payment__student__email")
    autocomplete_fields = ("payment",)
    readonly_fields = ("number", "created_at", "updated_at")
    list_select_related = ("payment__student", "payment__course")


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        "payment",
        "amount",
        "status",
        "requested_by",
        "processed_by",
        "processed_at",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "payment__reference",
        "payment__student__email",
        "reason",
    )
    autocomplete_fields = ("payment", "requested_by", "processed_by")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("payment__student", "requested_by", "processed_by")
