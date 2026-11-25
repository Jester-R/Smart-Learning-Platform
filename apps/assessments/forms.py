from django import forms

from .models import (
    Assignment,
    Exam,
    ExamChoice,
    ExamQuestion,
    Question,
    Quiz,
    Submission,
)


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = (
            "title",
            "description",
            "instructions",
            "attachment",
            "due_at",
            "max_points",
            "allow_late_submission",
            "is_published",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "instructions": forms.Textarea(attrs={"rows": 3}),
            "due_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ("text_response", "file")
        widgets = {"text_response": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("text_response") and not cleaned.get("file"):
            raise forms.ValidationError("Provide a written response or attach a file.")
        return cleaned


class GradeSubmissionForm(forms.Form):
    score = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0)
    feedback = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"})
    )
    status = forms.ChoiceField(choices=Submission.Status.choices, initial=Submission.Status.GRADED)
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))

    def __init__(self, *args, max_points=100, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["score"].widget.attrs.setdefault("class", "form-control")
        self.fields["score"].max_value = max_points
        self.fields["status"].widget.attrs.setdefault("class", "form-select")
        self.fields["reason"].label = "Reason for grade entry or change"

    def clean_score(self):
        score = self.cleaned_data["score"]
        if self.fields["score"].max_value is not None and score > self.fields["score"].max_value:
            raise forms.ValidationError("Score exceeds the maximum points.")
        return score


class AssessmentFormMixin(forms.ModelForm):
    class Meta:
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 3}),
            "opens_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "closes_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("opens_at", "closes_at"):
            if name in self.fields:
                self.fields[name].input_formats = ["%Y-%m-%dT%H:%M"]
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        opens = cleaned.get("opens_at")
        closes = cleaned.get("closes_at")
        if opens and closes and closes <= opens:
            self.add_error("closes_at", "Closing time must be after opening time.")
        return cleaned


class QuizForm(AssessmentFormMixin):
    class Meta(AssessmentFormMixin.Meta):
        model = Quiz
        fields = (
            "title",
            "description",
            "instructions",
            "time_limit_minutes",
            "passing_score",
            "max_attempts",
            "opens_at",
            "closes_at",
            "show_results",
            "shuffle_questions",
            "is_published",
        )


class ExamForm(AssessmentFormMixin):
    class Meta(AssessmentFormMixin.Meta):
        model = Exam
        fields = (
            "title",
            "description",
            "instructions",
            "time_limit_minutes",
            "passing_score",
            "max_attempts",
            "opens_at",
            "closes_at",
            "show_results",
            "shuffle_questions",
            "is_published",
        )


OPTION_FIELDS = ("option_a", "option_b", "option_c", "option_d")


class QuestionForm(forms.Form):
    question_type = forms.ChoiceField(
        choices=Question._meta.get_field("question_type").choices
    )
    text = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    points = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0.01)
    order = forms.IntegerField(min_value=1)
    option_a = forms.CharField(required=False, max_length=500)
    option_b = forms.CharField(required=False, max_length=500)
    option_c = forms.CharField(required=False, max_length=500)
    option_d = forms.CharField(required=False, max_length=500)
    correct_option = forms.ChoiceField(
        choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
        required=False,
    )
    correct_answer = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    explanation = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        if instance is not None:
            self.fields["question_type"].initial = instance.question_type
            self.fields["text"].initial = instance.text
            self.fields["points"].initial = instance.points
            self.fields["order"].initial = instance.order
            self.fields["correct_answer"].initial = instance.correct_answer
            self.fields["explanation"].initial = instance.explanation
            choices = list(instance.choices.all())
            for index, field in enumerate(OPTION_FIELDS):
                if index < len(choices):
                    self.fields[field].initial = choices[index].text
                    if choices[index].is_correct:
                        self.fields["correct_option"].initial = "ABCD"[index]
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        question_type = cleaned.get("question_type")
        option_values = [
            cleaned.get(field, "").strip() for field in OPTION_FIELDS
        ]
        if question_type == "multiple_choice":
            provided = [value for value in option_values if value]
            if len(provided) < 2:
                self.add_error("option_a", "Provide at least two answer options.")
            correct = cleaned.get("correct_option")
            if not correct:
                self.add_error("correct_option", "Select the correct option.")
            elif not cleaned.get(f"option_{correct.lower()}"):
                self.add_error("correct_option", "The selected correct option is empty.")
        elif question_type == "true_false":
            if cleaned.get("correct_option") not in ("A", "B"):
                self.add_error("correct_option", "Select True or False.")
        elif question_type == "short_answer":
            if not cleaned.get("correct_answer", "").strip():
                self.add_error("correct_answer", "An expected answer is required.")
        return cleaned

    def choice_rows(self):
        question_type = self.cleaned_data["question_type"]
        if question_type == "multiple_choice":
            correct = self.cleaned_data.get("correct_option", "")
            rows = []
            for index, field in enumerate(OPTION_FIELDS):
                text = self.cleaned_data.get(field, "").strip()
                if text:
                    rows.append((text, "ABCD"[index] == correct, len(rows) + 1))
            return rows
        if question_type == "true_false":
            correct = self.cleaned_data.get("correct_option")
            return [("True", correct == "A", 1), ("False", correct == "B", 2)]
        return []

    def save(self, parent, question_model, choice_model):
        data = self.cleaned_data
        question = self.instance or question_model()
        if self.instance is None:
            if isinstance(parent, Quiz):
                question.quiz = parent
            elif isinstance(parent, Exam):
                question.exam = parent
        question.question_type = data["question_type"]
        question.text = data["text"]
        question.points = data["points"]
        question.order = data["order"]
        question.explanation = data.get("explanation", "")
        question.correct_answer = data.get("correct_answer", "")
        question.save()
        if self.instance is not None:
            question.choices.all().delete()
        for text, is_correct, order in self.choice_rows():
            choice_model.objects.create(
                question=question, text=text, is_correct=is_correct, order=order
            )
        return question
