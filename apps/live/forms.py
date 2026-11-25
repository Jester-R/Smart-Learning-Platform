from django import forms

from apps.accounts.permissions import is_admin
from apps.courses.models import Course

from .models import LiveSession


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


class LiveSessionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LiveSession
        fields = (
            "course",
            "title",
            "description",
            "youtube_url",
            "starts_at",
            "ends_at",
            "status",
            "is_published",
        )
        widgets = {
            "starts_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "ends_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and not is_admin(user):
            self.fields["course"].queryset = Course.objects.filter(teacher=user)
