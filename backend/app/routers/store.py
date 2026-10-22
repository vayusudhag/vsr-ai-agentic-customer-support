from app.services.chat_service import iso
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, RefundRequest, ReturnRequest, User
from app.schemas import ReturnIn
from app.security import get_current_user
from app.tools.core import ToolContext, ToolError, check_return_eligibility, create_return_request, \
    get_customer_orders, get_order_details, get_refund_status, run_tool, search_products

router = APIRouter(prefix="/api", tags=["store"])


def _ctx(db, user):
    return ToolContext(db=db, user=user, agent="api")


@router.get("/products")
def products(q: str = "", category: str | None = None, max_price: float | None = Query(None, gt=0),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not q:
        stmt = select(Product)
        if category:
            stmt = stmt.where(Product.category == category)
        if max_price:
            stmt = stmt.where(Product.price <= max_price)
        return [{"sku": p.sku, "name": p.name, "category": p.category, "price": p.price, "rating": p.rating,
                 "stock": p.stock, "description": p.description, "tags": p.tags, "returnable": p.returnable}
                for p in db.scalars(stmt.order_by(Product.category, Product.price)).all()]
    try:
        return search_products(_ctx(db, user), query=q, category=category, max_price=max_price, limit=10)["products"]
    except ToolError as e:
        raise HTTPException(422, str(e))


@router.get("/orders")
def my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ctx = _ctx(db, user)
    out = []
    for o in get_customer_orders(ctx, limit=50)["orders"]:
        d = get_order_details(ctx, o["order_id"])
        d["return_eligibility"] = check_return_eligibility(ctx, o["order_id"])
        out.append(d)
    return out


@router.get("/orders/{order_id}")
def order(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return get_order_details(_ctx(db, user), order_id)
    except ToolError as e:
        raise HTTPException(404, str(e))


@router.get("/returns")
def my_returns(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rets = db.scalars(select(ReturnRequest).where(ReturnRequest.customer_id == user.id)
                      .order_by(ReturnRequest.created_at.desc())).all()
    return {
        "returns": [{"rma_number": r.rma_number, "order_id": r.order.order_number, "reason": r.reason,
                     "status": r.status, "created_at": iso(r.created_at)} for r in rets],
        "refunds": get_refund_status(_ctx(db, user))["refunds"],
    }


@router.post("/returns")
def start_return(body: ReturnIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return run_tool(_ctx(db, user), "create_return_request", create_return_request,
                        order_id=body.order_id, reason=body.reason)
    except ToolError as e:
        raise HTTPException(422, str(e))
