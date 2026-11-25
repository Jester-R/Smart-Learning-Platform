from django import forms

from .models import Category, Course


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = (
            "code",
            "title",
            "price",
            "category",
            "teacher",
            "description",
            "objectives",
            "thumbnail",
            "status",
            "difficulty",
            "duration_hours",
            "passing_score",
            "certificate_enabled",
            "min_lesson_completion",
            "min_assignment_completion",
            "min_quiz_average",
            "is_featured",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "objectives": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None and not user.is_admin_role:
            self.fields.pop("teacher", None)
            self.fields.pop("is_featured", None)
        elif "teacher" in self.fields:
            self.fields["teacher"].queryset = self.fields[
                "teacher"
            ].queryset.filter(role="teacher")
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        teacher = cleaned.get("teacher")
        if self.user is not None and not self.user.is_admin_role:
            teacher = self.user
        if not teacher:
            self.add_error("teacher", "Select a teacher for this course.")
        return cleaned

    def save(self, commit=True):
        course = super().save(commit=False)
        if self.user is not None and not self.user.is_admin_role:
            course.teacher = self.user
        if commit:
            course.save()
            self.save_m2m()
        return course


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "description", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")
