import pytest

from app.tools.core import (ToolError, check_return_eligibility, create_refund_request, create_return_request,
                            get_customer_orders, get_order_details, get_order_status, get_refund_status,
                            normalize_order_id, search_products)


def test_order_lookup_returns_real_record(ctx):
    d = get_order_details(ctx(), "ORD-1001")
    assert d["order_id"] == "ORD-1001" and d["status"] == "shipped"
    assert d["estimated_delivery"] and d["items"][0]["name"] == "Halden Aria Pro Headphones"


def test_order_id_normalisation_and_validation():
    assert normalize_order_id("ord 1001") == "ORD-1001"
    assert normalize_order_id("1001") == "ORD-1001"
    with pytest.raises(ToolError):
        normalize_order_id("DROP TABLE orders")


def test_cannot_read_another_customers_order(ctx):
    with pytest.raises(ToolError, match="couldn't find"):
        get_order_status(ctx(), "ORD-1006")  # belongs to Priya
    assert get_order_status(ctx("pavan.y@example.com"), "ORD-1006")["order_id"] == "ORD-1006"


def test_customer_orders_scoped_to_user(ctx):
    ids = {o["order_id"] for o in get_customer_orders(ctx(), limit=50)["orders"]}
    assert {"ORD-1001", "ORD-1002", "ORD-1003"} <= ids and "ORD-1006" not in ids


def test_product_search_filters(ctx):
    res = search_products(ctx(), query="noise-cancelling headphones", max_price=300)
    names = [p["name"] for p in res["products"]]
    assert "Halden Aria Pro Headphones" in names
    assert all(p["price"] <= 300 for p in res["products"])
    with pytest.raises(ToolError):
        search_products(ctx(), query="x", max_price=-5)


@pytest.mark.parametrize("order_id,eligible,fragment", [
    ("ORD-1002", True, "inside the 30-day window"),
    ("ORD-1003", False, "outside the 30-day"),
    ("ORD-1005", False, "final sale"),
    ("ORD-1001", False, "only be returned after delivery"),
    ("ORD-1004", False, "only be returned after delivery"),
])
def test_return_eligibility_scenarios(ctx, fresh_db, order_id, eligible, fragment):
    e = check_return_eligibility(ctx(), order_id)
    assert e["eligible"] is eligible
    assert fragment in " ".join(e["reasons"])


def test_refund_request_created_pending_and_duplicate_blocked(ctx, fresh_db):
    c = ctx()
    r = create_refund_request(c, "ORD-1002", "Watch strap broken on arrival")
    assert r["status"] == "pending" and r["requires_human_approval"]
    assert r["return_shipping_fee_waived"] and r["amount"] == 238.0
    with pytest.raises(ToolError):
        create_refund_request(c, "ORD-1002", "again")
    assert get_refund_status(c, order_id="ORD-1002")["refunds"][0]["status"] == "pending"


def test_refund_rejected_for_ineligible_order(ctx, fresh_db):
    with pytest.raises(ToolError, match="outside"):
        create_refund_request(ctx(), "ORD-1003", "Changed my mind")


def test_return_request_idempotent(ctx, fresh_db):
    a = create_return_request(ctx(), "ORD-1002", "Too small")
    b = create_return_request(ctx(), "ORD-1002", "Too small")
    assert a["rma_number"] == b["rma_number"] and b["already_existed"]
