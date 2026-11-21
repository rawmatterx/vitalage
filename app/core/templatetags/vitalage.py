"""Small helpers for showing numbers in templates."""

from django import template

register = template.Library()


@register.filter
def one(x):
    """One decimal place: 61.84 -> "61.8"."""
    return "%.1f" % x


@register.filter
def signed(x):
    """One decimal place with a sign: 3.84 -> "+3.8", -0.04 -> "0.0"."""
    s = "%+.1f" % x
    return "0.0" if s in ("+0.0", "-0.0") else s


@register.filter
def two(x):
    """Two decimal places: 1.184 -> "1.18"."""
    return "%.2f" % x
