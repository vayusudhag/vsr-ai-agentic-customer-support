from app.services.chat_service import iso
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Conversation, User
from app.schemas import ChatIn
from app.security import get_current_user, get_current_session
from app.services.chat_service import get_owned_conversation, send_message, serialize_message

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db), session_id: str = Depends(get_current_session)):
    res = send_message(db, user, body.message, body.conversation_id, session_id=session_id)
    res.pop("full_trace", None)
    return res


@router.get("/conversations")
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db), session_id: str = Depends(get_current_session)):
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id, Conversation.session_id == session_id)
                      .order_by(Conversation.updated_at.desc())).all()
    return [{"id": c.id, "title": c.title, "updated_at": iso(c.updated_at),
             "message_count": len(c.messages)} for c in rows]


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db), session_id: str = Depends(get_current_session)):
    c = get_owned_conversation(db, user, conversation_id, session_id)
    return {"id": c.id, "title": c.title, "messages": [serialize_message(m) for m in c.messages]}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db), session_id: str = Depends(get_current_session)):
    c = get_owned_conversation(db, user, conversation_id, session_id)
    db.delete(c)
    db.commit()
