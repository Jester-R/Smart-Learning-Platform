from django import forms

from .models import ForumComment, ForumPost, ForumReport


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


class ForumPostForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ForumPost
        fields = ("category", "title", "body")
        widgets = {"body": forms.Textarea(attrs={"rows": 6})}


class ForumCommentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ForumComment
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 3})}


class ForumReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ForumReport
        fields = ("reason",)
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}
