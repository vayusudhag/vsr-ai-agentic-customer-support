"""Tools that operate on the demo database and policy collection.

Every tool receives a ToolContext bound to the *authenticated* user. The user id
is never taken from model output, so an agent cannot be talked into reading or
modifying another customer's orders.
"""
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AgentExecutionLog, Order, Product, RefundRequest, ReturnRequest, User
from app.observability import redact

ORDER_RE = re.compile(r"^ORD-\d{4}$")
DEFECT_WORDS = ("defect", "broken", "broke", "cracked", "dead on arrival", "malfunction", "damaged", "faulty", "not working", "doesn't work", "stopped working", "wrong item", "incorrect")
RETURN_SHIPPING_FEE = 7.95


class ToolError(Exception):
    """Expected, user-safe failure (validation, permission, business rule)."""


@dataclass
class ToolContext:
    db: Session
    user: User
    conversation_id: str | None = None
    agent: str = "unknown"
    trace: list[dict] = field(default_factory=list)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fmt_date(dt: datetime | None) -> str | None:
    dt = _as_utc(dt)
    return dt.strftime("%B %d, %Y").replace(" 0", " ") if dt else None


def normalize_order_id(order_id: str) -> str:
    oid = (order_id or "").strip().upper().replace(" ", "")
    if re.fullmatch(r"\d{4}", oid):
        oid = f"ORD-{oid}"
    if re.fullmatch(r"ORD\d{4}", oid):
        oid = f"ORD-{oid[3:]}"
    if not ORDER_RE.match(oid):
        raise ToolError(f"'{order_id}' is not a valid order number. Order numbers look like ORD-1234.")
    return oid


def _load_owned_order(ctx: ToolContext, order_id: str) -> Order:
    oid = normalize_order_id(order_id)
    order = ctx.db.scalar(select(Order).where(Order.order_number == oid))
    # Same message whether the order is missing or belongs to someone else: no existence leak.
    if order is None or (ctx.user.role != "admin" and order.customer_id != ctx.user.id):
        raise ToolError(f"I couldn't find order {oid} on your account.")
    return order


def run_tool(ctx: ToolContext, name: str, fn, **kwargs) -> dict:
    """Execute a tool, time it, record it in the trace and the execution log."""
    t0 = time.perf_counter()
    ok, err, result = True, None, None
    try:
        result = fn(ctx, **kwargs)
        return result
    except ToolError as e:
        ok, err = False, str(e)
        raise
    except Exception as e:  # unexpected failure; never leak internals to the user
        ok, err = False, f"{type(e).__name__}: {e}"
        raise ToolError("That lookup failed unexpectedly. Please try again.") from e
    finally:
        ms = round((time.perf_counter() - t0) * 1000, 2)
        ctx.trace.append({"tool": name, "input": redact(kwargs), "success": ok, "error": err, "latency_ms": ms})
        ctx.db.add(AgentExecutionLog(conversation_id=ctx.conversation_id, user_id=ctx.user.id, agent=ctx.agent,
                                     tool_name=name, tool_input=redact(kwargs), success=ok, error=err, latency_ms=ms))
        ctx.db.commit()


# ---------------------------------------------------------------- orders
def get_order_status(ctx: ToolContext, order_id: str) -> dict:
    o = _load_owned_order(ctx, order_id)
    eta = _as_utc(o.estimated_delivery)
    # An open order whose estimate has passed is late; its old estimate is not a delivery date to quote.
    late = o.status in ("processing", "shipped", "in_transit") and eta is not None \
        and eta.date() < datetime.now(timezone.utc).date()
    return {
        "order_id": o.order_number, "status": o.status, "carrier": o.carrier, "tracking_number": o.tracking_number,
        "placed_on": _fmt_date(o.placed_at), "shipped_on": _fmt_date(o.shipped_at),
        "estimated_delivery": _fmt_date(o.estimated_delivery) if o.status != "delivered" else None,
        "running_late": late,
        "delivered_on": _fmt_date(o.delivered_at),
    }


def get_order_details(ctx: ToolContext, order_id: str) -> dict:
    o = _load_owned_order(ctx, order_id)
    d = get_order_status(ctx, order_id)
    d.update({
        "total": o.total, "shipping_address": o.shipping_address,
        "items": [{"sku": i.product.sku, "name": i.product.name, "quantity": i.quantity, "unit_price": i.unit_price,
                   "returnable": i.product.returnable} for i in o.items],
    })
    return d


