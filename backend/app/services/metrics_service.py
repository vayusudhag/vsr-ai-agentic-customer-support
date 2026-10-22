from app.services.chat_service import iso
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import AgentExecutionLog, ApprovalRecord, Conversation, Message, RefundRequest, ReturnRequest


def dashboard_metrics(db: Session) -> dict:
    """All values computed from live application data."""
    total_conv = db.scalar(select(func.count(Conversation.id))) or 0
    total_requests = db.scalar(select(func.count(Message.id)).where(Message.role == "user")) or 0
    pending = db.scalar(select(func.count(RefundRequest.id)).where(RefundRequest.status == "pending")) or 0
    approved = db.scalar(select(func.count(RefundRequest.id)).where(RefundRequest.status == "approved")) or 0
    rejected = db.scalar(select(func.count(RefundRequest.id)).where(RefundRequest.status == "rejected")) or 0
    returns = db.scalar(select(func.count(ReturnRequest.id))) or 0
    failed_tools = db.scalar(select(func.count(AgentExecutionLog.id)).where(
        AgentExecutionLog.tool_name.is_not(None), AgentExecutionLog.success.is_(False))) or 0
    total_tools = db.scalar(select(func.count(AgentExecutionLog.id)).where(AgentExecutionLog.tool_name.is_not(None))) or 0
    assistant_msgs = db.scalars(select(Message.meta).where(Message.role == "assistant")).all()
    lat = sorted(m.get("latency_ms") for m in assistant_msgs if m and m.get("latency_ms") is not None)
    completed = sum(1 for m in assistant_msgs if m and m.get("ok"))
    agent_usage = db.execute(select(AgentExecutionLog.agent, func.count(AgentExecutionLog.id))
                             .where(AgentExecutionLog.tool_name.is_(None), AgentExecutionLog.agent != "graph")
                             .group_by(AgentExecutionLog.agent)).all()
    tool_usage = db.execute(select(AgentExecutionLog.tool_name, func.count(AgentExecutionLog.id),
                                   func.sum(case((AgentExecutionLog.success.is_(False), 1), else_=0)))
                            .where(AgentExecutionLog.tool_name.is_not(None))
                            .group_by(AgentExecutionLog.tool_name)).all()
    intents = db.execute(select(AgentExecutionLog.intent, func.count(AgentExecutionLog.id))
                         .where(AgentExecutionLog.agent == "supervisor").group_by(AgentExecutionLog.intent)).all()
    recent_fail = db.scalars(select(AgentExecutionLog).where(AgentExecutionLog.success.is_(False))
                             .order_by(AgentExecutionLog.id.desc()).limit(8)).all()
    approvals = db.scalar(select(func.count(ApprovalRecord.id))) or 0

    def pct(p):
        return round(lat[min(len(lat) - 1, int(p * len(lat)))], 1) if lat else None

    return {
        "total_conversations": total_conv, "total_customer_requests": total_requests,
        "pending_refund_approvals": pending, "completed_requests": completed,
        "refunds": {"pending": pending, "approved": approved, "rejected": rejected},
        "return_requests": returns, "approval_records": approvals,
        "failed_tool_calls": failed_tools, "total_tool_calls": total_tools,
        "avg_response_latency_ms": round(sum(lat) / len(lat), 1) if lat else None,
        "p95_response_latency_ms": pct(0.95),
        "agent_usage": [{"agent": a, "count": c} for a, c in sorted(agent_usage, key=lambda x: -x[1])],
        "tool_usage": [{"tool": t, "count": c, "failures": int(f or 0)} for t, c, f in sorted(tool_usage, key=lambda x: -x[1])],
        "intent_distribution": [{"intent": i, "count": c} for i, c in sorted(intents, key=lambda x: -x[1])],
        "recent_failures": [{"agent": r.agent, "tool": r.tool_name, "error": r.error,
                             "at": iso(r.created_at)} for r in recent_fail],
    }
