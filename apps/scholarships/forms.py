from django import forms

from .models import Scholarship, ScholarshipApplication


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


class ScholarshipForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Scholarship
        fields = (
            "category",
            "university",
            "title",
            "description",
            "eligibility",
            "amount",
            "deadline",
            "application_link",
            "is_published",
        )
        widgets = {
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 5}),
            "eligibility": forms.Textarea(attrs={"rows": 4}),
        }


class ScholarshipApplicationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ScholarshipApplication
        fields = ("notes",)
        widgets = {"notes": forms.Textarea(attrs={"rows": 5})}
