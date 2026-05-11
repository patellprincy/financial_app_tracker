import json
from groq import Groq
from ai.core.config import settings
from ai.services.category_normalizer import normalize_category

_FALLBACK = {
    "transaction_type": "expense",
    "category_name": "Other",
    "normalized_category": "other",
    "confidence": 0.3,
    "reason": "Fallback due to invalid AI response.",
}

_VALID_TRANSACTION_TYPES = {"income", "expense"}

_PREFERRED_EXPENSE = (
    "Food & Drinks, Groceries, Transport, Shopping, Bills, Entertainment, "
    "Health, Education, Travel, Rent, Insurance, Subscriptions, Other"
)
_PREFERRED_INCOME = (
    "Salary, Benefits, Transfer In, Refund, Interest Income, "
    "Rewards, Investment Income, Other Income"
)

_PROMPT_TEMPLATE = """You are a financial transaction classifier.

Classify this transaction and return:
1. transaction_type: "income" (money received) or "expense" (money spent)
2. category_name: a broad, reusable category (1–3 words)
3. confidence: float 0.0–1.0
4. reason: one sentence

Classification signals in priority order:
1. Merchant name — PRIMARY signal
2. Amount pattern — SECONDARY signal (large round amounts can suggest payroll)
3. Notes — SUPPLEMENTARY only, use if present, not required
4. If transaction_type is unclear, default to "expense"

Preferred expense categories:
{preferred_expense}

Preferred income categories:
{preferred_income}

Use a preferred category when it fits. If none fit, create a broad reusable one (e.g. Pet Care, Fitness, Home Services, Childcare, Professional Fees). Never use a merchant or brand name as the category.

Examples:
Starbucks → expense, Food & Drinks
Tim Hortons → expense, Food & Drinks
McDonald's → expense, Food & Drinks
Uber → expense, Transport
Shell → expense, Transport
Netflix → expense, Entertainment
Walmart → expense, Groceries
Rent Payment → expense, Rent
Phone Bill → expense, Bills
Insurance Payment → expense, Insurance
Tuition Payment → expense, Education
PetSmart → expense, Pet Care
GoodLife Fitness → expense, Fitness
Payroll Deposit → income, Salary
Employer Deposit → income, Salary
Government Payment → income, Benefits
E-transfer Received → income, Transfer In
Refund from Amazon → income, Refund
Interest Paid → income, Interest Income
Cashback Reward → income, Rewards
Dividend Payment → income, Investment Income

Merchant: {merchant}
Amount: {amount}
Notes: {notes}"""


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

    prompt = _PROMPT_TEMPLATE.format(
        preferred_expense=_PREFERRED_EXPENSE,
        preferred_income=_PREFERRED_INCOME,
        merchant=merchant,
        amount=amount,
        notes=notes if notes else "not provided",
    )

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
