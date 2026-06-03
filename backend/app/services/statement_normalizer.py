"""
Statement normalization utilities.

Used by the parser for:
  - detect_statement_type  — classify the PDF as credit_card / bank_account / unknown
  - detect_section         — identify section headers (Payments, Deposits, etc.)

The AI cleanup service is the authority on noise filtering and sign correction.
These utilities are NOT applied after AI cleanup returns. They remain available
for testing, debugging, and any future deterministic fallback logic.

Sign convention (FinSight AI): expense = negative, income/credit = positive.
Nothing here logs raw PDF content or full account numbers — use redact().
"""

import logging
import re
from typing import Literal, Optional

logger = logging.getLogger(__name__)

StatementType = Literal["credit_card", "bank_account", "unknown"]


# ════════════════════════════════════════════════════════════════════════════
# Shared lightweight token regexes
# ════════════════════════════════════════════════════════════════════════════

_AMOUNT_TOKEN_RE = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}")
_DATE_TOKEN_RE = re.compile(
    r"(\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{1,2}"
    r"|\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)",
    re.IGNORECASE,
)
_LONG_DIGITS_RE = re.compile(r"\d{5,}")


def _has_amount(text: str) -> bool:
    return bool(_AMOUNT_TOKEN_RE.search(text or ""))


def _has_date(text: str) -> bool:
    return bool(_DATE_TOKEN_RE.search(text or ""))


def redact(text: str) -> str:
    """Collapse any run of 5+ digits so account/card numbers never reach logs.
    Phone fragments (e.g. 416-967-1111) and money amounts stay intact."""
    return _LONG_DIGITS_RE.sub("[redacted]", text or "")


def dedupe_key(transaction_date, description, amount) -> tuple:
    """Stable identity for de-duplication: date + normalized desc + |amount|."""
    desc = re.sub(r"\s+", " ", (description or "").strip().lower())
    try:
        amt = round(abs(float(amount)), 2)
    except (TypeError, ValueError):
        amt = 0.0
    return (str(transaction_date), desc, amt)


# ════════════════════════════════════════════════════════════════════════════
# 1. Statement type detection
# ════════════════════════════════════════════════════════════════════════════

_CC_INDICATORS = (
    "credit card", "minimum payment", "payment due date", "credit limit",
    "cash advance", "interest charged", "statement balance", "amount due",
    "new balance", "available credit", "previous balance",
)
_CC_WEAK = ("visa", "mastercard", "purchases")  # also appear on debit cards
_BANK_INDICATORS = (
    "chequing", "checking", "savings", "account activity", "opening balance",
    "closing balance", "deposits", "withdrawals", "interac", "direct deposit",
    "payroll", "overdraft", "transit number", "branch",
)


def detect_statement_type(text: str) -> StatementType:
    """
    Classify a statement as credit_card / bank_account / unknown from its text.
    Returns "unknown" when the evidence is weak or ambiguous.
    """
    t = (text or "").lower()
    cc = sum(1 for k in _CC_INDICATORS if k in t) + sum(0.5 for k in _CC_WEAK if k in t)
    bank = sum(1 for k in _BANK_INDICATORS if k in t)

    logger.info("detect_statement_type: cc_score=%.1f bank_score=%d", cc, bank)

    if cc >= 2 and cc > bank:
        return "credit_card"
    if bank >= 2 and bank > cc:
        return "bank_account"
    if cc >= 2 and cc == bank:
        # Credit-card terms are more specific than the generic bank ones.
        return "credit_card"
    return "unknown"


# ════════════════════════════════════════════════════════════════════════════
# 2. Section detection (header lines that influence sign)
# ════════════════════════════════════════════════════════════════════════════

# Canonical section keys grouped by the sign they imply.
_CREDIT_SECTIONS = {"payments", "credits", "deposits"}
_DEBIT_SECTIONS = {"purchases", "fees", "interest", "cash_advances",
                   "withdrawals", "card", "service_charges"}

# Anchored to a (mostly) standalone header line so we never swallow a real
# transaction whose description merely starts with one of these words.
_CC_SECTION_PATTERNS = [
    ("payments",       re.compile(r"^\s*payments?\s*:?\s*$", re.I)),
    ("credits",        re.compile(r"^\s*(other\s+credits|credits?)\s*:?\s*$", re.I)),
    ("cash_advances",  re.compile(r"^\s*cash\s+advances?\s*:?\s*$", re.I)),
    ("purchases",      re.compile(r"^\s*purchases?(\s+and\s+adjustments)?\s*:?\s*$", re.I)),
    ("fees",           re.compile(r"^\s*(fees?|fees?\s+and\s+charges)\s*:?\s*$", re.I)),
    ("interest",       re.compile(r"^\s*interest(\s+charges?)?\s*:?\s*$", re.I)),
]
_BANK_SECTION_PATTERNS = [
    ("deposits",        re.compile(r"^\s*(deposits?(\s+and\s+credits?)?|credits?)\s*:?\s*$", re.I)),
    ("withdrawals",     re.compile(r"^\s*(withdrawals?(\s+and\s+debits?)?|debits?)\s*:?\s*$", re.I)),
    ("service_charges", re.compile(r"^\s*(service\s+charges?|fees?)\s*:?\s*$", re.I)),
    ("transfers",       re.compile(r"^\s*transfers?\s*:?\s*$", re.I)),
    ("card",            re.compile(r"^\s*(card\s+(transactions|purchases)|point\s+of\s+sale)\s*:?\s*$", re.I)),
]


