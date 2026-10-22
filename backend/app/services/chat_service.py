import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.agents.graph import AgentContext, get_support_graph
from app.agents.llm import llm_mode
from app.models import AgentExecutionLog, Conversation, Message, User
from app.observability import configure_logging

log = configure_logging()


def get_owned_conversation(
    db: Session, user: User, conversation_id: str, session_id: str
) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if (
        conv is None
        or conv.user_id != user.id
        or conv.session_id != session_id
    ):
        raise HTTPException(404, "Conversation not found.")
    return conv


def send_message(
    db: Session,
    user: User,
    text: str,
    conversation_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    if not session_id:
        raise HTTPException(401, "Please sign in again.")
    if conversation_id:
        conv = get_owned_conversation(db, user, conversation_id, session_id)
    else:
        conv = Conversation(
            id=str(uuid.uuid4()),
            user_id=user.id,
            session_id=session_id,
            title=text[:60],
        )
        db.add(conv)
        db.commit()
    db.add(Message(conversation_id=conv.id, role="user", content=text, meta={}))
    db.commit()
    t0 = time.perf_counter()
    try:
        state = get_support_graph().invoke(
            {"messages": [HumanMessage(content=text)]},
            {"configurable": {"thread_id": conv.id}},
            context=AgentContext(db=db, user=user, conversation_id=conv.id),
        )
        reply = state["messages"][-1].content
        ok = True
    except Exception as e:  # keep the chat usable; log the failure for the dashboard
        db.rollback()
        log.exception("graph failure conversation=%s", conv.id)
        state, reply, ok = {}, "Something went wrong while handling that request. Please try again.", False
        db.add(AgentExecutionLog(conversation_id=conv.id, user_id=user.id, agent="graph", success=False,
                                 error=f"{type(e).__name__}: {e}"[:500]))
    latency = round((time.perf_counter() - t0) * 1000, 1)
    meta = {
        "intents": state.get("intents", []), "agent_path": state.get("agent_path", []),
        "tools": [{k: t[k] for k in ("tool", "success", "latency_ms")} for t in state.get("trace", [])],
        "citations": state.get("citations", []), "active_order_id": state.get("active_order_id"),
        "order_from_memory": state.get("order_from_memory", False), "router": state.get("router"),
        "pending_refund": state.get("pending_refund"), "latency_ms": latency, "mode": llm_mode(), "ok": ok,
    }
    msg = Message(conversation_id=conv.id, role="assistant", content=reply, meta=meta)
    db.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"conversation_id": conv.id, "message": serialize_message(msg), "full_trace": state.get("trace", [])}


def serialize_message(m: Message) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content, "meta": m.meta or {},
            "created_at": iso(m.created_at)}


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()
