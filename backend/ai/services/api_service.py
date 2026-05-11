import json
from groq import Groq
from ai.core.config import settings
from ai.services.category_normalizer import normalize_category
from ai.services.prompt_loader import get_classification_prompt_template

_FALLBACK = {
    "transaction_type": "expense",
    "category_name": "Other",
    "normalized_category": "other",
    "confidence": 0.3,
    "reason": "Fallback due to invalid AI response.",
}

_VALID_TRANSACTION_TYPES = {"income", "expense"}


def build_prompt(merchant: str, amount: float, notes: str | None = None) -> str:
    template = get_classification_prompt_template()
    return template.format(
        merchant=merchant,
        amount=amount,
        notes=notes or "No notes provided",
    )


def _validate_category(category_name: str) -> str:
    category_name = (category_name or "").strip()

    if not category_name:
        return "Other"

    words = category_name.split()

    if len(words) > 3:
        category_name = " ".join(words[:3])

    category_name = category_name.replace("&", "and")

    return category_name


def classify_transaction(merchant: str, amount: float, notes: str | None) -> dict:
    client = Groq(api_key=settings.groq_api_key)

    prompt = build_prompt(merchant=merchant, amount=amount, notes=notes)

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": "You are a financial transaction classifier. Always respond with a valid JSON object."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content)

        transaction_type = str(data.get("transaction_type", "")).strip().lower()
        if transaction_type not in _VALID_TRANSACTION_TYPES:
            transaction_type = "expense"

        category_name = _validate_category(str(data.get("category_name", "")))

        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5

        reason = str(data.get("reason", "")).strip() or "Classified based on merchant name."

        return {
            "transaction_type": transaction_type,
            "category_name": category_name,
            "normalized_category": normalize_category(category_name),
            "confidence": round(min(max(confidence, 0.0), 1.0), 2),
            "reason": reason,
        }

    except Exception as e:
        print(f"[classify_transaction] error: {e}")
        return _FALLBACK
