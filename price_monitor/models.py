"""Domain model + defensive coercion.

Real scrape targets return messy strings ("£51.77", "", "In stock (3)"). The
coercion here is where a one-off script becomes a deliverable: every value is
parsed defensively and an unknown is preserved as ``None`` rather than faked as
zero/false — a fake value is a silent data error the client finds days later.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_NON_NUMERIC = re.compile(r"[^0-9.\-]")
_STAR_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


@dataclass(slots=True)
class Product:
    """One normalised catalogue record. ``id`` is required (it is the diff key)."""

    id: str
    title: str | None
    price: float | None
    currency: str
    in_stock: bool | None
    rating: int | None
    url: str

    def as_dict(self) -> dict:
        return asdict(self)


def to_number(text: str | float | None) -> float | None:
    """Parse a price-ish value to float, or None if it cannot be trusted."""
    if text is None or isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return float(text) if _finite(float(text)) else None
    cleaned = _NON_NUMERIC.sub("", str(text))
    if cleaned in ("", "-", ".", "-."):
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if _finite(value) else None


def rating_from_class(class_value: str | None) -> int | None:
    """`p.star-rating Three` -> 3 (None if absent/unknown)."""
    if not class_value:
        return None
    word = class_value.replace("star-rating", "").strip()
    return _STAR_WORDS.get(word)


def stock_from_text(text: str | None) -> bool | None:
    """Empty/absent availability is UNKNOWN (None), never assumed out-of-stock."""
    if not text or not text.strip():
        return None
    return bool(re.search(r"in stock", text, re.IGNORECASE))


def _finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))
