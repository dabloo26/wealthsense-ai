from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
import numpy as np
from pydantic import BaseModel
import sentry_sdk

from .auth import auth_provider_mode, issue_mock_token, validate_token
from .coach import build_coach_context, generate_coach_text, stream_tokens
from .drift import detect_forecast_drift
import pandas as pd

from .schemas import AllocationRequest, ForecastRequest, GoalPlanRequest, LoginRequest, PortfolioRequest, ProfileRequest
from .services import compute_goal_plan, fetch_macro_snapshot, forecast_detail, live_forecast
from .storage import PersistenceStore
from wealthsense_ai.strategy import suggest_allocation


class HealthResponse(BaseModel):
    status: str
    backend_mode: str
    environment: str


app = FastAPI(title="WealthSense API", version="0.1.0")
store = PersistenceStore()
FREE_DAILY_COACH_CAP = 10
FREE_ASSET_CAP = 3
FREE_HORIZON_CAP_DAYS = 30
MODEL_VERSION = os.getenv("MODEL_VERSION", "ensemble-v1")

if os.getenv("SENTRY_DSN", "").strip():
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("APP_ENV", "local"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next: object) -> object:
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = (time.perf_counter() - start) * 1000
    user_id = "anonymous"
    auth_header = request.headers.get("authorization")
    if auth_header:
        try:
            user_id = validate_token(auth_header)
        except Exception:
            user_id = "invalid_token"
    logger.bind(
        user_id=user_id,
        endpoint=request.url.path,
        method=request.method,
        status_code=response.status_code,
        latency_ms=round(latency_ms, 2),
        model_version=MODEL_VERSION,
    ).info("request_completed")
    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        backend_mode=store.backend_mode(),
        environment=os.getenv("APP_ENV", "local"),
    )


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, str]:
    token = issue_mock_token(payload.email)
    if not store.get_user_profile(token):
        store.save_user_profile(
            token,
            {
                "name": payload.name,
                "email": payload.email,
                "risk_tolerance": "balanced",
                "goals": [],
                "tier": "free",
            },
        )
    return {"access_token": token, "provider_mode": auth_provider_mode()}


@app.post("/user/profile")
def upsert_profile(payload: ProfileRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, str]:
    token = _require_token(authorization)
    store.save_user_profile(token, payload.model_dump())
    return {"status": "saved"}


@app.get("/user/profile")
def get_profile(authorization: Optional[str] = Header(default=None)) -> dict[str, object]:
    token = _require_token(authorization)
    profile = store.get_user_profile(token)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.post("/portfolio")
def save_portfolio(payload: PortfolioRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, str]:
    token = _require_token(authorization)
    _enforce_limits(token=token, route_name="portfolio", payload=payload.model_dump())
    store.save_portfolio(token, payload.model_dump())
    return {"status": "saved"}


@app.get("/dashboard")
def dashboard(authorization: Optional[str] = Header(default=None)) -> dict[str, object]:
    token = _require_token(authorization)
    profile = store.get_user_profile(token) or {}
    portfolio = store.latest_portfolio(token) or {}
    goal = store.latest_goal_plan() or {}
    goal_prob = float(goal.get("success_probability", 0.0))
    insight = (
        "On track, keep contributions steady."
        if goal_prob >= 0.65
        else "Success odds are low; increasing monthly contribution may help."
    )
    return {
        "profile": profile,
        "latest_portfolio": portfolio,
        "latest_goal_plan": goal,
        "success_probability": goal_prob,
        "insight": insight,
    }


@app.post("/digest/preview")
def weekly_digest_preview(authorization: Optional[str] = Header(default=None)) -> dict[str, str]:
    token = _require_token(authorization)
    profile = store.get_user_profile(token) or {}
    email = str(profile.get("email", "user@example.com"))
    return {
        "status": "mock-sent",
        "recipient": email,
        "provider_mode": "sendgrid-mock",
    }


