from django import template

register = template.Library()

@register.filter
def split(value, key):
    """Splits the string by the given key."""
    return value.split(key)
