"""Async orchestration: fetch politely, parse, diff, and persist clean outputs.

This is the only module that touches the network. Everything it depends on
(parse, diff, models) is pure, so the logic is tested without hitting the site.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .models import Product
from .parse import parse_page
from .diff import diff_snapshots

log = logging.getLogger("price_monitor")


@dataclass(frozen=True)
class Config:
    base_url: str = "https://books.toscrape.com/catalogue/page-{n}.html"
    max_pages: int = 50  # full catalogue ~1000 items
    concurrency: int = 5  # be a good citizen
    max_retries: int = 3
    timeout_s: float = 15.0
    user_agent: str = "PriceMonitorDemo/1.0 (+https://github.com/Cobramass)"
    data_dir: Path = Path("data")

    @property
    def fields(self) -> list[str]:
        return ["id", "title", "price", "currency", "in_stock", "rating", "url"]


async def _fetch(client: httpx.AsyncClient, url: str, cfg: Config) -> str:
    """GET with timeout, retry and exponential backoff. Raises on final failure."""
    last_err: Exception | None = None
    for attempt in range(1, cfg.max_retries + 1):
        try:
            resp = await client.get(url, timeout=cfg.timeout_s)
            resp.raise_for_status()
            return resp.text
        except (httpx.HTTPError, httpx.TimeoutException) as err:
            last_err = err
            if attempt < cfg.max_retries:
                backoff = 0.5 * 2 ** (attempt - 1)
                log.warning("retry %d/%d for %s (%s) — waiting %.1fs",
                            attempt, cfg.max_retries, url, err, backoff)
                await asyncio.sleep(backoff)
    raise RuntimeError(f"failed {url} after {cfg.max_retries} attempts: {last_err}")


async def _fetch_page(client, sem, url, page_no, cfg) -> list[Product] | None:
    """Fetch+parse one page under the concurrency semaphore. None == failed page."""
    async with sem:
        try:
            html = await _fetch(client, url, cfg)
            items = parse_page(html)
            log.debug("page %d: %d items", page_no, len(items))
            return items
        except Exception as err:  # loud, not swallowed as "0 items"
            log.error("PAGE %d FAILED: %s", page_no, err)
            return None


async def scrape(cfg: Config) -> list[Product]:
    """Scrape every page concurrently. Refuses to return a partial catalogue."""
    sem = asyncio.Semaphore(cfg.concurrency)
    headers = {"User-Agent": cfg.user_agent, "Accept": "text/html"}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        tasks = [
            _fetch_page(client, sem, cfg.base_url.format(n=n), n, cfg)
            for n in range(1, cfg.max_pages + 1)
        ]
        results = await asyncio.gather(*tasks)

    failed = [i + 1 for i, r in enumerate(results) if r is None]
    if failed:
        # A partial snapshot would poison the next diff with phantom "removed"
        # items — so we refuse it loudly instead of shipping silent gaps.
        raise PartialCoverageError(failed, cfg.max_pages)

    catalog: list[Product] = [item for page in results for item in page]  # type: ignore[union-attr]
    return catalog


class PartialCoverageError(RuntimeError):
    def __init__(self, failed_pages: list[int], total: int):
        self.failed_pages = failed_pages
        super().__init__(
            f"PARTIAL COVERAGE: {len(failed_pages)}/{total} pages failed "
            f"({failed_pages}) — snapshot NOT saved (would poison the diff). Re-run."
        )


def write_outputs(catalog: list[Product], cfg: Config, started_at: str) -> dict | None:
    """Persist clean JSON + CSV and (if a baseline exists) a change report."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = cfg.data_dir / "catalog.json"
    rows = [p.as_dict() for p in catalog]

    change_report: dict | None = None
    if snapshot_path.exists():
        try:
            prev = json.loads(snapshot_path.read_text(encoding="utf-8"))
            prev_rows = prev.get("products", prev) if isinstance(prev, dict) else prev
            change_report = diff_snapshots(prev_rows, rows).as_dict()
            change_report["comparedAt"] = started_at
            (cfg.data_dir / "changes.json").write_text(
                json.dumps(change_report, indent=2), encoding="utf-8")
            log.info("changes vs last run: %s -> data/changes.json", change_report["summary"])
        except (OSError, json.JSONDecodeError) as err:
            log.error("could not diff previous snapshot: %s", err)
            (cfg.data_dir / "changes.json").write_text(
                json.dumps({"comparedAt": started_at,
                            "error": f"previous snapshot unreadable: {err}"}, indent=2),
                encoding="utf-8")
    else:
        log.info("no previous snapshot — this run is the baseline.")

    snapshot_path.write_text(
        json.dumps({"scrapedAt": started_at, "count": len(rows), "products": rows}, indent=2),
        encoding="utf-8")
    with (cfg.data_dir / "catalog.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cfg.fields)
        writer.writeheader()
        writer.writerows(rows)

    return change_report


async def run(cfg: Config) -> int:
    """Top-level: scrape -> persist. Returns a process exit code."""
    started_at = datetime.now(timezone.utc).isoformat()
    log.info("scan started %s", started_at)
    try:
        catalog = await scrape(cfg)
    except PartialCoverageError as err:
        log.error("%s", err)
        return 1
    log.info("scraped %d products across %d pages", len(catalog), cfg.max_pages)
    write_outputs(catalog, cfg, started_at)
    log.info("wrote data/catalog.json + data/catalog.csv (done)")
    return 0
