from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

try:
    from .config import PathsConfig
    from .simulation import run_goal_monte_carlo
    from .strategy import summarize_forecasts
except ImportError:
    # Support direct script execution via `streamlit run .../app.py`.
    from wealthsense_ai.config import PathsConfig
    from wealthsense_ai.simulation import run_goal_monte_carlo
    from wealthsense_ai.strategy import summarize_forecasts

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


def _load_artifacts(paths: PathsConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if not paths.forecasts_file.exists() or not paths.metrics_file.exists():
        raise FileNotFoundError("Missing training artifacts. Run python -m wealthsense_ai.train first.")

    forecasts = pd.read_csv(paths.forecasts_file, parse_dates=["date"])
    strategy = (
        pd.read_csv(paths.strategy_file)
        if paths.strategy_file.exists()
        else pd.DataFrame(columns=["ticker", "model", "cumulative_return", "sharpe_ratio", "max_drawdown"])
    )
    with paths.metrics_file.open("r", encoding="utf-8") as f:
        metrics = json.load(f)
    return forecasts, strategy, metrics


def _render_chat_summary(prompt: str, context: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "Set `ANTHROPIC_API_KEY` to enable AI explanations."
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-3-7-sonnet-latest",
            max_tokens=250,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are a financial assistant. Explain clearly with risk caveats.\n"
                        f"Dashboard context:\n{context}\n\nQuestion:\n{prompt}"
                    ),
                }
            ],
        )
        return resp.content[0].text if resp.content else "No response returned."
    except Exception as exc:
        return f"AI explanation unavailable: {exc}"


