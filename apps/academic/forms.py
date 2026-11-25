from django import forms

from .models import AcademicCalendar, ClassSchedule, ExamSchedule


class ClassScheduleForm(forms.ModelForm):
    class Meta:
        model = ClassSchedule
        fields = (
            "course",
            "lecturer",
            "university",
            "day_of_week",
            "start_time",
            "end_time",
            "room",
            "notes",
            "is_active",
        )
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class AcademicCalendarForm(forms.ModelForm):
    class Meta:
        model = AcademicCalendar
        fields = (
            "university",
            "title",
            "event_type",
            "start_date",
            "end_date",
            "description",
            "is_published",
        )
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ExamScheduleForm(forms.ModelForm):
    class Meta:
        model = ExamSchedule
        fields = (
            "course",
            "exam",
            "title",
            "start_at",
            "end_at",
            "venue",
            "is_published",
            "remarks",
        )
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
