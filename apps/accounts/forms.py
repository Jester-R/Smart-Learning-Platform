from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password

from .models import PlatformConfiguration, StudentProfile, User


class PlatformConfigurationForm(forms.ModelForm):
    gemini_api_key = forms.CharField(
        label="Gemini API token",
        required=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "new-password"},
            render_value=False,
        ),
        help_text="A new token replaces the saved token. The saved value is never displayed.",
    )
    clear_gemini_api_key = forms.BooleanField(
        label="Remove the saved token and use the server environment token, if set",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = PlatformConfiguration
        fields = ("ai_assistant_enabled", "video_downloads_enabled")
        labels = {
            "ai_assistant_enabled": "Enable Gemini AI Assistant",
            "video_downloads_enabled": "Allow downloads of uploaded lesson videos",
        }
        widgets = {
            "ai_assistant_enabled": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "video_downloads_enabled": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("clear_gemini_api_key") and cleaned_data.get("gemini_api_key"):
            self.add_error(
                "gemini_api_key",
                "Enter a new token or choose to clear the saved token, not both.",
            )
        return cleaned_data

    def save(self, commit=True):
        configuration = super().save(commit=False)
        api_key = self.cleaned_data.get("gemini_api_key", "").strip()
        if api_key:
            configuration.set_gemini_api_key(api_key)
        elif self.cleaned_data.get("clear_gemini_api_key"):
            configuration.set_gemini_api_key("")
        if commit:
            configuration.save()
        return configuration


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )


class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    account_type = forms.ChoiceField(
        label="Account type",
        choices=(
            (User.Role.STUDENT, "Student"),
            (User.Role.COMPANY, "Company / Employer"),
            (User.Role.INSTRUCTOR, "Course Creator / Instructor"),
        ),
        initial=User.Role.STUDENT,
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data.get("account_type") or User.Role.STUDENT
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "phone_number",
            "date_of_birth",
            "avatar",
            "bio",
        )
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "bio": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "avatar":
                field.widget.attrs.setdefault("class", "form-control")
            elif not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-control")


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = (
            "program",
            "year_level",
            "section",
            "guardian_name",
            "guardian_phone",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={"class": "form-control", "autocomplete": "email"}
        ),
    )


class PasswordResetConfirmForm(forms.Form):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "new-password"}
        ),
        validators=[validate_password],
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "new-password"}
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            self.add_error("new_password2", "The two password fields do not match.")
        return cleaned_data
