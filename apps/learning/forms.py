from django import forms
from django.core.exceptions import ValidationError

from apps.courses.models import Course, Enrollment

from .models import AttendanceRecord, LearningMaterial, Lesson, extract_youtube_video_id


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = (
            "title",
            "chapter",
            "youtube_url",
            "duration_minutes",
            "order",
            "is_published",
            "description",
            "content",
            "video_url",
            "video_file",
            "video_downloadable",
        )
        labels = {
            "chapter": "Chapter / Module",
            "youtube_url": "YouTube Video URL",
            "duration_minutes": "Duration (minutes)",
            "order": "Lesson Order Number",
            "is_published": "Publish immediately (visible to students)",
            "content": "Lesson Notes / Reading Content",
            "video_downloadable": "Allow students to download this uploaded video",
        }
        help_texts = {
            "youtube_url": (
                "Supported: youtube.com/watch?v=ID, youtu.be/ID, "
                "youtube.com/embed/ID, or youtube.com/shorts/ID."
            ),
            "chapter": "Group this video under a chapter or section (e.g. 'Chapter 1: Getting Started').",
            "duration_minutes": "Approximate length of the video in minutes.",
        }
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "e.g. Introduction to Python Functions"}),
            "chapter": forms.TextInput(attrs={"placeholder": "e.g. Chapter 1: Fundamentals"}),
            "youtube_url": forms.URLInput(
                attrs={
                    "placeholder": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "id": "id_youtube_url",
                }
            ),
            "duration_minutes": forms.NumberInput(attrs={"min": "0", "placeholder": "15"}),
            "order": forms.NumberInput(attrs={"min": "1"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Provide a clear summary of what students will learn in this video..."}
            ),
            "content": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Additional reading notes, code snippets, or reference links..."}
            ),
        }

    def __init__(self, *args, course=None, **kwargs):
        self.course = course
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean_youtube_url(self):
        url = self.cleaned_data.get("youtube_url", "").strip()
        if url:
            video_id = extract_youtube_video_id(url)
            if not video_id:
                raise ValidationError(
                    "Invalid YouTube URL. Please provide a valid link from youtube.com or youtu.be "
                    "(e.g., https://www.youtube.com/watch?v=VIDEO_ID, https://youtu.be/VIDEO_ID, "
                    "or https://www.youtube.com/shorts/VIDEO_ID)."
                )
        return url

    def clean_order(self):
        order = self.cleaned_data.get("order")
        if order is None:
            order = 1
        if self.course:
            queryset = self.course.lessons.filter(order=order)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError(
                    f"Lesson #{order} already exists in this course. Please choose another order number."
                )
        return order

    def save(self, commit=True):
        lesson = super().save(commit=False)
        if self.course:
            lesson.course = self.course
        if commit:
            lesson.save()
        return lesson


