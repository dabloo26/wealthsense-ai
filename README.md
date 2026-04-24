# WealthSense AI

Working end-to-end implementation of the proposal with a beginner-first UX: deep-learning forecasting + goal planning + portfolio insights + startup-oriented dashboard experience.

## What Was Built

- **Data layer**
  - Pulls Yahoo Finance daily OHLCV data for `AAPL`, `MSFT`, `NVDA`, `TSLA`, `SPY`
  - Uses fixed range `2015-01-01` to `2023-12-31`
  - Caches data to `artifacts/data_cache/` for reproducible demos
- **Feature engineering**
  - `SMA_10`, `SMA_30`, `EMA_12`, `RSI_14`, `Daily_Return`, `Volatility_10`
  - 30-day rolling sequence windows for supervised forecasting
  - Split policy:
    - Train: `2015-2021`
    - Validation: `2022`
    - Test: `2023`
- **Modeling**
  - PyTorch implementations of:
    - `LSTM` (2-layer)
    - `GRU` (2-layer)
    - Encoder-only `Transformer` with positional encoding
  - Early stopping + AdamW optimizer
- **Evaluation**
  - `MAE`, `RMSE`, `MAPE`, directional accuracy
  - Conformal 90% prediction intervals + interval coverage
  - Inverse-RMSE weighted **ensemble** model
- **Portfolio strategy simulation**
  - Model-signal strategy performance
  - Buy-and-hold baseline
  - Metrics: cumulative return, Sharpe, max drawdown
- **Goal-based planning**
  - Monte Carlo engine for goal success probability
  - Expected terminal value + suggested monthly contribution
- **Website (Streamlit app)**
  - Beginner-friendly `Start Here` onboarding flow
  - Simplified `Your Portfolio` and `Market Insights` views
  - Goal Planner with plain-language success guidance
  - Scenario Studio and advanced controls hidden behind simpler defaults
  - Startup-friendly `Ops & Downloads` module for demos and reporting

## Current Folder Map

- `src/wealthsense_ai/data.py` - download, normalize, feature engineering, sequence creation
- `src/wealthsense_ai/models.py` - LSTM/GRU/Transformer model classes
- `src/wealthsense_ai/train.py` - full train/evaluate pipeline, artifact generation
- `src/wealthsense_ai/strategy.py` - trading + benchmark metrics
- `src/wealthsense_ai/simulation.py` - Monte Carlo goal engine
- `src/wealthsense_ai/uncertainty.py` - conformal interval utilities
- `src/wealthsense_ai/app.py` - Streamlit website/dashboard
- `artifacts/` - generated trained outputs for demo
- `run_all.sh` - one command to install, train, and launch

## One-Command Run (Recommended)

From repo root:

```bash
cd wealthsense-ai
./run_all.sh
```

This script:
1. Installs dependencies
2. Trains all models
3. Generates all artifacts
4. Launches Streamlit website

## Manual Commands

From repo root:

```bash
npm run wealthsense:train
npm run wealthsense:dashboard
```

## Artifacts Produced

- `artifacts/metrics.json` - config + per-model metrics
- `artifacts/forecasts.csv` - predicted vs actual values + intervals
- `artifacts/strategy_results.csv` - strategy and buy-and-hold results
- `artifacts/models/*.pt` - trained PyTorch model weights
- `artifacts/data_cache/*.csv` - cached Yahoo Finance data

## Optional AI Chat Setup

```bash
export ANTHROPIC_API_KEY=your_key_here
```

If no key is set, the dashboard still works and shows all non-LLM features.

## Handoff Notes For New Team Members

- Start at `src/wealthsense_ai/train.py` to understand the end-to-end training flow.
- Use `src/wealthsense_ai/config.py` to adjust tickers, model sizes, epochs, and paths.
- Do not edit files in `artifacts/` manually; regenerate by rerunning training.
- For project demos, use cached data in `artifacts/data_cache` to avoid live API risk.

## What’s Next (If You Want To Improve It Further)

- Add macroeconomic exogenous features (rates, CPI, VIX, earnings events).
- Add walk-forward validation for stricter time-series rigor.
- Add drift detection and scheduled retraining jobs.