def get_customer_orders(ctx: ToolContext, limit: int = 10) -> dict:
    limit = max(1, min(int(limit), 50))
    rows = ctx.db.scalars(select(Order).where(Order.customer_id == ctx.user.id)
                          .order_by(Order.placed_at.desc()).limit(limit)).all()
    return {"count": len(rows), "orders": [
        {"order_id": o.order_number, "status": o.status, "total": o.total, "placed_on": _fmt_date(o.placed_at),
         "items": [i.product.name for i in o.items]} for o in rows]}


# ---------------------------------------------------------------- products
def search_products(ctx: ToolContext, query: str = "", category: str | None = None,
                    max_price: float | None = None, limit: int = 5) -> dict:
    from app.rag.embeddings import tokenize

    if max_price is not None and max_price <= 0:
        raise ToolError("Maximum price must be greater than zero.")
    limit = max(1, min(int(limit), 10))
    stmt = select(Product).where(Product.stock > 0)
    if category:
        stmt = stmt.where(Product.category.ilike(category))
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    products = ctx.db.scalars(stmt).all()
    q = set(tokenize(query))
    scored = []
    for p in products:
        hay = set(tokenize(f"{p.name} {p.category} {p.description} {' '.join(p.tags)}"))
        tag_hits = len(q & set(tokenize(" ".join(p.tags)))) * 2
        score = len(q & hay) + tag_hits
        if q and score == 0:
            continue
        words = {}
        for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", f"{' '.join(p.tags)} {p.name} {p.description}".lower()):
            words.setdefault(tokenize(w)[0] if tokenize(w) else w, w)
        scored.append((score + p.rating / 10, p, [words.get(t, t) for t in sorted(q & hay)]))
    scored.sort(key=lambda x: -x[0])
    return {"count": len(scored[:limit]), "products": [
        {"sku": p.sku, "name": p.name, "category": p.category, "price": p.price, "rating": p.rating,
         "description": p.description, "matched_terms": m} for _, p, m in scored[:limit]]}


# ---------------------------------------------------------------- knowledge base
def search_knowledge_base(ctx: ToolContext, query: str, k: int = 5) -> dict:
    from app.rag.retriever import retrieve

    if not query or len(query) > 500:
        raise ToolError("Search query must be between 1 and 500 characters.")
    chunks = retrieve(query, k=max(1, min(int(k), 10)))
    return {"results": [{"id": c.id, "text": c.text, "doc_title": c.doc_title, "section": c.section,
                         "score": c.score} for c in chunks]}


# ---------------------------------------------------------------- returns & refunds
def _eligibility(ctx: ToolContext, o: Order) -> dict:
    s = get_settings()
    now = datetime.now(timezone.utc)
    reasons, eligible = [], True
    days = None
    if o.status == "cancelled":
        eligible = False
        reasons.append("The order was cancelled, so there is nothing to return. Charges on cancelled orders are refunded automatically (Cancellation Policy).")
    elif o.status != "delivered":
        eligible = False
        reasons.append(f"The order is currently '{o.status.replace('_', ' ')}'. Orders can only be returned after delivery (Return Policy).")
    else:
        days = (now - _as_utc(o.delivered_at)).days
        if days > s.return_window_days:
            eligible = False
            reasons.append(f"It was delivered {days} days ago, outside the {s.return_window_days}-day return window (Return Policy).")
    non_returnable = [i.product.name for i in o.items if not i.product.returnable]
    if non_returnable and eligible:
        eligible = False
        reasons.append(f"{', '.join(non_returnable)} is final sale and cannot be returned (Return Policy).")
    active_refund = ctx.db.scalar(select(RefundRequest).where(RefundRequest.order_id == o.id,
                                                             RefundRequest.status.in_(["pending", "approved"])))
    if active_refund and eligible:
        eligible = False
        reasons.append(f"Refund {active_refund.refund_number} for this order is already {active_refund.status} (one active refund per order).")
    if eligible:
        reasons.append(f"Delivered {days} days ago, inside the {s.return_window_days}-day window, and all items are returnable.")
    return {"order_id": o.order_number, "eligible": eligible, "status": o.status, "days_since_delivery": days,
            "return_window_days": s.return_window_days,
            "days_remaining": (s.return_window_days - days) if (days is not None and eligible) else None,
            "reasons": reasons, "order_total": o.total}


