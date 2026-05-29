"""
Multi-strategy PDF bank statement parser.

Strategies tried in order:
  1. Table extraction  — pdfplumber.extract_tables() with flexible header detection.
  2. Text-line         — per-line regex anchored at a date token (single-line transactions).
  3. Block / state-machine — tracks last_seen_date across lines; handles multi-line
                             descriptions and date-less same-day transactions (e.g. RBC,
                             where the date prints only once per day).

Strategies 2 and 3 always both run; results are merged then deduped.
Returns ParseResult; never writes to the database.

Tested against:
  RBC  — DDMon date (no sep), date printed once per day group, Interac ref codes
  TD   — MMM DD date, CR/DR amount suffixes, table-based PDFs
  Scotiabank — DD-MON date, CR/DR suffixes
  BMO  — "Mon DD, YYYY" or table PDFs
  Chase / Wells Fargo (US) — MM/DD or MM/DD/YYYY dates
"""

import io
import re
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


# ============================================================
# Data classes
# ============================================================

@dataclass
class ParsedTransaction:
    transaction_date: str   # ISO-8601: YYYY-MM-DD
    description: str
    amount: float           # positive = credit/deposit, negative = debit/withdrawal
    raw_text: str
    _confidence: str = field(default="high", repr=False, compare=False)


@dataclass
class ParseResult:
    transactions: list = field(default_factory=list)
    parse_strategy: str = "failed"   # "table"|"text"|"block"|"text+block"|"failed"
    error: Optional[str] = None


# ============================================================
# Summary / noise line filter
# ============================================================

