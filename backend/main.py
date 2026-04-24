from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .auth import auth_provider_mode, issue_mock_token, validate_token
from .coach import build_coach_context, generate_coach_text, stream_tokens
from .schemas import ForecastRequest, GoalPlanRequest, LoginRequest, PortfolioRequest, ProfileRequest
from .services import compute_goal_plan, fetch_macro_snapshot, live_forecast
from .storage import PersistenceStore


class HealthResponse(BaseModel):
    status: str
    backend_mode: str
    environment: str


app = FastAPI(title="WealthSense API", version="0.1.0")
store = PersistenceStore()
FREE_DAILY_COACH_CAP = 10

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
def forecast(payload: ForecastRequest) -> dict[str, object]:
    try:
        macro = fetch_macro_snapshot()
        result = live_forecast(ticker=payload.ticker.upper(), horizon_days=payload.horizon_days, macro=macro)
        store.save_forecast(result)
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/goal-plan")
def goal_plan(payload: GoalPlanRequest) -> dict[str, float]:
    try:
        result = compute_goal_plan(payload.model_dump())
        persisted = payload.model_dump()
        persisted.update(result)
        store.save_goal_plan(persisted)
        return result
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
        raise HTTPException(status_code=429, detail="Daily free coach limit reached (10 messages).")

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


def _require_token(authorization: Optional[str]) -> str:
    try:
        return validate_token(authorization)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

