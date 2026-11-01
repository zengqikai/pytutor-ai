"""限流中间件的离线测试（不启动真实服务）。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware


def make_client(monkeypatch, api_limit=2, auth_limit=1, enabled=True, trust_proxy=False):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", enabled)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", api_limit)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_PER_MINUTE", auth_limit)
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", trust_proxy)

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/api/v1/ping")
    async def ping():
        return {"ok": True}

    @app.post("/api/v1/auth/login")
    async def login():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"ok": True}

    return TestClient(app)


def test_api_limit_returns_429(monkeypatch):
    client = make_client(monkeypatch, api_limit=2)
    assert client.get("/api/v1/ping").status_code == 200
    assert client.get("/api/v1/ping").status_code == 200
    resp = client.get("/api/v1/ping")
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) >= 1


def test_auth_has_separate_tighter_budget(monkeypatch):
    client = make_client(monkeypatch, api_limit=5, auth_limit=1)
    assert client.post("/api/v1/auth/login").status_code == 200
    assert client.post("/api/v1/auth/login").status_code == 429
    # 普通 API 不受 auth 桶影响
    assert client.get("/api/v1/ping").status_code == 200


def test_health_and_options_are_not_limited(monkeypatch):
    client = make_client(monkeypatch, api_limit=1)
    for _ in range(5):
        assert client.get("/api/v1/health").status_code == 200
    assert client.options("/api/v1/ping").status_code in (200, 405)


def test_disable_switch(monkeypatch):
    client = make_client(monkeypatch, api_limit=1, enabled=False)
    for _ in range(5):
        assert client.get("/api/v1/ping").status_code == 200


def test_clients_are_counted_separately(monkeypatch):
    """可信反代场景：TRUST_PROXY_HEADERS=True 时按 X-Forwarded-For 分桶。"""
    client = make_client(monkeypatch, api_limit=1, trust_proxy=True)
    assert client.get("/api/v1/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.get("/api/v1/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    assert client.get("/api/v1/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429


def test_forwarded_for_is_ignored_by_default(monkeypatch):
    """默认不采信 X-Forwarded-For：伪造头换 IP 不能绕过登录限流。"""
    client = make_client(monkeypatch, auth_limit=1)
    assert client.post("/api/v1/auth/login", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    resp = client.post("/api/v1/auth/login", headers={"X-Forwarded-For": "9.9.9.9"})
    assert resp.status_code == 429