class VideoLessonForm(forms.ModelForm):
    """Specialized form specifically for managing YouTube video lessons."""

    class Meta:
        model = Lesson
        fields = (
            "course",
            "youtube_url",
            "video_file",
            "video_downloadable",
            "title",
            "chapter",
            "duration_minutes",
            "order",
            "is_published",
            "description",
            "content",
        )
        labels = {
            "course": "Target Course",
            "youtube_url": "YouTube Video URL",
            "video_file": "Upload Video File (MP4, WebM, MOV...)",
            "video_downloadable": "Allow students to download this uploaded video",
            "title": "Video Lesson Title",
            "chapter": "Chapter / Section Name",
            "duration_minutes": "Duration (minutes)",
            "order": "Order in Course",
            "is_published": "Publish lesson (visible to enrolled students)",
            "description": "Video Description",
            "content": "Lesson Notes / Resources (Optional)",
        }
        help_texts = {
            "youtube_url": "Paste any standard YouTube video, Shorts, or youtu.be link.",
            "chapter": "Optional chapter name for structuring the course playlist.",
            "video_file": "Optional: upload a video file from your computer instead of (or in addition to) a YouTube link.",
        }
        widgets = {
            "youtube_url": forms.URLInput(
                attrs={
                    "placeholder": "https://www.youtube.com/watch?v=... or https://youtu.be/...",
                    "id": "id_youtube_url",
                    "autocomplete": "off",
                }
            ),
            "title": forms.TextInput(attrs={"placeholder": "e.g. Master Loops in Python"}),
            "chapter": forms.TextInput(attrs={"placeholder": "e.g. Chapter 2: Control Flow"}),
            "duration_minutes": forms.NumberInput(attrs={"min": "0", "placeholder": "e.g. 20"}),
            "order": forms.NumberInput(attrs={"min": "1"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "What will students learn in this video lesson?"}
            ),
            "content": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Supplementary notes, timestamps, or practice exercises..."}
            ),
        }

    def __init__(self, *args, user=None, course=None, **kwargs):
        self.user = user
        self.preset_course = course
        super().__init__(*args, **kwargs)

        # youtube_url is optional when a video file is uploaded instead
        self.fields["youtube_url"].required = False

        if self.preset_course:
            self.fields["course"].initial = self.preset_course
            self.fields["course"].widget = forms.HiddenInput()
            self.fields["course"].required = False
        elif self.user:
            courses_qs = Course.objects.all()
            if not (self.user.is_superuser or getattr(self.user, "role", None) == "admin"):
                courses_qs = courses_qs.filter(teacher=self.user)
            self.fields["course"].queryset = courses_qs
            self.fields["course"].empty_label = "--- Select Course ---"
            self.fields["course"].widget.attrs.setdefault("class", "form-select")

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            elif not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.setdefault("class", "form-control")

    def clean_youtube_url(self):
        url = self.cleaned_data.get("youtube_url", "").strip()
        if not url:
            return url
        video_id = extract_youtube_video_id(url)
        if not video_id:
            raise ValidationError(
                "Invalid YouTube URL. Please enter a valid YouTube video link (e.g. "
                "https://www.youtube.com/watch?v=VIDEO_ID, https://youtu.be/VIDEO_ID, or "
                "https://www.youtube.com/shorts/VIDEO_ID)."
            )
        return url

    def clean(self):
        cleaned = super().clean()
        course = self.preset_course or cleaned.get("course")
        if not course:
            raise ValidationError({"course": "Please select a course for this lesson."})

        youtube_url = cleaned.get("youtube_url")
        video_file = cleaned.get("video_file")
        has_existing_file = bool(
            self.instance.pk and self.instance.video_file
        )
        if not youtube_url and not video_file and not has_existing_file:
            raise ValidationError(
                "Provide a YouTube video URL or upload a video file for this lesson."
            )

        order = cleaned.get("order")
        if course and order is not None:
            qs = course.lessons.filter(order=order)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    {"order": f"Lesson #{order} already exists in '{course.title}'. Choose a different order."}
                )
        return cleaned

    def save(self, commit=True):
        lesson = super().save(commit=False)
        if self.preset_course:
            lesson.course = self.preset_course
        if commit:
            lesson.save()
        return lesson


class LearningMaterialForm(forms.ModelForm):
    class Meta:
        model = LearningMaterial
        fields = (
            "title",
            "description",
            "material_type",
            "file",
            "external_url",
            "lesson",
            "is_downloadable",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, course=None, **kwargs):
        self.course = course
        super().__init__(*args, **kwargs)
        if course:
            self.fields["lesson"].queryset = course.lessons.all()
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("file") and not cleaned.get("external_url"):
            raise forms.ValidationError(
                "Attach a file or provide an external URL for this material."
            )
        return cleaned

    def save(self, commit=True):
        material = super().save(commit=False)
        if self.course:
            material.course = self.course
        if commit:
            material.save()
        return material


class AttendanceRecordForm(forms.ModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ("student", "course", "date", "status", "remarks")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, courses=None, students=None, **kwargs):
        super().__init__(*args, **kwargs)
        if courses is not None:
            self.fields["course"].queryset = courses
        if students is not None:
            self.fields["student"].queryset = students
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        course = cleaned.get("course")
        if student and course:
            enrolled = Enrollment.objects.filter(student=student, course=course).exists()
            if not enrolled:
                raise ValidationError("Select a student who is enrolled in this course.")
        return cleaned
