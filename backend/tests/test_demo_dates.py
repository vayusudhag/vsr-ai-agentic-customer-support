from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.seed import refresh_demo_dates
from app.tools.core import _fmt_date, check_return_eligibility, get_order_status
from tests.conftest import chat


@pytest.fixture
def stale_db(fresh_db):
    """Demo data as if it was seeded 30 days ago, put back to current afterwards."""
    refresh_demo_dates(datetime.now(timezone.utc) - timedelta(days=30))
    yield
    refresh_demo_dates()


def _order_count():
    from app.db import SessionLocal
    from app.models import Order

    with SessionLocal() as db:
        return db.scalar(select(func.count(Order.id)))


def test_refresh_moves_stale_demo_dates_to_today(ctx, stale_db):
    count = _order_count()
    assert get_order_status(ctx(), "ORD-1001")["running_late"]
    assert refresh_demo_dates() == 30
    assert refresh_demo_dates() == 0  # already current: repeat runs change nothing
    assert _order_count() == count
    status = get_order_status(ctx(), "ORD-1001")
    assert status["estimated_delivery"] == _fmt_date(datetime.now(timezone.utc) + timedelta(days=4))
    assert not status["running_late"]
    elig = check_return_eligibility(ctx(), "ORD-1002")
    assert elig["eligible"] and elig["days_remaining"] == 20


def test_shipped_order_past_its_estimate_is_reported_late(client, pardha, stale_db):
    text = chat(client, pardha, "Where is my order ORD-1001?")["message"]["content"]
    assert "running late" in text and "expected to arrive" not in text
