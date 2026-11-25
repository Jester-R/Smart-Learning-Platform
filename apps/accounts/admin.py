from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from .models import StudentProfile, TeacherProfile, User


class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields do not match.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text=(
            "Raw passwords are not stored. Use the password reset flow to change it."
        ),
    )

    class Meta:
        model = User
        fields = "__all__"

    def clean_password(self):
        return self.initial.get("password")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    list_display = (
        "email",
        "full_name",
        "role",
        "account_status",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = (
        "role",
        "account_status",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_verified",
    )
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("last_login", "date_joined", "updated_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone_number",
                    "date_of_birth",
                    "avatar",
                    "bio",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "role",
                    "account_status",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_verified",
                    "email_verified_at",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("student_profile", "teacher_profile")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "student_number",
        "user",
        "program",
        "year_level",
        "section",
        "enrollment_date",
    )
    list_filter = ("year_level", "program")
    search_fields = ("student_number", "user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("student_number", "created_at", "updated_at")


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = (
        "employee_number",
        "user",
        "department",
        "specialization",
        "hire_date",
    )
    list_filter = ("department",)
    search_fields = ("employee_number", "user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)
    readonly_fields = ("employee_number", "created_at", "updated_at")
