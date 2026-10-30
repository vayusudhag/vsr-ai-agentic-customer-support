import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="vsr_ai_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["CHROMA_PATH"] = f"{_tmp}/chroma"
os.environ["CHECKPOINT_DB_PATH"] = f"{_tmp}/checkpoints.sqlite"
os.environ["LLM_PROVIDER"] = "none"
os.environ["EMBEDDING_PROVIDER"] = "hashing"
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["CHAT_RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-use-0123456789"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _bootstrap():
    from app.rag.ingest import ingest
    from app.seed import seed

    seed()
    ingest()
    yield


@pytest.fixture
def fresh_db():
    """Reseed for tests that mutate refunds/returns."""
    from app.seed import seed

    seed()
    yield


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def pardha(client):
    return _login(client, "pardha.saradhi@example.com", "demo1234")


@pytest.fixture
def pavan(client):
    return _login(client, "pavan.y@example.com", "demo1234")


@pytest.fixture
def admin(client):
    return _login(client, "gopireddy.vsr@example.com", "admin1234")


@pytest.fixture
def ctx():
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User
    from app.tools.core import ToolContext

    db = SessionLocal()

    def make(email="pardha.saradhi@example.com"):
        return ToolContext(db=db, user=db.scalar(select(User).where(User.email == email)))

    yield make
    db.close()


def chat(client, headers, message, conversation_id=None):
    r = client.post("/api/chat", json={"message": message, "conversation_id": conversation_id}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()