def _build_portfolio_series(forecasts: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    ens = forecasts[forecasts["model"] == "ensemble"].copy()
    ens = ens[ens["ticker"].isin(list(weights.keys()))]
    pivot = ens.pivot_table(index="date", columns="ticker", values="actual", aggfunc="mean").dropna()
    returns = pivot.pct_change().dropna()

    # Normalize in case the sliders do not sum to exactly 1.0.
    w = np.array([weights[t] for t in returns.columns], dtype=float)
    w = w / max(w.sum(), 1e-8)
    portfolio_returns = returns.values @ w
    out = pd.DataFrame({"date": returns.index, "portfolio_return": portfolio_returns})
    out["cumulative"] = (1.0 + out["portfolio_return"]).cumprod() - 1.0
    return out


def _rolling_var(returns: pd.Series, window: int = 20, alpha: float = 0.05) -> pd.Series:
    return returns.rolling(window).quantile(alpha)


def _portfolio_paths_mc(
    start_value: float,
    annual_mu: float,
    annual_sigma: float,
    horizon_years: int,
    paths: int,
) -> pd.DataFrame:
    steps = max(1, horizon_years * 12)
    mu_m = (1.0 + annual_mu) ** (1.0 / 12.0) - 1.0
    sigma_m = annual_sigma / np.sqrt(12.0)
    shocks = np.random.normal(mu_m, sigma_m, size=(paths, steps))
    growth = np.cumprod(1.0 + shocks, axis=1)
    values = start_value * growth
    out = pd.DataFrame(values.T)
    out["month"] = np.arange(1, steps + 1)
    return out


def _risk_profile_defaults(risk_profile: str) -> tuple[float, float]:
    table = {
        "Conservative": (0.055, 0.10),
        "Balanced": (0.08, 0.16),
        "Growth": (0.11, 0.24),
    }
    return table[risk_profile]


def _goal_templates() -> dict[str, tuple[float, float]]:
    return {
        "Emergency Fund": (15000.0, 1.5),
        "Home Down Payment": (75000.0, 4.0),
        "Retirement Booster": (500000.0, 15.0),
        "Child Education": (120000.0, 10.0),
    }


def _portfolio_metrics(returns: pd.Series) -> dict[str, float]:
    if returns.empty:
        return {"cumulative": 0.0, "annualized_vol": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    cumulative = float((1.0 + returns).prod() - 1.0)
    annualized_vol = float(returns.std() * np.sqrt(252.0))
    excess = returns - (0.02 / 252.0)
    sharpe = 0.0 if excess.std() == 0.0 else float(np.sqrt(252.0) * excess.mean() / excess.std())
    equity = (1.0 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return {
        "cumulative": cumulative,
        "annualized_vol": annualized_vol,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
    }


def main() -> None:
    st.set_page_config(page_title="WealthSense AI", layout="wide", initial_sidebar_state="expanded")
    _apply_custom_theme()
    st.title("WealthSense AI")
    st.caption("A beginner-friendly AI financial copilot for savings, investing, and goals")

    paths = PathsConfig()
    paths.ensure()

    try:
        forecasts, strategy, metrics = _load_artifacts(paths)
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

    all_tickers = sorted(forecasts["ticker"].unique())
    model_leaderboard = summarize_forecasts(forecasts)
    top_model_global = model_leaderboard.groupby("model", as_index=False)["mape"].mean().sort_values("mape").iloc[0]

    st.sidebar.header("Your Profile")
    beginner_mode = st.sidebar.toggle("Beginner mode", value=True)
    selected = st.sidebar.multiselect("Investments you care about", options=all_tickers, default=all_tickers[:4])
    if not selected:
        st.sidebar.warning("Pick at least one ticker.")
        selected = all_tickers[:1]
    risk_profile = st.sidebar.selectbox("Risk comfort", ["Conservative", "Balanced", "Growth"], index=1)
    annual_mu_default, annual_sigma_default = _risk_profile_defaults(risk_profile)
    risk_free_rate = st.sidebar.slider("Savings account / risk-free rate (%)", min_value=0.0, max_value=8.0, value=2.0, step=0.25) / 100.0

    if beginner_mode:
        confidence_level = 90
        sim_paths = 1000
    else:
        confidence_level = st.sidebar.slider("Prediction confidence (%)", 80, 99, 90, 1)
        sim_paths = st.sidebar.slider("Simulation depth", min_value=200, max_value=5000, value=1200, step=200)

    st.sidebar.markdown("### Portfolio mix")
    weight_cols = st.sidebar.columns(1 if beginner_mode else 2)
    weights: dict[str, float] = {}
    for idx, ticker in enumerate(selected):
        with weight_cols[idx % len(weight_cols)]:
            weights[ticker] = st.slider(
                f"{ticker}",
                min_value=0.0,
                max_value=1.0,
                value=1.0 / len(selected),
                step=0.10 if beginner_mode else 0.05,
                key=f"w_{ticker}",
            )

    series = _build_portfolio_series(forecasts=forecasts, weights=weights)
    pm = _portfolio_metrics(series["portfolio_return"])

    st.markdown('<div class="ws-card">', unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Portfolio Return", f"{pm['cumulative'] * 100:.2f}%")
    k2.metric("Volatility", f"{pm['annualized_vol'] * 100:.2f}%")
    k3.metric("Sharpe", f"{pm['sharpe']:.2f}")
    k4.metric("Max Drawdown", f"{pm['max_drawdown'] * 100:.2f}%")
    k5.metric("Best Model", f"{top_model_global['model']} ({top_model_global['mape'] * 100:.2f}% MAPE)")
    st.markdown("</div>", unsafe_allow_html=True)

    tab_start, tab_portfolio, tab_forecast, tab_goal, tab_chat, tab_scenarios, tab_ops = st.tabs(
        [
            "Start Here",
            "Your Portfolio",
            "Market Insights",
            "Goal Planner",
            "AI Copilot",
            "Scenario Studio",
            "Ops & Downloads",
        ]
    )

    with tab_start:
        st.subheader("Start in 60 seconds")
        c1, c2, c3 = st.columns(3)
        with c1:
            monthly_income = st.number_input("Monthly income ($)", min_value=0.0, value=6000.0, step=100.0)
        with c2:
            monthly_expenses = st.number_input("Monthly expenses ($)", min_value=0.0, value=4200.0, step=100.0)
        with c3:
            current_savings = st.number_input("Current savings ($)", min_value=0.0, value=20000.0, step=500.0)

        template = st.selectbox("Pick your main goal", list(_goal_templates().keys()))
        default_goal, default_years = _goal_templates()[template]
        monthly_surplus = max(0.0, monthly_income - monthly_expenses)
        runway_months = 0.0 if monthly_expenses == 0 else current_savings / max(monthly_expenses, 1.0)

        g1, g2, g3 = st.columns(3)
        g1.metric("Monthly surplus", f"${monthly_surplus:,.0f}")
        g2.metric("Emergency runway", f"{runway_months:.1f} months")
        g3.metric("Suggested starter goal", template)

        if monthly_surplus < 300:
            st.warning("Your current monthly surplus is low. Focus on expenses first, then investing.")
        else:
            st.success("You have investable surplus. You're in a good position to start this plan.")

    with tab_portfolio:
        st.subheader("Your Portfolio")
        wdf = pd.DataFrame({"ticker": list(weights.keys()), "weight_raw": list(weights.values())})
        wdf["weight"] = wdf["weight_raw"] / max(wdf["weight_raw"].sum(), 1e-8)

        sector_map = {
            "AAPL": "Technology",
            "MSFT": "Technology",
            "NVDA": "Technology",
            "TSLA": "Automotive",
            "SPY": "Diversified ETF",
        }
        sector_df = wdf.assign(sector=lambda d: d["ticker"].map(sector_map).fillna("Other")).groupby("sector", as_index=False)["weight"].sum()

        c1, c2 = st.columns(2)
        with c1:
            pie = px.pie(wdf, names="ticker", values="weight", hole=0.45, title="Dynamic Asset Allocation")
            st.plotly_chart(pie, use_container_width=True)
        with c2:
            sfig = px.bar(sector_df, x="sector", y="weight", color="sector", title="Sector Exposure")
            st.plotly_chart(sfig, use_container_width=True)

        line = px.line(series, x="date", y="cumulative", title="Portfolio Cumulative Curve")
        line.add_hline(y=0, line_dash="dot", line_color="gray")
        st.plotly_chart(line, use_container_width=True)

        returns = series["portfolio_return"]
        var_series = _rolling_var(returns, window=20, alpha=1.0 - (confidence_level / 100.0))
        risk_df = pd.DataFrame({"date": series["date"], "return": returns.values, "rolling_var": var_series.values})
        rfig = go.Figure()
        rfig.add_trace(go.Scatter(x=risk_df["date"], y=risk_df["return"], mode="lines", name="Daily return"))
        rfig.add_trace(go.Scatter(x=risk_df["date"], y=risk_df["rolling_var"], mode="lines", name=f"Rolling VaR ({confidence_level}%)"))
        rfig.update_layout(title="Risk Monitor: Return vs Rolling VaR")
        st.plotly_chart(rfig, use_container_width=True)

        with st.expander("Advanced details"):
            st.write("These numbers are based on ensemble-return simulation from historical test windows.")
            st.dataframe(wdf, use_container_width=True)

    with tab_forecast:
        st.subheader("Market Insights")
        ticker = st.selectbox("Ticker", all_tickers, key="forecast_ticker")
        subset = forecasts[forecasts["ticker"] == ticker].copy()
        best_model_row = summarize_forecasts(subset).iloc[0]
        best_model = str(best_model_row["model"])
        best_subset = subset[subset["model"] == best_model].sort_values("date")

        c1, c2 = st.columns(2)
        with c1:
            plot_df = subset.melt(
                id_vars=["date", "model"],
                value_vars=["actual", "predicted"],
                var_name="series",
                value_name="price",
            )
            fig = px.line(
                plot_df,
                x="date",
                y="price",
                color="model",
                line_dash="series",
                title=f"Forecasts vs Actual ({ticker})",
            )
            st.plotly_chart(fig, use_container_width=True)
            if {"pred_lower", "pred_upper"}.issubset(best_subset.columns):
                band_fig = go.Figure()
                band_fig.add_trace(go.Scatter(x=best_subset["date"], y=best_subset["actual"], mode="lines", name="Actual"))
                band_fig.add_trace(go.Scatter(x=best_subset["date"], y=best_subset["pred_upper"], mode="lines", line=dict(width=0), showlegend=False))
                band_fig.add_trace(
                    go.Scatter(
                        x=best_subset["date"],
                        y=best_subset["pred_lower"],
                        mode="lines",
                        fill="tonexty",
                        fillcolor="rgba(99, 110, 250, 0.2)",
                        line=dict(width=0),
                        name=f"{best_model} 90% interval",
                    )
                )
                band_fig.add_trace(
                    go.Scatter(x=best_subset["date"], y=best_subset["predicted"], mode="lines", name=f"{best_model} prediction")
                )
                band_fig.update_layout(title=f"Best Model with Confidence Band ({best_model})")
                st.plotly_chart(band_fig, use_container_width=True)
        with c2:
            summary_table = summarize_forecasts(subset)
            top_mape = float(summary_table.iloc[0]["mape"] * 100)
            if top_mape < 5:
                st.success(f"High forecast confidence for {ticker} (MAPE {top_mape:.2f}%).")
            elif top_mape < 10:
                st.info(f"Moderate forecast confidence for {ticker} (MAPE {top_mape:.2f}%).")
            else:
                st.warning(f"Low forecast confidence for {ticker} (MAPE {top_mape:.2f}%).")

            st.subheader("What worked best")
            strat_table = strategy[strategy["ticker"] == ticker].sort_values("sharpe_ratio", ascending=False)
            st.dataframe(strat_table, use_container_width=True)

            best = summary_table.iloc[0]
            st.metric("Forecast error (MAPE)", f"{best['mape'] * 100:.2f}%")
            st.metric("Direction accuracy", f"{best['directional_accuracy'] * 100:.2f}%")

            with st.expander("Compare all models (advanced)"):
                st.dataframe(summary_table, use_container_width=True)

    with tab_goal:
        st.subheader("Goal Planner")
        g1, g2, g3, g4, g5, g6 = st.columns(6)
        with g1:
            current_balance = st.number_input("Current savings ($)", min_value=0.0, value=current_savings if 'current_savings' in locals() else 20000.0, step=500.0)
        with g2:
            monthly_contribution = st.number_input("Monthly contribution ($)", min_value=0.0, value=monthly_surplus if 'monthly_surplus' in locals() else 1200.0, step=50.0)
        with g3:
            target_amount = st.number_input("Goal target ($)", min_value=1000.0, value=default_goal if 'default_goal' in locals() else 60000.0, step=1000.0)
        with g4:
            years = st.number_input("Timeline (years)", min_value=0.5, value=default_years if 'default_years' in locals() else 3.0, step=0.5)
        with g5:
            annual_mu = st.number_input("Expected annual return", min_value=-0.2, max_value=0.4, value=annual_mu_default, step=0.01)
        with g6:
            annual_sigma = st.number_input("Annual volatility", min_value=0.05, max_value=0.8, value=annual_sigma_default, step=0.01)

        result = run_goal_monte_carlo(
            current_balance=current_balance,
            monthly_contribution=monthly_contribution,
            target_amount=target_amount,
            years=years,
            annual_return_mean=annual_mu,
            annual_volatility=annual_sigma,
            num_sims=sim_paths,
        )
        gm1, gm2, gm3, gm4 = st.columns(4)
        gm1.metric("Goal Success Probability", f"{result['success_probability'] * 100:.1f}%")
        gm2.metric("Expected Terminal Value", f"${result['expected_terminal_value']:,.0f}")
        gm3.metric("Median Shortfall", f"${result['median_shortfall']:,.0f}")
        gm4.metric("Suggested Monthly Contribution", f"${result['recommended_monthly_contribution']:,.0f}")

        stress_df = pd.DataFrame(
            [
                {
                    "scenario": "Bear",
                    **run_goal_monte_carlo(
                        current_balance=current_balance,
                        monthly_contribution=monthly_contribution,
                        target_amount=target_amount,
                        years=years,
                        annual_return_mean=annual_mu - 0.04,
                        annual_volatility=min(0.9, annual_sigma + 0.08),
                        num_sims=3000,
                    ),
                },
                {
                    "scenario": "Base",
                    **run_goal_monte_carlo(
                        current_balance=current_balance,
                        monthly_contribution=monthly_contribution,
                        target_amount=target_amount,
                        years=years,
                        annual_return_mean=annual_mu,
                        annual_volatility=annual_sigma,
                        num_sims=3000,
                    ),
                },
                {
                    "scenario": "Bull",
                    **run_goal_monte_carlo(
                        current_balance=current_balance,
                        monthly_contribution=monthly_contribution,
                        target_amount=target_amount,
                        years=years,
                        annual_return_mean=annual_mu + 0.04,
                        annual_volatility=max(0.05, annual_sigma - 0.05),
                        num_sims=3000,
                    ),
                },
            ]
        )
        stress_plot = px.bar(
            stress_df,
            x="scenario",
            y="success_probability",
            color="scenario",
            title="Goal Probability by Market Regime",
        )
        st.plotly_chart(stress_plot, use_container_width=True)
        st.dataframe(
            stress_df.assign(
                success_probability=lambda d: (d["success_probability"] * 100).round(2),
                expected_terminal_value=lambda d: d["expected_terminal_value"].round(0),
                median_shortfall=lambda d: d["median_shortfall"].round(0),
                recommended_monthly_contribution=lambda d: d["recommended_monthly_contribution"].round(0),
            ),
            use_container_width=True,
        )

    with tab_chat:
        st.subheader("AI Copilot")
        st.write("Ask plain-English questions about your money plan.")
        question = st.text_input("Ask about your plan", value="I want to buy a home in 3 years. Am I on track?")
        if st.button("Generate explanation"):
            leaderboard = summarize_forecasts(forecasts)
            context = (
                f"model_metrics={leaderboard.to_dict(orient='records')}; "
                f"training_device={metrics.get('device')}; "
                f"supported_tickers={all_tickers}; "
                f"portfolio_metrics={pm}; "
                f"risk_free_rate={risk_free_rate}; "
                f"confidence={confidence_level}"
            )
            st.write(_render_chat_summary(prompt=question, context=context))

    with tab_scenarios:
        st.subheader("Scenario Studio")
        start_value = st.number_input("Start Portfolio Value ($)", min_value=1000.0, value=50000.0, step=1000.0)
        horizon = st.slider("Horizon (years)", min_value=1, max_value=15, value=5)
        scen = _portfolio_paths_mc(
            start_value=start_value,
            annual_mu=0.08,
            annual_sigma=max(0.08, pm["annualized_vol"]),
            horizon_years=horizon,
            paths=min(sim_paths, 3000),
        )
        quantiles = scen.drop(columns=["month"]).quantile([0.1, 0.5, 0.9], axis=1).T
        quantiles["month"] = scen["month"]
        qfig = go.Figure()
        qfig.add_trace(go.Scatter(x=quantiles["month"], y=quantiles[0.5], mode="lines", name="Median"))
        qfig.add_trace(go.Scatter(x=quantiles["month"], y=quantiles[0.9], mode="lines", name="P90", line=dict(dash="dot")))
        qfig.add_trace(go.Scatter(x=quantiles["month"], y=quantiles[0.1], mode="lines", name="P10", line=dict(dash="dot")))
        qfig.update_layout(title="Forward Distribution of Portfolio Value")
        st.plotly_chart(qfig, use_container_width=True)

    with tab_ops:
        st.subheader("Startup Ops & Exports")
        st.code(
            "Training command:\n"
            "PYTHONPATH=wealthsense-ai/src python3 -m wealthsense_ai.train\n\n"
            "App command:\n"
            "PYTHONPATH=wealthsense-ai/src python3 -m streamlit run wealthsense-ai/src/wealthsense_ai/app.py",
            language="bash",
        )
        st.write("Download artifacts for reporting, portfolio projects, and peer review.")
        st.download_button(
            label="Download Forecasts CSV",
            data=forecasts.to_csv(index=False).encode("utf-8"),
            file_name="wealthsense_forecasts.csv",
            mime="text/csv",
        )
        st.download_button(
            label="Download Strategy CSV",
            data=strategy.to_csv(index=False).encode("utf-8"),
            file_name="wealthsense_strategy.csv",
            mime="text/csv",
        )
        st.download_button(
            label="Download Metrics JSON",
            data=json.dumps(metrics, indent=2).encode("utf-8"),
            file_name="wealthsense_metrics.json",
            mime="application/json",
        )
        st.dataframe(model_leaderboard, use_container_width=True)
        st.info(
            "Important: WealthSense is educational and planning-oriented, not personalized financial advice. "
            "For production startup use, add onboarding KYC, advisor review, and compliance checks."
        )


if __name__ == "__main__":
    main()
