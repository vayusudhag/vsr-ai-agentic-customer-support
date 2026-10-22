from app.observability import redact


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_rejects_bad_password(client):
    assert client.post("/api/auth/login", json={"email": "pardha.saradhi@example.com", "password": "nope"}).status_code == 401


def test_endpoints_require_auth(client):
    for path in ("/api/orders", "/api/chat/conversations", "/api/admin/metrics", "/api/products"):
        assert client.get(path).status_code == 401


def test_admin_endpoints_forbidden_for_customers(client, alex):
    assert client.get("/api/admin/metrics", headers=alex).status_code == 403
    assert client.get("/api/admin/refunds", headers=alex).status_code == 403


def test_input_validation(client, alex):
    assert client.post("/api/chat", json={"message": "   "}, headers=alex).status_code == 422
    assert client.post("/api/chat", json={"message": "x" * 2001}, headers=alex).status_code == 422


def test_orders_endpoint_scoped(client, alex):
    ids = [o["order_id"] for o in client.get("/api/orders", headers=alex).json()]
    assert "ORD-1001" in ids and "ORD-1006" not in ids
    assert client.get("/api/orders/ORD-1006", headers=alex).status_code == 404


def test_products_endpoint(client, alex):
    assert len(client.get("/api/products", headers=alex).json()) >= 20


def test_metrics_come_from_data(client, alex, admin):
    before = client.get("/api/admin/metrics", headers=admin).json()["total_customer_requests"]
    client.post("/api/chat", json={"message": "Where is ORD-1001?"}, headers=alex)
    after = client.get("/api/admin/metrics", headers=admin).json()
    assert after["total_customer_requests"] == before + 1
    assert after["agent_usage"] and after["avg_response_latency_ms"] is not None


def test_redaction():
    out = redact({"password": "secret", "note": "mail me at a.b@example.com, card 4111 1111 1111 1111"})
    assert out["password"] == "[REDACTED]" and "example.com" not in out["note"] and "4111" not in out["note"]


def test_rate_limit(monkeypatch, client):
    from app import main

    monkeypatch.setattr(main.settings, "rate_limit_per_minute", 3)
    main._hits.clear()
    codes = [client.get("/api/health").status_code for _ in range(5)]
    main._hits.clear()
    assert codes[:3] == [200, 200, 200] and 429 in codes[3:]


def test_login_rate_limit_is_separate_and_strict(monkeypatch, client):
    from app import main

    monkeypatch.setattr(main.settings, "login_rate_limit_per_minute", 2)
    main._hits.clear()
    codes = [client.post("/api/auth/login", json={"email": "x@example.com", "password": "bad"}).status_code for _ in range(3)]
    health = client.get("/api/health").status_code  # general bucket unaffected
    main._hits.clear()
    assert codes == [401, 401, 429] and health == 200


def test_forwarded_for_only_trusted_when_enabled(monkeypatch, client):
    from app import main

    monkeypatch.setattr(main.settings, "rate_limit_per_minute", 1)
    monkeypatch.setattr(main.settings, "trust_proxy_headers", False)
    main._hits.clear()
    a = client.get("/api/health", headers={"X-Forwarded-For": "10.0.0.1"}).status_code
    b = client.get("/api/health", headers={"X-Forwarded-For": "10.0.0.2"}).status_code  # spoofed header ignored -> same client
    monkeypatch.setattr(main.settings, "trust_proxy_headers", True)
    main._hits.clear()
    c = client.get("/api/health", headers={"X-Forwarded-For": "10.0.0.1"}).status_code
    d = client.get("/api/health", headers={"X-Forwarded-For": "10.0.0.2"}).status_code  # distinct clients behind proxy
    main._hits.clear()
    assert (a, b, c, d) == (200, 429, 200, 200)
