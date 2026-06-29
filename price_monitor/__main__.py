"""CLI entry point: `python -m price_monitor`.

Logs to stderr (so stdout could carry piped data if ever needed) and exits
non-zero on partial coverage so a scheduler/cron treats a bad run as a failure.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .core import Config, run


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="price_monitor", description="Scrape a catalogue with change-detection.")
    p.add_argument("--max-pages", type=int, default=50, help="pages to scrape (default 50 = full demo catalogue)")
    p.add_argument("--concurrency", type=int, default=5, help="parallel requests (default 5)")
    p.add_argument("--data-dir", type=Path, default=Path("data"), help="output directory (default ./data)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[price-monitor] %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # keep our logs the signal
    cfg = Config(max_pages=args.max_pages, concurrency=args.concurrency, data_dir=args.data_dir)
    return asyncio.run(run(cfg))


if __name__ == "__main__":
    raise SystemExit(main())
