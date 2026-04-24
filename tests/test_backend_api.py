from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "backend_mode" in data


def test_goal_plan_endpoint() -> None:
    resp = client.post(
        "/goal-plan",
        json={
            "current_balance": 20000,
            "monthly_contribution": 1000,
            "target_amount": 120000,
            "years": 5,
            "annual_return_mean": 0.08,
            "annual_volatility": 0.16,
            "simulations": 1200,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 0.0 <= data["success_probability"] <= 1.0
    assert data["expected_terminal_value"] > 0


def test_auth_profile_dashboard_flow() -> None:
    login = client.post("/auth/login", json={"email": "demo@example.com", "name": "Demo User"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    profile_resp = client.post(
        "/user/profile",
        json={
            "name": "Demo User",
            "email": "demo@example.com",
            "risk_tolerance": "balanced",
            "goals": [{"goal_name": "Home", "target_amount": 90000, "target_date": "2030-01-01"}],
        },
        headers=headers,
    )
    assert profile_resp.status_code == 200

    portfolio_resp = client.post(
        "/portfolio",
        json={"name": "Starter Portfolio", "assets": [{"ticker": "SPY", "allocation": 0.6}, {"ticker": "QQQ", "allocation": 0.4}]},
        headers=headers,
    )
    assert portfolio_resp.status_code == 200

    dashboard = client.get("/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert "success_probability" in dashboard.json()


def test_coach_stream_endpoint() -> None:
    login = client.post("/auth/login", json={"email": "coach@example.com", "name": "Coach User"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/coach/stream", params={"question": "Am I on track?"}, headers=headers)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "data:" in resp.text

