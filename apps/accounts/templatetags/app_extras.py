from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    if hasattr(mapping, "get"):
        return mapping.get(key)
    return None


@register.filter
def percentage(value, total):
    try:
        return round(float(value) / float(total) * 100, 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0
