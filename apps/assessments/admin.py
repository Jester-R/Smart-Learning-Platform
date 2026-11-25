from django.contrib import admin

from .models import (
    Assignment,
    Choice,
    Exam,
    ExamAnswer,
    ExamAttempt,
    ExamChoice,
    ExamQuestion,
    Grade,
    Question,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    Submission,
)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


class ExamChoiceInline(admin.TabularInline):
    model = ExamChoice
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "time_limit_minutes",
        "passing_score",
        "max_attempts",
        "is_published",
        "opens_at",
        "closes_at",
    )
    list_filter = ("is_published", "show_results", "course")
    search_fields = ("title", "description", "course__code", "course__title")
    autocomplete_fields = ("course", "created_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "quiz", "question_type", "points", "order")
    list_filter = ("question_type", "quiz__course")
    search_fields = ("text", "quiz__title", "quiz__course__code")
    autocomplete_fields = ("quiz",)
    inlines = [ChoiceInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "quiz",
        "attempt_number",
        "score",
        "max_score",
        "status",
        "started_at",
        "submitted_at",
    )
    list_filter = ("status", "quiz__course")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "quiz__title",
    )
    autocomplete_fields = ("quiz", "student")
    readonly_fields = (
        "started_at",
        "submitted_at",
        "score",
        "max_score",
        "status",
    )


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question",
        "selected_choice",
        "is_correct",
        "points_awarded",
    )
    list_filter = ("is_correct",)
    autocomplete_fields = ("attempt", "question")
    readonly_fields = ("attempt", "question", "selected_choice")


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "time_limit_minutes",
        "passing_score",
        "max_attempts",
        "is_published",
        "opens_at",
        "closes_at",
    )
    list_filter = ("is_published", "show_results", "course")
    search_fields = ("title", "description", "course__code", "course__title")
    autocomplete_fields = ("course", "created_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "exam", "question_type", "points", "order")
    list_filter = ("question_type", "exam__course")
    search_fields = ("text", "exam__title", "exam__course__code")
    autocomplete_fields = ("exam",)
    inlines = [ExamChoiceInline]


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam",
        "attempt_number",
        "score",
        "max_score",
        "status",
        "started_at",
        "submitted_at",
    )
    list_filter = ("status", "exam__course")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "exam__title",
    )
    autocomplete_fields = ("exam", "student")
    readonly_fields = (
        "started_at",
        "submitted_at",
        "score",
        "max_score",
        "status",
    )


@admin.register(ExamAnswer)
class ExamAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question",
        "selected_choice",
        "is_correct",
        "points_awarded",
    )
    list_filter = ("is_correct",)
    autocomplete_fields = ("attempt", "question")
    readonly_fields = ("attempt", "question", "selected_choice")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "due_at",
        "max_points",
        "allow_late_submission",
        "is_published",
        "created_by",
    )
    list_filter = ("is_published", "allow_late_submission", "course")
    search_fields = ("title", "description", "course__code", "course__title")
    autocomplete_fields = ("course", "created_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "assignment",
        "status",
        "score",
        "is_late",
        "submitted_at",
        "graded_by",
    )
    list_filter = ("status", "is_late", "assignment__course")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "assignment__title",
    )
    autocomplete_fields = ("assignment", "student", "graded_by")
    readonly_fields = ("submitted_at", "updated_at", "resubmission_count")
    list_select_related = ("assignment", "student", "graded_by")


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "course",
        "component",
        "title",
        "score",
        "max_score",
        "weight",
        "graded_at",
    )
    list_filter = ("component", "course")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "course__code",
        "course__title",
        "title",
    )
    autocomplete_fields = ("student", "course", "graded_by")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("student", "course", "graded_by")
