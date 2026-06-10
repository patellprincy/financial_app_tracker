"""
Merchant/description normalization for the classification cache.

Converts a raw bank statement description into a stable, lowercase cache key
by stripping store numbers, URL suffixes, reference codes, and noise words.
"""

import re

# Recognized TLDs — used to detect and extract the brand name from URL tokens.
_COMMON_TLDS = frozenset({
    "com", "ca", "net", "org", "io", "co", "app",
    "gov", "edu", "uk", "us", "au", "de", "fr",
})

# e.g. "AMAZON.CA", "HELP.UBER.COM", "PAY.APPLE.COM"
_URL_RE = re.compile(
    r"\b\w+(?:\.\w+)*\.(?:" + "|".join(_COMMON_TLDS) + r")\b",
    re.IGNORECASE,
)

# e.g. "WALMART STORE 3154", "SHOP 99", "BRANCH 01", "NO. 42", "LOCATION 7"
_STORE_NUM_RE = re.compile(
    r"\b(?:store|shop|location|branch|no\.?)\s*\d+\b",
    re.IGNORECASE,
)

# e.g. "#4421", "#ON-EAST-12"
_HASH_REF_RE = re.compile(r"#\S+")

# Standalone digit-only tokens (store IDs, reference numbers)
_NUM_ONLY_RE = re.compile(r"\b\d+\b")

# Company-type suffixes and generic trip/routing words that follow the brand.
# Kept minimal — only words that virtually never appear AS the merchant name.
_NOISE_WORDS_RE = re.compile(
    r"\b(?:inc|ltd|corp|llc|trip)\b",
    re.IGNORECASE,
)

# Anything that isn't a letter, digit, space, or hyphen.
_SPECIAL_CHARS_RE = re.compile(r"[^\w\s-]")

_WHITESPACE_RE = re.compile(r"\s+")

# Maximum number of words to keep — limits key length while preserving
# multi-word brands like "TIM HORTONS" or "BEST BUY".
_MAX_WORDS = 3


def _url_to_brand(match: re.Match) -> str:
    """
    Replace a URL-like token with just the brand component.

    "HELP.UBER.COM"  → " uber "
    "AMAZON.CA"      → " amazon "
    "PAY.APPLE.COM"  → " apple "
    """
    token = match.group(0).lower()
    parts = token.split(".")
    # Strip TLD components from the right until a non-TLD part remains.
    while parts and parts[-1] in _COMMON_TLDS:
        parts.pop()
    return (" " + parts[-1] + " ") if parts else " "


def normalize_merchant(raw: str) -> str:
    """
    Normalize a raw merchant/description string to a stable cache key.

    Examples:
        "STARBUCKS #4421 TORONTO"     → "starbucks toronto"
        "WALMART STORE 3154"          → "walmart"
        "UBER TRIP HELP.UBER.COM"     → "uber"
        "AMAZON.CA"                   → "amazon"
        "TIM HORTONS #1234"           → "tim hortons"
        "PAYPAL *SPOTIFY"             → "paypal spotify"
        "BEST BUY INC"                → "best buy"

    Returns an empty string for blank/None input — callers should treat an
    empty normalized key as always-uncached (never save, always classify).
    """
    if not raw or not raw.strip():
        return ""

    text = raw.strip()

    # "PAYPAL *SPOTIFY" → "PAYPAL  SPOTIFY"
    text = text.replace("*", " ")

    # Replace URLs with their extracted brand component.
    text = _URL_RE.sub(_url_to_brand, text)

    # "WALMART STORE 3154" → "WALMART " (remove keyword+number together before
    # the generic number pass so "DOLLAR STORE" is left intact).
    text = _STORE_NUM_RE.sub(" ", text)

    # "#4421" → " "
    text = _HASH_REF_RE.sub(" ", text)

    # Remove any remaining standalone digit tokens.
    text = _NUM_ONLY_RE.sub(" ", text)

    # Lowercase before word-boundary matching.
    text = text.lower()

    # Remove noise suffixes ("INC", "LTD", "TRIP", …).
    text = _NOISE_WORDS_RE.sub(" ", text)

    # Strip punctuation (hyphens kept for "CO-OP" etc.).
    text = _SPECIAL_CHARS_RE.sub(" ", text)

    # Collapse runs of whitespace.
    text = _WHITESPACE_RE.sub(" ", text).strip()

    # Deduplicate words (handles "uber uber" → "uber") then take first N.
    words = list(dict.fromkeys(text.split()))[:_MAX_WORDS]
    return " ".join(words)