@app.post("/forecast")
def forecast(payload: ForecastRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, object]:
    try:
        token: Optional[str] = None
        if authorization:
            token = _require_token(authorization)
        tier = _tier_for_token(token)
        if payload.horizon_days > _horizon_cap_for_tier(tier):
            raise HTTPException(
                status_code=402,
                detail=f"Free plan supports up to {FREE_HORIZON_CAP_DAYS}-day horizon. Upgrade to Pro for up to 365 days.",
            )
        macro = fetch_macro_snapshot()
        result = live_forecast(ticker=payload.ticker.upper(), horizon_days=payload.horizon_days, macro=macro)
        store.save_forecast(result)
        if token:
            store.log_audit_event(token=token, event_type="forecast_saved", payload={"ticker": payload.ticker.upper(), "horizon_days": payload.horizon_days})
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/forecast-detail/{ticker}")
def forecast_detail_route(ticker: str, horizon_days: int = Query(default=30, ge=7, le=365)) -> dict[str, object]:
    try:
        return forecast_detail(ticker=ticker.upper(), horizon_days=horizon_days)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/goal-plan")
def goal_plan(payload: GoalPlanRequest) -> dict[str, object]:
    try:
        result = compute_goal_plan(payload.model_dump())
        persisted = payload.model_dump()
        persisted.update(result)
        store.save_goal_plan(persisted)
        store.log_audit_event(token="system", event_type="goal_plan_saved", payload={"target_amount": payload.target_amount, "years": payload.years})
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/coach/stream")
def coach_stream(
    question: str = Query(..., min_length=2, max_length=1200),
    authorization: Optional[str] = Header(default=None),
) -> StreamingResponse:
    token = _require_token(authorization)
    profile = store.get_user_profile(token) or {}
    tier = str(profile.get("tier", "free")).lower()
    daily_count = store.count_daily_coach_messages(token)
    if tier == "free" and daily_count >= FREE_DAILY_COACH_CAP:
        raise HTTPException(
            status_code=402,
            detail="Daily free coach limit reached (10 messages). Upgrade to Pro for unlimited coach access.",
        )

    portfolio = store.latest_portfolio(token) or {}
    goal_plan = store.latest_goal_plan()
    latest_forecast = store.latest_forecast(token)
    macro = fetch_macro_snapshot()
    context = build_coach_context(
        profile=profile,
        portfolio=portfolio,
        latest_goal_plan=goal_plan,
        latest_forecast=latest_forecast,
        macro=macro,
    )
    answer = generate_coach_text(context=context, question=question)

    store.log_audit_event(token=token, event_type="coach_message", payload={"question": question, "answer": answer, "tier": tier})

    def event_stream() -> object:
        for token_piece in stream_tokens(answer):
            yield f"data: {token_piece}\n\n"
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/billing/start-trial")
def start_trial(authorization: Optional[str] = Header(default=None)) -> dict[str, str]:
    token = _require_token(authorization)
    trial_ends = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    store.update_user_profile(token, {"tier": "pro_trial", "trial_ends_at": trial_ends})
    store.log_audit_event(token=token, event_type="billing_trial_started", payload={"trial_ends_at": trial_ends})
    return {"status": "trial_started", "trial_ends_at": trial_ends}


@app.post("/billing/checkout")
def billing_checkout(authorization: Optional[str] = Header(default=None)) -> dict[str, str]:
    token = _require_token(authorization)
    pub_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not pub_key:
        url = "https://billing.mock/checkout?plan=pro"
        store.log_audit_event(token=token, event_type="billing_checkout_mock", payload={"url": url})
        return {"mode": "mock", "checkout_url": url}
    # Minimal real-mode stub (swappable with stripe checkout session creation).
    return {"mode": "stripe", "checkout_url": "https://checkout.stripe.com/c/pay/mock"}


@app.post("/billing/portal")
def billing_portal(authorization: Optional[str] = Header(default=None)) -> dict[str, str]:
    token = _require_token(authorization)
    if not os.getenv("STRIPE_SECRET_KEY", "").strip():
        return {"mode": "mock", "portal_url": "https://billing.mock/portal"}
    return {"mode": "stripe", "portal_url": "https://billing.stripe.com/p/session/mock"}


