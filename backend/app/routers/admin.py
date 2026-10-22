from app.services.chat_service import iso
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ApprovalRecord, RefundRequest, User
from app.schemas import DecisionIn
from app.security import require_admin
from app.services.metrics_service import dashboard_metrics
from app.services.refund_service import decide_refund

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/metrics")
def metrics(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return dashboard_metrics(db)


@router.get("/refunds")
def refunds(status: str | None = None, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(RefundRequest).order_by(RefundRequest.created_at.desc())
    if status:
        stmt = stmt.where(RefundRequest.status == status)
    out = []
    for r in db.scalars(stmt).all():
        appr = db.scalar(select(ApprovalRecord).where(ApprovalRecord.refund_request_id == r.id))
        out.append({"refund_id": r.refund_number, "order_id": r.order.order_number, "customer": r.customer.full_name,
                    "customer_email": r.customer.email, "amount": r.amount, "order_total": r.order.total,
                    "reason": r.reason, "status": r.status, "created_at": iso(r.created_at),
                    "decided_at": iso(r.decided_at),
                    "approved_by": appr.approver.full_name if appr else None, "note": appr.note if appr else None,
                    "simulated_transaction_id": r.simulated_transaction_id,
                    "workflow_thread_id": r.workflow_thread_id})
    return out


@router.post("/refunds/{refund_id}/decision")
def decide(refund_id: str, body: DecisionIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if get_settings().environment.lower() == "production":
        raise HTTPException(
            status_code=403,
            detail="Refund decisions are disabled in the public demo."
        )
    return decide_refund(db, admin, refund_id, body.decision, body.note)
