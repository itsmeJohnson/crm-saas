import unicodedata

def normalize_email(raw: str | None) -> str | None:
    """
    Centralized email normalization function.
    - NFC normalizes Unicode string.
    - Trims surrounding whitespace.
    - Lowercases the entire address.
    - Does NOT strip subaddressing (+tags/dots).
    """
    if raw is None:
        return None
    normalized = unicodedata.normalize("NFC", raw).strip()
    if not normalized:
        return None
    return normalized.lower()
