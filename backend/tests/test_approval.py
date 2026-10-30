from app.agents.graph import get_refund_graph
from tests.conftest import chat


def _request_refund(client, headers, order="ORD-1002"):
    r = chat(client, headers, f"I want a refund for {order}, the watch is broken")
    pending = r["message"]["meta"]["pending_refund"]
    assert pending and pending["status"] == "pending" and pending["interrupted"]
    return r["conversation_id"], pending


def test_refund_pauses_for_human_approval(client, pardha, admin, fresh_db):
    cid, p = _request_refund(client, pardha)
    snap = get_refund_graph().get_state({"configurable": {"thread_id": p["workflow_thread_id"]}})
    assert snap.next == ("human_approval",)  # persisted, paused workflow
    listed = client.get("/api/admin/refunds?status=pending", headers=admin).json()
    assert [x["refund_id"] for x in listed] == [p["refund_id"]]


def test_customer_cannot_approve(client, pardha, fresh_db):
    _, p = _request_refund(client, pardha)
    r = client.post(f"/api/admin/refunds/{p['refund_id']}/decision", json={"decision": "approved"}, headers=pardha)
    assert r.status_code == 403


def test_admin_approval_resumes_workflow_and_notifies(client, pardha, admin, fresh_db):
    cid, p = _request_refund(client, pardha)
    r = client.post(f"/api/admin/refunds/{p['refund_id']}/decision",
                    json={"decision": "approved", "note": "Photos verified"}, headers=admin)
    body = r.json()
    assert r.status_code == 200 and body["status"] == "approved" and body["workflow_completed"]
    assert body["approved_by"].startswith("Gopireddy VSR") and body["simulated_transaction_id"].startswith("SIM-TXN-")
    msgs = client.get(f"/api/chat/conversations/{cid}", headers=pardha).json()["messages"]
    assert "approved" in msgs[-1]["content"] and p["refund_id"] in msgs[-1]["content"]
    row = client.get("/api/admin/refunds", headers=admin).json()[0]
    assert row["approved_by"] and row["decided_at"]


def test_duplicate_decision_blocked(client, pardha, admin, fresh_db):
    _, p = _request_refund(client, pardha)
    url = f"/api/admin/refunds/{p['refund_id']}/decision"
    assert client.post(url, json={"decision": "rejected", "note": "No"}, headers=admin).status_code == 200
    assert client.post(url, json={"decision": "approved"}, headers=admin).status_code == 409


def test_rejection_flow_and_new_request_allowed_after_rejection(client, pardha, admin, fresh_db):
    cid, p = _request_refund(client, pardha)
    client.post(f"/api/admin/refunds/{p['refund_id']}/decision",
                json={"decision": "rejected", "note": "Item shows water damage"}, headers=admin)
    msgs = client.get(f"/api/chat/conversations/{cid}", headers=pardha).json()["messages"]
    assert "not approved" in msgs[-1]["content"] and "water damage" in msgs[-1]["content"]
    # second refund for same order now allowed (rejected requests are inactive)
    _request_refund(client, pardha)


def test_second_refund_while_pending_is_refused(client, pardha, fresh_db):
    cid, _ = _request_refund(client, pardha)
    r = chat(client, pardha, "I want a refund for ORD-1002", cid)
    assert "already pending" in r["message"]["content"]
