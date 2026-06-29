"""HTML -> Product records. Pure and unit-testable (no network)."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import Product, rating_from_class, stock_from_text, to_number

log = logging.getLogger("price_monitor")

CATALOGUE_BASE = "https://books.toscrape.com/catalogue/"


def parse_page(html: str) -> list[Product]:
    """Parse one catalogue page into normalised records.

    A record with no derivable id is dropped LOUDLY (it cannot be diffed across
    runs) — never emitted with a null/colliding key.
    """
    soup = BeautifulSoup(html, "lxml")
    products: list[Product] = []

    for pod in soup.select("article.product_pod"):
        link = pod.select_one("h3 a")
        title = (link.get("title") or "").strip() if link else None
        href = (link.get("href") or "") if link else ""

        # stable id from the URL slug so repeated titles still diff correctly
        slug = href.rstrip("/").split("/")[-2] if "/" in href.strip("/") else None
        record_id = slug or title
        if not record_id:
            log.warning("skipped a product with no id or title (selector drift?)")
            continue

        price_el = pod.select_one(".price_color")
        price = to_number(price_el.get_text(strip=True)) if price_el else None

        avail_el = pod.select_one(".instock.availability")
        in_stock = stock_from_text(avail_el.get_text(strip=True) if avail_el else None)

        rating_el = pod.select_one("p.star-rating")
        rating = rating_from_class(" ".join(rating_el.get("class", [])) if rating_el else None)

        products.append(
            Product(
                id=record_id,
                title=title,
                price=price,
                currency="GBP",
                in_stock=in_stock,
                rating=rating,
                url=urljoin(CATALOGUE_BASE, href.lstrip("./")),
            )
        )

    return products
