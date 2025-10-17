import json
import os
from typing import Dict

from django.conf import settings
from django.utils import translation


def _load_json(path: str) -> Dict[str, str]:
    try:
        # Use utf-8-sig to gracefully handle files saved with BOM on Windows
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def load_translations(lang_code: str) -> Dict[str, str]:
    """
    Load and merge project-level and app-level i18n JSON files for given lang.
    Later files override earlier keys. Falls back to 'en' where missing.
    """
    base_dir = settings.BASE_DIR

    # Candidate folders to load from (project-wide + specific apps in use)
    sources = [
        os.path.join(base_dir, "i18n"),
        os.path.join(base_dir, "accounting", "i18n"),
    ]

    def build(lang: str) -> Dict[str, str]:
        merged: Dict[str, str] = {}
        for folder in sources:
            path = os.path.join(folder, f"{lang}.json")
            data = _load_json(path)
            if data:
                merged.update(data)
        return merged

    # First try requested language, then fallback to English
    translations = build(lang_code)
    if lang_code != "en":
        fallback = build("en")
        # Only add missing keys from fallback
        for k, v in fallback.items():
            translations.setdefault(k, v)

    return translations


def get_current_language(request) -> str:
    # Use Django's language cookie/session key when available
    lang = request.session.get(settings.LANGUAGE_COOKIE_NAME) or \
           request.session.get("django_language")
    if not lang:
        # Derive from settings.LANGUAGE_CODE (e.g., 'en-us' -> 'en')
        lang = (settings.LANGUAGE_CODE or "en").split("-")[0]
    return lang


def i18n_context(request):
    """
    Context processor: injects i18n translations and selected language/region.
    """
    lang = get_current_language(request)
    # Normalize like 'en-us' -> 'en'
    lang_short = lang.split("-")[0]
    translations = load_translations(lang_short)

    region = request.session.get("region", "US")

    # Ensure Django's translation is active for {% trans %}
    try:
        translation.activate(lang)
    except Exception:
        pass

    return {
        "i18n": translations,
        "current_language": lang_short,
        "current_region": region,
    }
