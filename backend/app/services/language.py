import re

_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿ]+")


def detect_language(text: str) -> str:
    """Return 'ar' if text contains Arabic script, else 'en'."""
    if _ARABIC_RE.search(text):
        return "ar"
    return "en"
