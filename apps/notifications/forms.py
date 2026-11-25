from django import forms

from apps.courses.models import Course

from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = (
            "title",
            "content",
            "audience",
            "course",
            "expires_at",
            "is_published",
        )
        widgets = {
            "content": forms.Textarea(attrs={"rows": 5}),
            "expires_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expires_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if user is not None and not user.is_admin_role:
            self.fields["course"].queryset = Course.objects.filter(teacher=user)
            self.fields["audience"].choices = [
                choice
                for choice in self.fields["audience"].choices
                if choice[0] != Announcement.Audience.TEACHERS
            ]
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")