def detect_section(line: str, statement_type: str) -> Optional[str]:
    """Return a canonical section key if `line` is a section header, else None."""
    s = (line or "").strip()
    if not s or len(s) > 40 or _AMOUNT_TOKEN_RE.search(s):
        return None  # headers are short and carry no amount
    if statement_type == "credit_card":
        patterns = _CC_SECTION_PATTERNS
    elif statement_type == "bank_account":
        patterns = _BANK_SECTION_PATTERNS
    else:
        return None
    for key, pat in patterns:
        if pat.search(s):
            return key
    return None


# ════════════════════════════════════════════════════════════════════════════
# 3. Non-transaction (noise / metadata) filtering
# ════════════════════════════════════════════════════════════════════════════

# Phrases that are ALWAYS statement metadata, even when they carry an amount
# (e.g. "New Balance $1,234.56"). Deliberately does NOT include bare "fee",
# "interest", "payment", or "total" so real transaction rows survive.
_NOISE_PHRASE_RE = re.compile(
    r"""
    \b(
        previous\s*balance | new\s*balance | opening\s*balance | closing\s*balance
      | statement\s*balance | balance\s*(?:forward|brought\s*forward|carried\s*forward)
      | minimum\s*payment | minimum\s*(?:amount\s*)?due
      | payment\s*due\s*date | due\s*date
      | total\s*amount\s*due | amount\s*due
      | credit\s*limit | available\s*credit | available\s*balance | credit\s*available
      | annual\s*interest\s*rate | interest\s*rate
      | total\s*interest | total\s*fees
      | cash\s*back\s*summary | rewards?\s*summary | points?\s*summary | rewards?\s*balance
      | account\s*summary | statement\s*(?:period|date|summary)
      | sub\s*-?\s*total | grand\s*total
      | total\s*(?:purchases|payments|withdrawals|deposits|credits|debits|new\s*charges)
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Contact / instruction lines — noise UNLESS the line is itself a dated txn.
_CONTACT_RE = re.compile(
    r"""
    customer\s*service | lost\s*(?:or\s*|/)?\s*stolen | report\s*(?:lost|fraud)
  | online\s*banking | www\. | https?:// | \.com\b | \.ca\b
  | call\s*(?:us|toll) | 1[-\s]?800 | toll[-\s]?free
  | make\s*(?:cheque|check)\s*payable | mail\s*your\s*payment | remit\s*to
  | please\s*(?:pay|see) | to\s*pay\s*your\s*bill | payment\s*options
  | visit\s*(?:us|our) | contact\s*us
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A line that is essentially just digits/phone punctuation (no letters).
_PHONE_ONLY_RE = re.compile(r"^[\s+()0-9.\-]{7,}$")
_PAGE_RE = re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE)


def is_non_transaction_line(text: str) -> bool:
    """
    True when a line/row is statement metadata rather than a real transaction.

    Careful: a real transaction row that merely contains a phone number or the
    words fee/interest/payment is KEPT. Only summaries, balances, instructions,
    contact lines and headers are removed.
    """
    if not text or not text.strip():
        return True
    s = text.strip()
    low = s.lower()

    if _PHONE_ONLY_RE.match(s):
        return True
    if _PAGE_RE.match(s):
        return True
    if _NOISE_PHRASE_RE.search(low):
        return True
    # Contact/instruction text is noise only when it is not itself a dated txn.
    if _CONTACT_RE.search(low) and not (_has_date(s) and _has_amount(s)):
        return True
    return False


def is_valid_transaction_row(
    transaction_date, description, amount, raw_text: str = ""
) -> bool:
    """A candidate must have a date, a meaningful description, and an amount,
    and must not be obvious metadata."""
    if not transaction_date or not str(transaction_date).strip():
        return False
    if amount is None:
        return False
    try:
        float(amount)
    except (TypeError, ValueError):
        return False
    desc = (description or "").strip()
    if len(desc) < 2:
        return False
    if is_non_transaction_line(f"{desc} {raw_text or ''}"):
        return False
    return True


# ════════════════════════════════════════════════════════════════════════════
# 4. Sign normalization
# ════════════════════════════════════════════════════════════════════════════

_CR_MARKER_RE = re.compile(r"\bCR\b")
_DR_MARKER_RE = re.compile(r"\bDR\b")

