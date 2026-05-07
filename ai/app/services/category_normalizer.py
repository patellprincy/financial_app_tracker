import re


def normalize_category(category_name: str) -> str:
    normalized = category_name.lower().strip()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized)
    return normalized