# Use \s* (not \s+) so concatenated words like "OpeningBalance" or "ClosingBalance"
# are caught even when pdfplumber strips the space between them.
_SKIP_RE = re.compile(
    r"""
    \b(
        opening\s*balance | closing\s*balance | previous\s*balance
      | new\s*balance     | beginning\s*balance | ending\s*balance
      | brought\s*forward | carried\s*forward   | balance\s*forward
      | running\s*balance
      | \btotals?\b | sub\s*-?\s*total | grand\s*total
      | \bsummary\b
      | interest\s*rate
      | account\s*(?:number|no\.?|\#)
      | statement\s*(?:period|date|balance)
      | (?:^|\s)page\s+\d | (?:^|\s)\bpage\b
      | payments?\s*due
      | credit\s*limit
      | available\s*credit
      | minimum\s*(?:payment|due)
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_summary_line(line: str) -> bool:
    """Return True when a line is a balance total, header, or footer — not a transaction."""
    return bool(_SKIP_RE.search(line))


# ============================================================
# Text normalization
# ============================================================

def normalize_text(text: str) -> str:
    """Collapse runs of whitespace and strip control characters."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_description(desc: str) -> str:
    """Normalize whitespace and strip leading/trailing punctuation."""
    desc = normalize_text(desc)
    desc = re.sub(r"^[^a-zA-Z0-9(]+", "", desc)
    desc = re.sub(r"[^a-zA-Z0-9)]+$", "", desc)
    return desc.strip()


# ============================================================
# Reference-code filtering
# ============================================================

def _is_reference_code(token: str) -> bool:
    """
    Return True when a token looks like a bank/Interac reference code
    rather than a human-readable description word.

    A reference code: contains BOTH digits and letters, has no spaces,
    and is at least 8 characters long.
    Examples: 2c7a84ec8cce32f8, C1AuK29Mzuxg, C1AAfPPDb6CB
    Not a reference code: TIRTHKUMARPANCHAL (all letters), OPENAI*CHATGPT (has *)
    """
    token = token.strip()
    if len(token) < 8:
        return False
    if not re.match(r'^[A-Za-z0-9]+$', token):
        return False
    has_digit = bool(re.search(r'\d', token))
    has_alpha = bool(re.search(r'[a-zA-Z]', token))
    return has_digit and has_alpha


def _clean_prefix(text: str) -> str:
    """
    Remove reference-code tokens from a description prefix, keeping
    human-readable words (merchant names, payee names, action words).
    """
    tokens = text.split()
    kept = [t for t in tokens if not _is_reference_code(t)]
    return " ".join(kept)


# ============================================================
# Date parsing
# ============================================================

_FULL_DATE_FORMATS = [
    "%m/%d/%Y", "%m/%d/%y",
    "%d/%m/%Y", "%d/%m/%y",
    "%Y-%m-%d", "%Y/%m/%d",
    "%b %d, %Y", "%b %d %Y",
    "%B %d, %Y", "%B %d %Y",
    "%d %b %Y", "%d %B %Y",
    "%d-%b-%Y", "%d-%b-%y",
    "%b. %d, %Y",
]

# Partial formats: year filled in from ref_year.
# "%d%b" handles RBC/TD-style "10Dec", "18Nov" (no separator).
_PARTIAL_DATE_FORMATS = [
    "%d%b", "%d%B",       # 10Dec, 10December  — RBC / some TD
    "%m/%d",              # 11/18               — US banks (Chase, WF)
    "%b %d", "%B %d",     # Nov 18, November 18
    "%d %b", "%d %B",     # 18 Nov, 18 November
    "%d-%b", "%d-%B",     # 18-Nov, 18-November — Scotiabank
]

# Full-date alternatives MUST precede partial so "01/15/2024" is not
# short-circuited to the "%m/%d" partial pattern.
_DATE_RE = re.compile(
    r"""
    (?:
        # ── Full dates (year present) ──────────────────────────────────────
        \d{4}[-/]\d{1,2}[-/]\d{1,2}
      | \d{1,2}[-/]\d{1,2}[-/]\d{2,4}
      | (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4}
      | \d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4}
      | \d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*-\d{2,4}
        # ── Partial dates — no year (ref_year applied in parse_date) ────────
      | (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}
      | \d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*
        # No separator: "10Dec", "15Nov" — RBC style; keep AFTER spaced alternatives
      | \d{1,2}(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*
        # Hyphen separator: "18-Nov" — Scotiabank style
      | \d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*
        # MM/DD (no year) — US banks
      | \d{1,2}/\d{1,2}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def parse_date(raw: Optional[str], ref_year: Optional[int] = None) -> Optional[str]:
    """
    Convert a raw date string to ISO-8601 (YYYY-MM-DD).
    ref_year fills in the year for partial dates (month + day only).
    """
    if not raw:
        return None
    raw = raw.strip().rstrip(",").strip()
    year = ref_year or datetime.now().year

    for fmt in _FULL_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    for fmt in _PARTIAL_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(year=year).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


# ============================================================
# Amount parsing
# ============================================================

# Captures: optional sign, optional $, optional open-paren, digits with comma
# thousands, two decimal places, optional close-paren.
# Also captures an optional trailing CR/DR indicator (TD, Scotiabank, BMO).
# Requires exactly 2 decimal places to filter out account/phone numbers.
_AMOUNT_RE = re.compile(
    r"(?<![,\d])"
    r"([+\-]?\s*\$?\s*\(?\d{1,3}(?:,\d{3})*\.\d{2}\)?(?:\s*(?:CR|DR)\b)?)"
    r"(?![,\d])",
    re.IGNORECASE,
)

_CR_DR_SUFFIX_RE = re.compile(r"\s*(CR|DR)\s*$", re.IGNORECASE)

# Broad matching — no strict \b so "VisaDebitpurchase" triggers "debit".
_DEBIT_HINT_RE = re.compile(
    r"debit|withdrawal|payment|purchase|fee|charge|pos\b|dr\b"
    r"|paid\s*out|money\s*out|\bsent\b|visa",
    re.IGNORECASE,
)
_CREDIT_HINT_RE = re.compile(
    r"credit|deposit|payroll|refund|transfer.{0,5}in|direct.{0,5}deposit"
    r"|salary|interest.{0,5}paid|cr\b|paid.{0,5}in|money.{0,5}in"
    r"|received|autodeposit",
    re.IGNORECASE,
)


def parse_amount(raw: Optional[str], context: str = "") -> Optional[float]:
    """
    Parse a raw amount string into a signed float.

    Handles:
      • Explicit sign:          -5.00, +5.00
      • Parenthesis negative:   (5.00)
      • CR/DR suffix:           5.00DR, 100.00 CR  (common in CA banks)
      • Context hints:          surrounding text scanned for debit/credit keywords
    """
    if not raw:
        return None

    # Strip trailing CR/DR indicator before numeric parsing.
    cr_dr_indicator: Optional[str] = None
    cr_dr_m = _CR_DR_SUFFIX_RE.search(raw)
    if cr_dr_m:
        cr_dr_indicator = cr_dr_m.group(1).upper()
        raw = raw[: cr_dr_m.start()]

    s = raw.strip().replace(" ", "").replace("$", "").replace(",", "")
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        val = float(s)
    except ValueError:
        return None

    if negative:
        return -abs(val)
    if cr_dr_indicator == "DR":
        return -abs(val)
    if cr_dr_indicator == "CR":
        return abs(val)

    has_explicit_sign = raw.strip()[:1] in ("+", "-")
    if not has_explicit_sign and context:
        if _DEBIT_HINT_RE.search(context):
            return -abs(val)
        if _CREDIT_HINT_RE.search(context):
            return abs(val)

    return val


# ============================================================
# Transaction-line helpers
# ============================================================

def is_probable_transaction_line(line: str, ref_year: Optional[int] = None) -> bool:
    """Return True when a text line likely represents the start of a transaction."""
    line = line.strip()
    if len(line) < 10 or is_summary_line(line):
        return False
    if not _DATE_RE.match(line):
        return False
    return bool(_AMOUNT_RE.search(line))


def _is_continuation_line(line: str) -> bool:
    """
    True when a line with no leading date looks like a description continuation.
    Filters out summary lines, purely-numeric lines, and very short noise.
    """
    line = line.strip()
    if not line or len(line) < 3:
        return False
    if is_summary_line(line):
        return False
    if _DATE_RE.match(line):
        return False
    return bool(re.search(r"[a-zA-Z]", line))


# ============================================================
# Deduplication
# ============================================================

def deduplicate_transactions(txns: list[ParsedTransaction]) -> list[ParsedTransaction]:
    """Remove exact duplicates keyed on (date, rounded amount, normalised description)."""
    seen: set[tuple] = set()
    unique: list[ParsedTransaction] = []
    for t in txns:
        key = (t.transaction_date, round(t.amount, 2), t.description.lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


# ============================================================
# Shared amount selector (Strategies 2 & 3)
# ============================================================

def _numeric_value(raw: str) -> Optional[float]:
    """Extract the numeric value from a raw amount string, ignoring sign/symbol/CR/DR."""
    s = raw.strip()
    # Strip CR/DR suffix
    s = _CR_DR_SUFFIX_RE.sub("", s)
    s = s.replace(" ", "").replace("$", "").replace(",", "").strip("()")
    # Remove any remaining letters (safety net)
    s = re.sub(r"[A-Za-z]", "", s)
    try:
        return abs(float(s))
    except ValueError:
        return None


def _raw_pick(amounts: list[str]) -> str:
    """
    Return the raw amount string most likely to be the transaction (not the running balance).
    Rule: last amount on a line is usually the balance. Walk backwards through
    the non-last candidates and return the first non-zero.
    """
    if len(amounts) == 1:
        return amounts[0]
    for raw in amounts[:-1]:
        v = _numeric_value(raw)
        if v is not None and v != 0.0:
            return raw
    return amounts[-1]


def _pick_amount(amounts: list[str], context: str) -> Optional[float]:
    """Select the transaction amount from all amounts found on one line."""
    raw = _raw_pick(amounts)
    return parse_amount(raw, context)


# ============================================================
# Strategy 1 — Table-based extraction
# ============================================================

_TABLE_COL_KEYWORDS: dict[str, list[str]] = {
    "date":    ["date", "posted date", "transaction date", "activity date",
                "trans date", "trans.", "posted", "value date", "effective date"],
    "desc":    ["description", "details", "merchant", "transaction", "activity",
                "memo", "payee", "narrative", "particulars", "reference"],
    "debit":   ["debit", "withdrawal", "withdrawals", "money out", "paid out",
                "charge", "charges", "dr", "payment out", "amount debit"],
    "credit":  ["credit", "deposit", "deposits", "money in", "paid in",
                "payment in", "cr", "amount credit"],
    "amount":  ["amount", "transaction amount", "net amount"],
    "balance": ["balance", "running balance", "available balance", "closing balance"],
}


def _find_col(headers: list[str], keywords: list[str]) -> Optional[int]:
    for i, h in enumerate(headers):
        if any(kw in h for kw in keywords):
            return i
    return None


def _cell(row: list, idx: Optional[int]) -> str:
    if idx is None or idx >= len(row):
        return ""
    return str(row[idx] or "").strip()


def _parse_table(table: list, ref_year: int) -> list[ParsedTransaction]:
    if not table or len(table) < 2:
        return []

    headers = [str(h or "").lower().strip() for h in table[0]]
    logger.debug("Table headers: %s", headers)

    date_col    = _find_col(headers, _TABLE_COL_KEYWORDS["date"])
    desc_col    = _find_col(headers, _TABLE_COL_KEYWORDS["desc"])
    debit_col   = _find_col(headers, _TABLE_COL_KEYWORDS["debit"])
    credit_col  = _find_col(headers, _TABLE_COL_KEYWORDS["credit"])
    amount_col  = _find_col(headers, _TABLE_COL_KEYWORDS["amount"])
    balance_col = _find_col(headers, _TABLE_COL_KEYWORDS["balance"])

    if date_col is None or desc_col is None:
        logger.debug("Table skipped — no date or description column. Headers: %s", headers)
        return []
    if debit_col is None and credit_col is None and amount_col is None:
        logger.debug("Table skipped — no amount column. Headers: %s", headers)
        return []
    if amount_col is not None and amount_col == balance_col:
        amount_col = None

    results: list[ParsedTransaction] = []
    for row in table[1:]:
        if not row or all(not c for c in row):
            continue

        raw_text = " | ".join(str(c or "").strip() for c in row)
        iso_date = parse_date(_cell(row, date_col), ref_year)
        if not iso_date:
            continue

        description = clean_description(_cell(row, desc_col))
        if not description or is_summary_line(description):
            continue

        amount: Optional[float] = None
        if amount_col is not None:
            amount = parse_amount(_cell(row, amount_col), raw_text)
        if amount is None and debit_col is not None:
            v = parse_amount(_cell(row, debit_col))
            if v is not None:
                amount = -abs(v)
        if amount is None and credit_col is not None:
            v = parse_amount(_cell(row, credit_col))
            if v is not None:
                amount = abs(v)
        if amount is None:
            continue

        results.append(ParsedTransaction(
            transaction_date=iso_date,
            description=description,
            amount=amount,
            raw_text=raw_text,
            _confidence="high",
        ))
    return results


def _extract_table_transactions(pdf: pdfplumber.PDF, ref_year: int) -> list[ParsedTransaction]:
    results: list[ParsedTransaction] = []
    for page_num, page in enumerate(pdf.pages, 1):
        tables = page.extract_tables()
        logger.debug("Page %d — %d table(s).", page_num, len(tables))
        for table in tables:
            rows = _parse_table(table, ref_year)
            logger.debug("Table on page %d: %d row(s).", page_num, len(rows))
            results.extend(rows)
    logger.info("Strategy 1 (table) raw: %d.", len(results))
    return results


# ============================================================
# Strategy 2 — Text-line extraction (single-line transactions)
# ============================================================

def _parse_text_line(line: str, ref_year: int) -> Optional[ParsedTransaction]:
    line = line.strip()
    if len(line) < 10 or is_summary_line(line):
        return None

    m = _DATE_RE.match(line)
    if not m:
        return None

    iso_date = parse_date(m.group(0), ref_year)
    if not iso_date:
        return None

    remainder = line[m.end():].strip()
    amounts = _AMOUNT_RE.findall(remainder)
    if not amounts:
        return None

    amount = _pick_amount(amounts, line)
    if amount is None:
        return None

    first_match = _AMOUNT_RE.search(remainder)
    raw_desc = remainder[: first_match.start()] if first_match else ""
    description = clean_description(_clean_prefix(raw_desc))
    if not description:
        return None

    return ParsedTransaction(
        transaction_date=iso_date,
        description=description,
        amount=amount,
        raw_text=line,
        _confidence="medium",
    )


def _extract_text_transactions(pdf: pdfplumber.PDF, ref_year: int) -> list[ParsedTransaction]:
    results: list[ParsedTransaction] = []
    for page_num, page in enumerate(pdf.pages, 1):
        text = page.extract_text() or ""
        logger.debug("Page %d — text length: %d chars.", page_num, len(text))
        for line in text.splitlines():
            txn = _parse_text_line(line, ref_year)
            if txn:
                results.append(txn)
    logger.info("Strategy 2 (text-line) raw: %d.", len(results))
    return results


# ============================================================
# Strategy 3 — Block / state-machine extraction
#
# Handles three RBC-style (and other bank) patterns:
#   a) Single-line:   DATE DESCRIPTION AMOUNT [BALANCE]
#   b) Multi-line:    DATE DESCRIPTION
#                     [REF_CODE] AMOUNT [BALANCE]
#   c) Date-less:     DESCRIPTION [AMOUNT]   ← uses last_seen_date
#      (Date printed only once per group of same-day transactions.)
# ============================================================

def _extract_block_transactions(pdf: pdfplumber.PDF, ref_year: int) -> list[ParsedTransaction]:
    results: list[ParsedTransaction] = []

    for page_num, page in enumerate(pdf.pages, 1):
        text = page.extract_text() or ""
        if not text:
            continue

        last_seen_date: Optional[str] = None

        # Pending state in a dict so the inner flush() can mutate it cleanly.
        s: dict = {
            "date":       None,
            "parts":      [],       # description fragments
            "amount_raw": None,     # raw amount string (sign resolved at flush)
            "context":    "",       # full line text accumulated for sign inference
            "raw_lines":  [],
        }

        def flush() -> None:
            if not (s["date"] and s["parts"] and s["amount_raw"] is not None):
                s["date"] = None
                s["parts"] = []
                s["amount_raw"] = None
                s["context"] = ""
                s["raw_lines"] = []
                return

            full_context = s["context"] + " " + " ".join(s["parts"])
            amount = parse_amount(s["amount_raw"], full_context)
            if amount is not None:
                description = clean_description(" ".join(s["parts"]))
                if description:
                    results.append(ParsedTransaction(
                        transaction_date=s["date"],
                        description=description,
                        amount=amount,
                        raw_text=" | ".join(s["raw_lines"]),
                        _confidence="low",
                    ))

            s["date"] = None
            s["parts"] = []
            s["amount_raw"] = None
            s["context"] = ""
            s["raw_lines"] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or is_summary_line(line):
                continue

            date_m = _DATE_RE.match(line)

            # ── Case A/B: line starts with a date ─────────────────────────
            if date_m:
                flush()
                iso_date = parse_date(date_m.group(0), ref_year)
                if not iso_date:
                    continue
                last_seen_date = iso_date
                s["date"] = iso_date
                s["raw_lines"].append(line)
                s["context"] += " " + line

                remainder = line[date_m.end():].strip()
                amounts = _AMOUNT_RE.findall(remainder)

                if amounts:
                    # Complete one-liner — description before first amount.
                    first_m = _AMOUNT_RE.search(remainder)
                    raw_desc = remainder[: first_m.start()].strip() if first_m else remainder
                    desc_clean = _clean_prefix(raw_desc)
                    if desc_clean:
                        s["parts"].append(desc_clean)
                    s["amount_raw"] = _raw_pick(amounts)
                    flush()
                else:
                    # Description-only date line; wait for amount on continuation.
                    if remainder:
                        s["parts"].append(_clean_prefix(remainder) or remainder)

            # ── No date: either completes a pending block or is standalone ─
            else:
                amounts = _AMOUNT_RE.findall(line)

                if amounts:
                    if s["date"] is not None and s["amount_raw"] is None:
                        # ── Complete a pending multi-line transaction ──────
                        first_m = _AMOUNT_RE.search(line)
                        raw_prefix = line[: first_m.start()].strip() if first_m else ""
                        desc_prefix = _clean_prefix(raw_prefix)
                        if desc_prefix and _is_continuation_line(desc_prefix):
                            s["parts"].append(desc_prefix)
                        s["amount_raw"] = _raw_pick(amounts)
                        s["context"] += " " + line
                        s["raw_lines"].append(line)
                        flush()

                    elif last_seen_date is not None:
                        # ── Standalone date-less transaction ──────────────
                        first_m = _AMOUNT_RE.search(line)
                        raw_desc = line[: first_m.start()].strip() if first_m else ""
                        description = clean_description(_clean_prefix(raw_desc))
                        amount_raw = _raw_pick(amounts)
                        full_context = line + " " + description
                        amount = parse_amount(amount_raw, full_context)
                        if amount is not None and description:
                            results.append(ParsedTransaction(
                                transaction_date=last_seen_date,
                                description=description,
                                amount=amount,
                                raw_text=line,
                                _confidence="low",
                            ))

                else:
                    # ── Description-only continuation ─────────────────────
                    if _is_continuation_line(line):
                        if s["date"] is not None and s["amount_raw"] is None:
                            # Append to existing pending block.
                            s["parts"].append(line)
                            s["context"] += " " + line
                            s["raw_lines"].append(line)
                        elif last_seen_date is not None and s["date"] is None:
                            # Start a new pending block using last_seen_date.
                            s["date"] = last_seen_date
                            s["parts"].append(line)
                            s["context"] += " " + line
                            s["raw_lines"].append(line)

        flush()  # flush last pending block on the page

    logger.info("Strategy 3 (block) raw: %d.", len(results))
    return results


# ============================================================
# Debug helper — POST /statements/debug
# ============================================================

def debug_parse(pdf_bytes: bytes) -> dict:
    """
    Returns raw pdfplumber diagnostics for a PDF so callers can inspect
    exactly what text, tables, dates, and amounts the PDF contains.
    Never writes to the database.
    """
    result: dict = {"page_count": 0, "pages": []}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            result["page_count"] = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

                line_diagnostics = []
                for ln in lines[:30]:
                    date_m = _DATE_RE.match(ln)
                    amounts = _AMOUNT_RE.findall(ln)
                    line_diagnostics.append({
                        "line": ln[:120],
                        "date_at_start": date_m.group(0) if date_m else None,
                        "amounts": amounts,
                        "is_summary": is_summary_line(ln),
                        "would_parse": bool(date_m) and bool(amounts) and not is_summary_line(ln),
                    })

                tables = page.extract_tables()
                table_diagnostics = [
                    {"row_count": len(tbl), "headers": tbl[0], "sample_rows": tbl[1:4]}
                    for tbl in tables if tbl
                ]

                result["pages"].append({
                    "page": page_num,
                    "text_length": len(text),
                    "text_sample": text[:800],
                    "line_count": len(lines),
                    "line_diagnostics": line_diagnostics,
                    "table_count": len(tables),
                    "tables": table_diagnostics,
                })
    except Exception as exc:
        result["error"] = str(exc)
    return result


# ============================================================
# Public API
# ============================================================

def parse_statement(pdf_bytes: bytes) -> ParseResult:
    """
    Parse a PDF bank statement and return extracted transactions.
    All errors are captured in ParseResult.error — nothing is raised.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            n_pages = len(pdf.pages)
            logger.info("PDF opened — %d page(s).", n_pages)

            if not n_pages:
                return ParseResult(error="PDF has no pages.")
            if n_pages > 100:
                logger.warning("Large PDF: %d pages — parsing may be slow.", n_pages)

            ref_year = datetime.now().year

            # ── Strategy 1: Table extraction ──────────────────────────────
            table_txns = deduplicate_transactions(
                _extract_table_transactions(pdf, ref_year)
            )
            logger.info("Strategy 1 final: %d transaction(s).", len(table_txns))
            if table_txns:
                return ParseResult(transactions=table_txns, parse_strategy="table")

            # ── Scanned-PDF early exit ─────────────────────────────────────
            all_text = "".join((page.extract_text() or "") for page in pdf.pages)
            if not all_text.strip():
                return ParseResult(
                    error=(
                        "No readable text found. "
                        "This PDF may be scanned/image-based and requires OCR."
                    ),
                )

            # ── Strategies 2 + 3: run both, merge, dedup ──────────────────
            # Strategy 2: complete single-line transactions (date + amount same line).
            # Strategy 3: multi-line blocks and date-less same-day transactions.
            text_txns  = _extract_text_transactions(pdf, ref_year)
            block_txns = _extract_block_transactions(pdf, ref_year)

            combined = deduplicate_transactions(text_txns + block_txns)
            logger.info(
                "Strategies 2+3 — text: %d, block: %d, combined: %d.",
                len(text_txns), len(block_txns), len(combined),
            )

            if combined:
                if text_txns and block_txns:
                    strategy = "text+block"
                elif text_txns:
                    strategy = "text"
                else:
                    strategy = "block"
                return ParseResult(transactions=combined, parse_strategy=strategy)

            return ParseResult(
                error=(
                    "No transactions found. "
                    "The PDF may be scanned/image-based or use an unsupported layout."
                ),
            )

    except Exception as exc:
        logger.exception("PDF parse error: %s", exc)
        return ParseResult(error=f"Could not read PDF: {exc}")
