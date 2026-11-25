from django import forms

from .models import FAQ, Feedback, SupportTicket, TicketMessage


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


class FAQForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ("category", "question", "answer", "is_published", "order")
        widgets = {"answer": forms.Textarea(attrs={"rows": 5})}


class SupportTicketForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ("subject", "description", "category", "priority")
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class TicketMessageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TicketMessage
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}


class FeedbackForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ("subject", "message", "rating")
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}