_INTEREST_CHARGE_RE = re.compile(r"interest\s+(charge|charged|charges)", re.I)
_INTEREST_PAID_RE = re.compile(r"interest\s+(paid|earned)", re.I)

# e-Transfer direction — handled with regex because real Canadian bank PDFs
# concatenate the words with no space ("e-Transfersent"), a space ("e-Transfer
# sent"), or a hyphen ("e-Transfer-sent"). Simple string containment misses the
# no-space form because "sent" has a word character immediately before it.
# Pattern: optional "e-", then "transfer", then optional whitespace/hyphen, then
# the direction keyword.
_ETRANSFER_SENT_RE = re.compile(
    r"e-?transfer\s*-?\s*sent", re.I
)
_ETRANSFER_RECEIVED_RE = re.compile(
    r"e-?transfer\s*-?\s*(received|autodeposit)", re.I
)

# Direction by keyword. "credit" => positive (income), "debit" => negative.
_UNIVERSAL_CREDIT = (
    "refund", "reversal", "rebate", "cashback", "cash back",
    "payroll", "direct deposit", "auto deposit",
    "received from", "remittance", "credit memo",
)
_UNIVERSAL_DEBIT = (
    "purchase", "withdrawal", "cash advance", "atm", "nsf", "overdraft",
    "service charge", "service fee", "monthly fee", "account fee",
    "maintenance fee", "annual fee", "pos ", "point of sale",
    "bill payment", "pre-authorized", "preauthorized",
)
# On a credit card, a bare "payment" is money TOWARD the card => credit.
_CC_CREDIT = ("payment thank you", "thank you", "payment received",
              "autopay", "auto pay", "payment -", "payment")
_CC_DEBIT = ("fee", "interest", "purchase")
# On a bank account, "payment"/"cheque" is money OUT => debit. Checked first.
_BANK_DEBIT = ("debit", "payment", "withdrawal", "transfer to", "transfer out",
               "cheque", "check", "fee", "service")
_BANK_CREDIT = ("credit", "interest", "deposit", "transfer from", "transfer in")


def _keyword_direction(blob: str, statement_type: str) -> Optional[str]:
    # e-Transfer direction checked first with regex — catches all spacing/
    # hyphen variants including the concatenated "e-Transfersent" form.
    if _ETRANSFER_SENT_RE.search(blob):
        return "debit"
    if _ETRANSFER_RECEIVED_RE.search(blob):
        return "credit"

    # Interest phrasing — direction depends on charge vs paid.
    if _INTEREST_CHARGE_RE.search(blob):
        return "debit"
    if _INTEREST_PAID_RE.search(blob):
        return "credit"

    if any(k in blob for k in _UNIVERSAL_CREDIT):
        return "credit"
    if any(k in blob for k in _UNIVERSAL_DEBIT):
        return "debit"

    if statement_type == "credit_card":
        if any(k in blob for k in _CC_CREDIT):
            return "credit"
        if any(k in blob for k in _CC_DEBIT):
            return "debit"
    elif statement_type == "bank_account":
        # debit-first so "credit card payment" reads as money out, not a credit.
        if any(k in blob for k in _BANK_DEBIT):
            return "debit"
        if any(k in blob for k in _BANK_CREDIT):
            return "credit"
    return None


def normalize_amount_sign(
    amount: float,
    description: str,
    statement_type: str,
    section_context: Optional[str],
    raw_text: str,
    apply_type_default: bool = True,
) -> float:
    """
    Return `amount` with the correct sign (expense<0, income>0).

    Signal precedence (strongest first):
      1. Explicit CR / DR marker in raw_text.
      2. Section context (Payments/Deposits => +, Purchases/Withdrawals => -).
      3. Description keyword direction (type-aware).
      4. Statement-type default (credit_card => expense) — only when
         apply_type_default is True.
      5. Otherwise keep the parsed sign (logged for unknown statements).

    apply_type_default=False is used by the post-AI pass so it never flips a
    sign the parser already derived from section context.
    """
    mag = abs(float(amount))
    raw = raw_text or ""
    blob = f"{description or ''} {raw}".lower()

    # 1. Explicit markers
    if _CR_MARKER_RE.search(raw):
        return mag
    if _DR_MARKER_RE.search(raw):
        return -mag

    # 2. Section context
    sect = (section_context or "").lower()
    if sect in _CREDIT_SECTIONS:
        return mag
    if sect in _DEBIT_SECTIONS:
        return -mag

    # 3. Keyword direction
    direction = _keyword_direction(blob, statement_type)
    if direction == "credit":
        return mag
    if direction == "debit":
        return -mag

    # 4. Statement-type default
    if apply_type_default and statement_type == "credit_card":
        # Uncategorised rows on a credit-card statement are purchases.
        return -mag

    # 5. Undecided — keep parsed sign.
    if statement_type == "unknown":
        logger.warning(
            "normalize_amount_sign: undecided sign (type=unknown) for %r — keeping parsed sign",
            redact(description or "")[:60],
        )
    return float(amount)
