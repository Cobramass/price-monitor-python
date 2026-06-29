"""Held-out eval — the pure logic (no network).

Mirrors the Node demo's test intent: messy input is coerced not crashed, parsing
finds records and drops the un-diffable ones, and the diff only reports changes
it can actually prove.
"""

from price_monitor.models import to_number, rating_from_class, stock_from_text
from price_monitor.parse import parse_page
from price_monitor.diff import diff_snapshots


# --- coercion -------------------------------------------------------------

def test_to_number_handles_messy_input():
    assert to_number("£51.77") == 51.77
    assert to_number("1,200.00") == 1200.0
    assert to_number(39.5) == 39.5
    assert to_number("n/a") is None      # unparseable -> None, not 0
    assert to_number("") is None
    assert to_number(None) is None
    assert to_number(True) is None        # bool is not a price


def test_stock_and_rating_unknowns_are_none():
    assert stock_from_text("In stock (5 available)") is True
    assert stock_from_text("") is None    # absent != out-of-stock
    assert stock_from_text(None) is None
    assert rating_from_class("star-rating Three") == 3
    assert rating_from_class("star-rating") is None
    assert rating_from_class(None) is None


# --- parsing --------------------------------------------------------------

_FIXTURE = """
<section><ol class="row">
  <li><article class="product_pod">
    <h3><a href="../../catalogue/a-light-in-the-attic_1000/index.html" title="A Light in the Attic">A Light...</a></h3>
    <p class="star-rating Three"></p>
    <p class="price_color">£51.77</p>
    <p class="instock availability">In stock</p>
  </article></li>
  <li><article class="product_pod">
    <h3><a href="catalogue/tipping-the-velvet_999/index.html" title="Tipping the Velvet">Tipping...</a></h3>
    <p class="star-rating One"></p>
    <p class="price_color">£53.74</p>
    <p class="instock availability"></p>
  </article></li>
</ol></section>
"""


def test_parse_page_extracts_normalised_records():
    products = parse_page(_FIXTURE)
    assert len(products) == 2
    first = products[0]
    assert first.id == "a-light-in-the-attic_1000"
    assert first.price == 51.77
    assert first.rating == 3
    assert first.in_stock is True
    assert first.url.startswith("https://books.toscrape.com/catalogue/")
    # second item has empty availability -> unknown, not False
    assert products[1].in_stock is None


def test_parse_page_drops_records_with_no_id():
    broken = '<article class="product_pod"><h3><a>no href no title</a></h3></article>'
    assert parse_page(broken) == []


# --- change-detection -----------------------------------------------------

def test_diff_reports_only_provable_changes():
    prev = [
        {"id": "a", "title": "A", "price": 10.0, "in_stock": True},
        {"id": "b", "title": "B", "price": 20.0, "in_stock": False},
        {"id": "c", "title": "C", "price": 30.0, "in_stock": None},
    ]
    curr = [
        {"id": "a", "title": "A", "price": 8.0, "in_stock": True},     # price down
        {"id": "b", "title": "B", "price": 20.0, "in_stock": True},    # stock flip
        {"id": "c", "title": "C", "price": 33.0, "in_stock": True},    # both prev unknown-stock
        {"id": "d", "title": "D", "price": 5.0, "in_stock": True},     # new
    ]
    changes = diff_snapshots(prev, curr)

    assert [x["id"] for x in changes.added] == ["d"]
    assert [x["id"] for x in changes.removed] == []
    price_ids = {x["id"] for x in changes.price_changes}
    assert price_ids == {"a", "c"}
    a = next(x for x in changes.price_changes if x["id"] == "a")
    assert a["deltaPct"] == -20.0
    # b flips stock; c had unknown prev stock so NO fabricated stock change
    stock_ids = {x["id"] for x in changes.stock_changes}
    assert stock_ids == {"b"}


def test_diff_summary_string():
    assert "price" in diff_snapshots([], []).summary