@app.post("/billing/webhook")
def billing_webhook(payload: dict[str, object]) -> dict[str, str]:
    event_type = str(payload.get("type", ""))
    data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
    email = str(data.get("email", ""))
    token = str(data.get("token", "")) or (store.find_token_by_email(email) if email else None)
    if not token:
        return {"status": "ignored", "reason": "no_user_match"}

    if event_type in {"customer.subscription.updated", "checkout.session.completed"}:
        tier = str(data.get("tier", "pro")).lower()
        store.update_user_profile(token, {"tier": tier})
        store.log_audit_event(token=token, event_type="billing_tier_updated", payload={"tier": tier, "event": event_type})
        return {"status": "updated", "tier": tier}
    if event_type in {"customer.subscription.deleted", "customer.subscription.canceled"}:
        store.update_user_profile(token, {"tier": "free"})
        store.log_audit_event(token=token, event_type="billing_tier_updated", payload={"tier": "free", "event": event_type})
        return {"status": "updated", "tier": "free"}
    return {"status": "ignored", "event": event_type}


@app.get("/ops/drift")
def drift_status() -> dict[str, object]:
    baseline = float(os.getenv("DRIFT_BASELINE_MAE", "0.01"))
    threshold_multiplier = float(os.getenv("DRIFT_THRESHOLD_MULTIPLIER", "2.0"))
    report = detect_forecast_drift(
        forecasts_path="artifacts/forecasts.csv",
        baseline_mae=baseline,
        threshold_multiplier=threshold_multiplier,
    )
    return {"status": "ok", **report}


@app.get("/account/export")
def account_export(authorization: Optional[str] = Header(default=None)) -> dict[str, object]:
    token = _require_token(authorization)
    data = store.export_account_data(token)
    store.log_audit_event(token=token, event_type="account_export", payload={"records": len(data.get("recent_audit_events", []))})
    return {"status": "ok", "exported_at": datetime.now(timezone.utc).isoformat(), "data": data}


@app.delete("/account/delete")
def account_delete(authorization: Optional[str] = Header(default=None)) -> dict[str, str]:
    token = _require_token(authorization)
    store.log_audit_event(token=token, event_type="account_delete_requested", payload={})
    store.delete_account_data(token)
    return {"status": "deleted"}


@app.post("/allocation/suggest")
def allocation_suggest(
    payload: AllocationRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, object]:
    token = _require_token(authorization)
    forecasts_path = Path("artifacts/forecasts.csv")
    if forecasts_path.exists():
        df = pd.read_csv(forecasts_path)
        ensemble = df[df["model"] == "ensemble"].copy()
        exp_returns = []
        for ticker in payload.tickers:
            recent = ensemble[ensemble["ticker"] == ticker].tail(20)
            exp_returns.append(float(recent["predicted"].mean()) if not recent.empty else 0.0)
    else:
        exp_returns = [0.0 for _ in payload.tickers]

    alloc = suggest_allocation(
        tickers=payload.tickers,
        expected_returns=np.array(exp_returns, dtype=float),
        risk_tolerance=payload.risk_tolerance.lower(),
        max_weight=0.4,
    )
    store.log_audit_event(token=token, event_type="allocation_suggested", payload={"tickers": payload.tickers, "risk_tolerance": payload.risk_tolerance, "allocation": alloc})
    return {
        "allocation": alloc,
        "disclaimer": "Not financial advice. Suggested weights are model-driven estimates with uncertainty.",
    }


def _require_token(authorization: Optional[str]) -> str:
    try:
        return validate_token(authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _tier_for_token(token: Optional[str]) -> str:
    if not token:
        return "free"
    profile = store.get_user_profile(token) or {}
    return str(profile.get("tier", "free")).lower()


def _horizon_cap_for_tier(tier: str) -> int:
    return 365 if tier in {"pro", "advisor", "pro_trial"} else FREE_HORIZON_CAP_DAYS


def _enforce_limits(token: str, route_name: str, payload: dict[str, object]) -> None:
    tier = _tier_for_token(token)
    if route_name == "portfolio" and tier == "free":
        assets = payload.get("assets", [])
        if isinstance(assets, list) and len(assets) > FREE_ASSET_CAP:
            raise HTTPException(
                status_code=402,
                detail=f"Free plan supports up to {FREE_ASSET_CAP} assets. Upgrade to Pro for unlimited assets.",
            )

