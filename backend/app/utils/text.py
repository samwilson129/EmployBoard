from __future__ import annotations

import html
import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from typing import Any

_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_TAG_RE = re.compile(
    r"</?(?:p|div|li|ul|ol|h[1-6]|tr|td|th|table|section|article|br)\b[^>]*>",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^a-z0-9+#.]+")


def unescape_html(value: str | None) -> str | None:
    """Decode entities exactly once (Greenhouse returns escaped HTML)."""
    if value is None:
        return None
    decoded = html.unescape(value)
    return decoded if decoded.strip() else None


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    text = _SCRIPT_STYLE_RE.sub(" ", value)
    text = _BLOCK_TAG_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def make_snippet(value: str | None, max_length: int = 240) -> str | None:
    text = _WHITESPACE_RE.sub(" ", html_to_text(value)).strip()
    if not text:
        return None
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return f"{truncated}…"


def normalize_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _WHITESPACE_RE.sub(" ", value).strip()
    return cleaned or None


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_title(value: str) -> str:
    value = strip_accents(value).lower().replace("&", " and ")
    value = _NON_WORD_RE.sub(" ", value)
    return _WHITESPACE_RE.sub(" ", value).strip()


def normalize_location(value: str | None) -> str | None:
    if not value:
        return None
    value = strip_accents(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    normalized = _WHITESPACE_RE.sub(" ", value).strip()
    return normalized or None


_LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "llc",
    "ltd",
    "limited",
    "plc",
    "gmbh",
    "ag",
    "sa",
    "sas",
    "bv",
    "nv",
    "oy",
    "ab",
    "pte",
    "pty",
    "private",
    "pvt",
}


def normalize_company_name(value: str) -> str:
    tokens = normalize_title(value).split()
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def slugify(value: str) -> str:
    value = strip_accents(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "company"


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, (int, float)):
        number = float(value)
        # Lever's createdAt is milliseconds; accept seconds as well.
        if number > 100_000_000_000:
            number /= 1000.0
        try:
            result = datetime.fromtimestamp(number, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            result = datetime.fromisoformat(raw)
        except ValueError:
            for fmt in (
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%d/%m/%Y",
                "%Y-%m-%d %H:%M:%S UTC",
            ):
                try:
                    result = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
            else:
                try:
                    result = parsedate_to_datetime(raw)
                except (TypeError, ValueError, OverflowError):
                    return None
    else:
        return None

    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.\-]", "", value)
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
    return None


_REQUISITION_PLACEHOLDERS = {
    "n a",
    "na",
    "none",
    "null",
    "nil",
    "unknown",
    "tbd",
    "to be determined",
    "not applicable",
    "not specified",
    "no requisition id",
    "see opening",
    "see opening id",
    "see job id",
    "opening id",
    "job id",
    "requisition",
    "requisition id",
    "req",
    "req id",
    "multiple",
    "multi",
    "mul",
    "one",
}


def clean_requisition_id(value: Any) -> str | None:
    """Return a usable requisition identifier, or None for placeholders.

    Several public boards expose a shared placeholder such as "See Opening ID"
    or "MULTI" for every posting. Treating those as real requisition numbers
    would collapse hundreds of distinct vacancies into one record, so they are
    discarded here. The sync service also requires a matching title and
    location before it uses a requisition identifier for deduplication.
    """
    if value is None:
        return None
    text = normalize_whitespace(str(value))
    if not text:
        return None
    key = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    if not key or key in _REQUISITION_PLACEHOLDERS:
        return None
    # Short values without a digit are usually labels such as "ONE." or "MUL".
    if len(key) <= 12 and not any(char.isdigit() for char in text):
        return None
    if len(text) > 100:
        return None
    return text


def normalize_currency(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    currency = value.strip().upper()
    return currency if len(currency) == 3 and currency.isalpha() else None


def clean_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    url = value.strip()
    if url.startswith(("http://", "https://")):
        return url
    return None
