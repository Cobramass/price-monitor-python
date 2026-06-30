# Price & Stock Monitor — Python

[![CI](https://github.com/Cobramass/price-monitor-python/actions/workflows/ci.yml/badge.svg)](https://github.com/Cobramass/price-monitor-python/actions/workflows/ci.yml)

A production-shaped **web-scraping / data-feed** tool in Python: it scrapes a product
catalogue concurrently, delivers clean structured data (JSON + CSV), and reports **what changed
since last time** — price moves, stock flips, new and removed items.

This is the Python counterpart to the Node [`price-monitor`](https://github.com/Cobramass/price-monitor-node) demo — same
engineering bar, idiomatic `asyncio` + `httpx` + BeautifulSoup. Run against
[`books.toscrape.com`](https://books.toscrape.com), a sandbox built for scraping practice (no
ToS/legal exposure); a real target is the URL pattern + three CSS selectors in `parse.py`.

## Run it

```bash
python -m venv .venv && . .venv/Scripts/activate   # (or .venv/bin/activate on macOS/Linux)
pip install -e ".[dev]"

python -m price_monitor --max-pages 3   # small run
python -m price_monitor                 # full catalogue (~1000 items)
python -m price_monitor                 # run again → change report vs the last run

pytest -q                               # the held-out eval suite
```

Outputs land in `data/`: `catalog.json`, `catalog.csv`, and `changes.json` (what moved).

## What it demonstrates (the deliverable bar)

| Concern | How it's handled |
|---|---|
| **Idiomatic async** | `asyncio.gather` over `httpx.AsyncClient`, bounded by a `Semaphore` — fast but polite |
| **Reliability** | Retry with exponential backoff + per-request timeout; a real `User-Agent` |
| **Clean, typed schema** | `@dataclass(slots=True)` records; defensive coercion (`"£51.77"`, `"1,200.00"`, `"n/a"` → trustworthy float or `None`, never a faked 0) |
| **The actual product** | Change-detection diff between runs → `changes.json`; only reports moves it can *prove* (never a stock flip against an unknown) |
| **No silent failure** | A failed page is logged loudly; if any page fails, the snapshot is **refused** (a partial snapshot would poison the next diff) and the process exits non-zero so a scheduler sees the failure |
| **Tested** | Pure logic (parse / coerce / diff) unit-tested with `pytest`; CI runs it on Python 3.11–3.13 |
| **Logs to stderr** | stdout stays clean for piping; our logs are the signal (httpx's request noise is quieted) |

## Layout

```
price_monitor/
  __main__.py   CLI (argparse) — python -m price_monitor
  core.py       async fetch + orchestration + output writing (the only I/O)
  parse.py      HTML → records (pure)
  models.py     dataclass + defensive coercion (pure)
  diff.py       change-detection (pure)
tests/          pytest eval — coercion, parsing, diff
.github/workflows/ci.yml   pytest on 3.11–3.13
```

## Applying it to a real client target

1. **Target** — URL pattern + the 3 selectors in `parse.py` (title / price / availability).
2. **Anti-bot** — swap the plain `httpx` client for a residential-proxy client or `playwright`
   for JS-heavy/blocked sites; the retry/concurrency/diff scaffolding is unchanged.
3. **Delivery** — JSON/CSV today; a Google Sheet, a webhook, an emailed report, or a small API
   on a cron schedule just as easily. For `.xlsx` delivery, `pandas` + `openpyxl` is a drop-in.

Built by Matthew Daly — web-scraping & data-feed work in Python or Node, delivered clean and async.
