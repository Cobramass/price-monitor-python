"""Change-detection between two snapshots. Pure and unit-testable.

The diff IS the product on a scheduled feed — so it only reports a change when
*both* sides are known. A price/stock move against an unknown (None) is never
fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Changes:
    added: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    price_changes: list[dict] = field(default_factory=list)
    stock_changes: list[dict] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"{len(self.price_changes)} price · {len(self.stock_changes)} stock · "
            f"{len(self.added)} new · {len(self.removed)} removed"
        )

    def as_dict(self) -> dict:
        return {
            "summary": self.summary,
            "added": self.added,
            "removed": self.removed,
            "priceChanges": self.price_changes,
            "stockChanges": self.stock_changes,
        }


def diff_snapshots(prev: list[dict], curr: list[dict]) -> Changes:
    prev_by_id = {p["id"]: p for p in prev}
    curr_by_id = {c["id"]: c for c in curr}
    changes = Changes()

    changes.added = [
        {"id": c["id"], "title": c.get("title"), "price": c.get("price")}
        for c in curr
        if c["id"] not in prev_by_id
    ]
    changes.removed = [
        {"id": p["id"], "title": p.get("title")}
        for p in prev
        if p["id"] not in curr_by_id
    ]

    for c in curr:
        p = prev_by_id.get(c["id"])
        if p is None:
            continue

        old_price, new_price = p.get("price"), c.get("price")
        if _is_num(old_price) and _is_num(new_price) and old_price != new_price:
            changes.price_changes.append(
                {
                    "id": c["id"],
                    "title": c.get("title"),
                    "from": old_price,
                    "to": new_price,
                    "deltaPct": round((new_price - old_price) / old_price * 100, 2),
                }
            )

        old_stock, new_stock = p.get("in_stock"), c.get("in_stock")
        if isinstance(old_stock, bool) and isinstance(new_stock, bool) and old_stock != new_stock:
            changes.stock_changes.append(
                {
                    "id": c["id"],
                    "title": c.get("title"),
                    "from": "in_stock" if old_stock else "out_of_stock",
                    "to": "in_stock" if new_stock else "out_of_stock",
                }
            )

    return changes


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)
