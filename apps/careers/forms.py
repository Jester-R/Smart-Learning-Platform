from pathlib import Path

from django import forms

from .models import ApplicationMessage, CVDocument, CompanyProfile, Job, JobApplication


def validate_cv_file(uploaded):
    allowed = {".pdf", ".doc", ".docx"}
    if Path(uploaded.name).suffix.lower() not in allowed:
        raise forms.ValidationError("Upload a PDF, DOC, or DOCX file.")
    if uploaded.size > 5 * 1024 * 1024:
        raise forms.ValidationError("CV files must be 5 MB or smaller.")
    return uploaded


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class CompanyProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = ("company_name", "description", "website", "contact_email", "logo")


class JobForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Job
        fields = (
            "title",
            "description",
            "responsibilities",
            "requirements",
            "location",
            "job_type",
            "salary_min",
            "salary_max",
            "application_deadline",
            "package",
        )
        widgets = {
            "application_deadline": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "description": forms.Textarea(attrs={"rows": 5}),
            "responsibilities": forms.Textarea(attrs={"rows": 4}),
            "requirements": forms.Textarea(attrs={"rows": 4}),
        }


class JobApplicationForm(StyledFormMixin, forms.ModelForm):
    cv_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx"}),
        help_text="Upload a new CV here, or choose one you already uploaded below.",
    )

    class Meta:
        model = JobApplication
        fields = ("cover_letter", "cv_document")
        widgets = {"cover_letter": forms.Textarea(attrs={"rows": 5})}

    def clean_cv_file(self):
        uploaded = self.cleaned_data.get("cv_file")
        return validate_cv_file(uploaded) if uploaded else uploaded


class CVUploadForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CVDocument
        fields = ("title", "file")
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. CV 2026"}),
            "file": forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx"}),
        }

    def clean_file(self):
        return validate_cv_file(self.cleaned_data["file"])


class ApplicationMessageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ApplicationMessage
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 4, "placeholder": "Write a message about the interview..."})}
