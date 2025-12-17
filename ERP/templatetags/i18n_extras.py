from django import template

register = template.Library()


@register.filter
def i18n_get(translations, key):
    """
    Fetch a translation value from a flat dict by key string (supports dots).
    Usage: {{ i18n|i18n_get:'journal.entry.title'|default:'Journal Entry' }}
    """
    if not isinstance(translations, dict):
        return ""
    return translations.get(key, "")