def check_return_eligibility(ctx: ToolContext, order_id: str) -> dict:
    return _eligibility(ctx, _load_owned_order(ctx, order_id))


def _validate_reason(reason: str) -> str:
    reason = " ".join((reason or "").split())
    if not 3 <= len(reason) <= 255:
        raise ToolError("Please give a short reason (3-255 characters).")
    return reason


def create_return_request(ctx: ToolContext, order_id: str, reason: str) -> dict:
    o = _load_owned_order(ctx, order_id)
    reason = _validate_reason(reason)
    elig = _eligibility(ctx, o)
    if not elig["eligible"]:
        raise ToolError("This order isn't eligible for return: " + " ".join(elig["reasons"]))
    existing = ctx.db.scalar(select(ReturnRequest).where(ReturnRequest.order_id == o.id, ReturnRequest.status == "open"))
    if existing:
        return {"rma_number": existing.rma_number, "order_id": o.order_number, "status": existing.status, "already_existed": True}
    rr = ReturnRequest(rma_number=f"RMA-{uuid.uuid4().hex[:6].upper()}", order_id=o.id, customer_id=o.customer_id, reason=reason)
    ctx.db.add(rr)
    ctx.db.commit()
    return {"rma_number": rr.rma_number, "order_id": o.order_number, "status": rr.status, "already_existed": False}


def refund_amount_for(order_total: float, reason: str) -> tuple[float, bool]:
    defective = any(w in reason.lower() for w in DEFECT_WORDS)
    amount = order_total if defective else max(0.0, order_total - RETURN_SHIPPING_FEE)
    return round(amount, 2), defective


def create_refund_request(ctx: ToolContext, order_id: str, reason: str) -> dict:
    if ctx.user.role != "customer":
        raise ToolError("Refund requests are created on behalf of the customer who owns the order.")
    o = _load_owned_order(ctx, order_id)
    reason = _validate_reason(reason)
    elig = _eligibility(ctx, o)
    if not elig["eligible"]:
        raise ToolError("A refund can't be requested for this order: " + " ".join(elig["reasons"]))
    amount, defective = refund_amount_for(o.total, reason)
    rf = RefundRequest(refund_number=f"RF-{uuid.uuid4().hex[:6].upper()}", order_id=o.id, customer_id=o.customer_id,
                       conversation_id=ctx.conversation_id, amount=amount, reason=reason, status="pending",
                       active_key="active")
    ctx.db.add(rf)
    try:
        ctx.db.commit()
    except IntegrityError:  # concurrent duplicate caught by the unique constraint
        ctx.db.rollback()
        raise ToolError(f"A refund for {o.order_number} is already in progress.")
    return {"refund_id": rf.refund_number, "order_id": o.order_number, "amount": amount, "status": "pending",
            "return_shipping_fee_waived": defective, "requires_human_approval": True}


def get_refund_status(ctx: ToolContext, order_id: str | None = None, refund_id: str | None = None) -> dict:
    stmt = select(RefundRequest)
    if refund_id:
        stmt = stmt.where(RefundRequest.refund_number == refund_id.strip().upper())
    elif order_id:
        o = _load_owned_order(ctx, order_id)
        stmt = stmt.where(RefundRequest.order_id == o.id)
    else:
        stmt = stmt.where(RefundRequest.customer_id == ctx.user.id)
    if ctx.user.role != "admin":
        stmt = stmt.where(RefundRequest.customer_id == ctx.user.id)
    rows = ctx.db.scalars(stmt.order_by(RefundRequest.created_at.desc())).all()
    return {"count": len(rows), "refunds": [
        {"refund_id": r.refund_number, "order_id": r.order.order_number, "amount": r.amount, "status": r.status,
         "requested_on": _fmt_date(r.created_at), "decided_on": _fmt_date(r.decided_at)} for r in rows]}


TOOL_FUNCTIONS = {
    "get_order_status": get_order_status,
    "get_order_details": get_order_details,
    "get_customer_orders": get_customer_orders,
    "search_products": search_products,
    "search_knowledge_base": search_knowledge_base,
    "check_return_eligibility": check_return_eligibility,
    "create_return_request": create_return_request,
    "create_refund_request": create_refund_request,
    "get_refund_status": get_refund_status,
}
