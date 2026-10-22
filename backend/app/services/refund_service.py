from fastapi import HTTPException
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.agents.graph import AgentContext, get_refund_graph
from app.models import RefundRequest, User
from app.services.chat_service import iso


def decide_refund(db: Session, admin: User, refund_number: str, decision: str, note: str | None) -> dict:
    if decision not in ("approved", "rejected"):
        raise HTTPException(422, "Decision must be 'approved' or 'rejected'.")
    rf = db.query(RefundRequest).filter_by(refund_number=refund_number).one_or_none()
    if rf is None:
        raise HTTPException(404, "Refund request not found.")
    if admin.role != "admin":
        raise HTTPException(403, "Admin role required.")
    if rf.customer_id == admin.id:
        raise HTTPException(403, "You can't decide on your own refund request.")
    if rf.status != "pending":
        raise HTTPException(409, f"Refund {refund_number} was already {rf.status}.")
    if not rf.workflow_thread_id:
        raise HTTPException(409, "No paused workflow is attached to this refund.")
    graph = get_refund_graph()
    cfg = {"configurable": {"thread_id": rf.workflow_thread_id}}
    snapshot = graph.get_state(cfg)
    if "human_approval" not in (snapshot.next or ()):
        raise HTTPException(409, "This refund's workflow is not waiting for approval.")
    customer = db.get(User, rf.customer_id)
    result = graph.invoke(Command(resume={"decision": decision, "approver_id": admin.id, "note": note}), cfg,
                          context=AgentContext(db=db, user=customer, conversation_id=rf.conversation_id or ""))
    if result.get("outcome") == "already_decided":
        raise HTTPException(409, f"Refund {refund_number} was already decided.")
    db.refresh(rf)
    return {"refund_id": rf.refund_number, "status": rf.status, "decided_at": iso(rf.decided_at),
            "approved_by": admin.full_name, "simulated_transaction_id": rf.simulated_transaction_id,
            "workflow_completed": not graph.get_state(cfg).next}
