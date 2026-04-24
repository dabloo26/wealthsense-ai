from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _apply_custom_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f8fbff 0%, #eef6ff 100%);
            color: #0f172a;
        }
        .block-container {padding-top: 1.5rem; padding-bottom: 1.5rem;}
        [data-testid="stMetricValue"] {font-size: 1.4rem;}
        .ws-card {
            background: #ffffff;
            border: 1px solid #dbeafe;
            border-radius: 14px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _api_base() -> str:
    return os.getenv("WEALTHSENSE_API_URL", "http://127.0.0.1:8000")


def _health_check() -> dict[str, object]:
    return requests.get(f"{_api_base()}/health", timeout=15).json()


def _forecast(ticker: str, horizon_days: int) -> dict[str, object]:
    resp = requests.post(
        f"{_api_base()}/forecast",
        json={"ticker": ticker, "horizon_days": horizon_days},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _goal_plan(payload: dict[str, float | int]) -> dict[str, float]:
    resp = requests.post(f"{_api_base()}/goal-plan", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _login(email: str, name: str) -> str:
    resp = requests.post(f"{_api_base()}/auth/login", json={"email": email, "name": name}, timeout=20)
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _save_profile(token: str, payload: dict[str, object]) -> None:
    resp = requests.post(f"{_api_base()}/user/profile", json=payload, headers=_auth_headers(token), timeout=20)
    resp.raise_for_status()


def _save_portfolio(token: str, payload: dict[str, object]) -> None:
    resp = requests.post(f"{_api_base()}/portfolio", json=payload, headers=_auth_headers(token), timeout=20)
    resp.raise_for_status()


def _dashboard(token: str) -> dict[str, object]:
    resp = requests.get(f"{_api_base()}/dashboard", headers=_auth_headers(token), timeout=20)
    resp.raise_for_status()
    return resp.json()


def _digest_preview(token: str) -> dict[str, str]:
    resp = requests.post(f"{_api_base()}/digest/preview", headers=_auth_headers(token), timeout=20)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    st.set_page_config(page_title="WealthSense AI", layout="wide", initial_sidebar_state="expanded")
    _apply_custom_theme()
    st.title("WealthSense AI")
    st.caption("Now powered by FastAPI backend, live market data, and persisted results")

    st.sidebar.header("Backend")
    st.sidebar.code(_api_base())
    try:
        h = _health_check()
        st.sidebar.success(f"API healthy ({h['backend_mode']})")
    except Exception as exc:
        st.sidebar.error(f"API unavailable: {exc}")
        st.stop()

    st.sidebar.header("Account")
    email = st.sidebar.text_input("Email", value="demo@wealthsense.ai")
    name = st.sidebar.text_input("Name", value="Demo User")
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = ""
    if st.sidebar.button("Login"):
        st.session_state.auth_token = _login(email=email, name=name)
        st.sidebar.success("Signed in")

    if "onboard_complete" not in st.session_state:
        st.session_state.onboard_complete = False
    if "onboard_goal" not in st.session_state:
        st.session_state.onboard_goal = "Grow my wealth"
    if "onboard_risk" not in st.session_state:
        st.session_state.onboard_risk = 3
    if "onboard_asset" not in st.session_state:
        st.session_state.onboard_asset = "SPY"

    tab_onboarding, tab_dashboard, tab_forecast, tab_goal = st.tabs(["Onboarding", "Dashboard", "Forecast", "Goal Planner"])

    with tab_onboarding:
        st.subheader("3-minute setup")
        goal_choices = ["Retire early", "Buy a home", "Build a safety net", "Grow my wealth"]
        custom_goal = st.text_input("Step 1: What are you working toward? (optional custom goal)")
        selected_goal = st.radio("Or pick one:", goal_choices, index=3)
        risk = st.slider(
            "Step 2: How do you feel about risk?",
            min_value=1,
            max_value=5,
            value=st.session_state.onboard_risk,
            help="1 = safety first, 5 = comfortable with larger ups and downs",
        )
        risk_text = {
            1: "I want steadier outcomes, even if growth is slower.",
            2: "I prefer low swings and can accept moderate growth.",
            3: "I want a balance between growth and stability.",
            4: "I can accept bumps for stronger long-term growth.",
            5: "I can tolerate high volatility for maximum upside potential.",
        }[risk]
        st.caption(risk_text)
        asset_cards = ["SPY", "QQQ", "VOO", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META"]
        preferred_asset = st.selectbox("Step 3: Pick your first asset to watch", asset_cards, index=0)
        if st.button("Complete onboarding and build my dashboard"):
            st.session_state.onboard_goal = custom_goal.strip() or selected_goal
            st.session_state.onboard_risk = risk
            st.session_state.onboard_asset = preferred_asset
            st.session_state.onboard_complete = True
            if st.session_state.auth_token:
                _save_profile(
                    st.session_state.auth_token,
                    {
                        "name": name,
                        "email": email,
                        "risk_tolerance": {1: "conservative", 2: "conservative", 3: "balanced", 4: "aggressive", 5: "aggressive"}[risk],
                        "goals": [
                            {
                                "goal_name": st.session_state.onboard_goal,
                                "target_amount": 100000,
                                "target_date": "2030-01-01",
                            }
                        ],
                    },
                )
            st.success("Onboarding complete. Your personalized dashboard is ready.")

    with tab_dashboard:
        st.subheader("Your Dashboard")
        if not st.session_state.auth_token:
            st.info("Login from the sidebar to save profile, portfolio, and view your dashboard.")
        else:
            risk = st.selectbox("Risk tolerance", ["conservative", "balanced", "aggressive"], index=1)
            if st.button("Save profile"):
                _save_profile(
                    st.session_state.auth_token,
                    {
                        "name": name,
                        "email": email,
                        "risk_tolerance": risk,
                        "goals": [{"goal_name": "Retire early", "target_amount": 700000, "target_date": "2040-12-31"}],
                    },
                )
                st.success("Profile saved")
            if st.button("Save starter portfolio"):
                _save_portfolio(
                    st.session_state.auth_token,
                    {
                        "name": "Starter Mix",
                        "assets": [{"ticker": "SPY", "allocation": 0.5}, {"ticker": "QQQ", "allocation": 0.3}, {"ticker": "VOO", "allocation": 0.2}],
                    },
                )
                st.success("Portfolio saved")
            dash = _dashboard(st.session_state.auth_token)
            st.metric("Plan success probability", f"{float(dash.get('success_probability', 0.0)) * 100:.1f}%")
            st.write(f"Insight: {dash.get('insight', 'No insight yet')}")
            if st.button("Send weekly digest preview"):
                digest = _digest_preview(st.session_state.auth_token)
                st.success(f"Digest {digest.get('status')} to {digest.get('recipient')}")
            if st.session_state.onboard_complete:
                first = _forecast(ticker=st.session_state.onboard_asset, horizon_days=30)
                st.write(
                    f"Personalized first look: Based on your '{st.session_state.onboard_goal}' goal and "
                    f"risk level {st.session_state.onboard_risk}/5, we are watching {st.session_state.onboard_asset} first."
                )
                fdf = pd.DataFrame(first["forecast"])
                st.line_chart(fdf.set_index("date")["predicted"])

    with tab_forecast:
        st.subheader("Live Forecast")
        ticker = st.selectbox("Asset", ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ", "VOO", "AMZN", "GOOGL", "META"])
        horizon = st.slider("Forecast horizon (days)", min_value=7, max_value=365, value=30)
        if st.button("Run live forecast", use_container_width=True):
            result = _forecast(ticker=ticker, horizon_days=horizon)
            st.metric("Latest Price", f"${result['latest_price']:.2f}")
            st.write(f"Macro context: {result['macro']}")
            df = pd.DataFrame(result["forecast"])
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["date"], y=df["predicted"], mode="lines", name="Median forecast"))
            fig.add_trace(go.Scatter(x=df["date"], y=df["pred_upper"], mode="lines", line=dict(width=0), showlegend=False))
            fig.add_trace(
                go.Scatter(
                    x=df["date"],
                    y=df["pred_lower"],
                    mode="lines",
                    fill="tonexty",
                    fillcolor="rgba(99,110,250,0.2)",
                    line=dict(width=0),
                    name="P10-P90 interval",
                )
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True)

    with tab_goal:
        st.subheader("Goal Planner")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            current_balance = st.number_input("Current savings ($)", min_value=0.0, value=25000.0, step=500.0)
        with c2:
            monthly_contribution = st.number_input("Monthly contribution ($)", min_value=0.0, value=1200.0, step=50.0)
        with c3:
            target_amount = st.number_input("Target ($)", min_value=1000.0, value=120000.0, step=1000.0)
        with c4:
            years = st.number_input("Years", min_value=0.5, value=5.0, step=0.5)
        annual_return_mean = st.slider("Expected annual return", min_value=-0.2, max_value=0.4, value=0.08, step=0.01)
        annual_volatility = st.slider("Annual volatility", min_value=0.05, max_value=0.8, value=0.16, step=0.01)
        simulations = st.slider("Simulations", min_value=500, max_value=20000, value=5000, step=500)
        if st.button("Run goal plan", use_container_width=True):
            result = _goal_plan(
                {
                    "current_balance": current_balance,
                    "monthly_contribution": monthly_contribution,
                    "target_amount": target_amount,
                    "years": years,
                    "annual_return_mean": annual_return_mean,
                    "annual_volatility": annual_volatility,
                    "simulations": simulations,
                }
            )
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("Success Probability", f"{result['success_probability'] * 100:.1f}%")
            g2.metric("Expected Terminal Value", f"${result['expected_terminal_value']:,.0f}")
            g3.metric("Median Shortfall", f"${result['median_shortfall']:,.0f}")
            g4.metric("Recommended Contribution", f"${result['recommended_monthly_contribution']:,.0f}")


if __name__ == "__main__":
    main()
