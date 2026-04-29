# WealthSense AI

WealthSense AI is a personal finance forecasting product with:

- live market and macro-aware forecasts
- Monte Carlo goal planning
- AI coach chat
- tiered billing
- FastAPI backend + Next.js frontend
- ongoing ML pipeline upgrades (Step 9 in progress)

## Current Product State

Implemented through Step 8 and actively building Step 9.

### Backend (`backend/`)

- FastAPI API with health, forecasting, goal planning, auth/profile/portfolio, coach, billing, and operations endpoints
- SQLite fallback persistence with Supabase-ready integration
- Structured request logging (`loguru`) for endpoint/user/latency/model version
- Drift status endpoint: `GET /ops/drift`
- GDPR basics:
  - `GET /account/export`
  - `DELETE /account/delete`
- Weekly retraining workflow in GitHub Actions (`.github/workflows/retrain.yml`)
- Sentry wiring (safe no-op until DSN is provided)

### Frontend (`frontend/`)

- Next.js + TypeScript + Tailwind app
- Product routes:
  - `/`
  - `/onboarding`
  - `/dashboard`
  - `/forecast`
  - `/goals`
  - `/strategy`
  - `/settings`
- Dashboard AI coach integration with streaming responses
- Sentry client init hook (safe no-op until `NEXT_PUBLIC_SENTRY_DSN` is set)

### ML Pipeline (`src/wealthsense_ai/`)

- Targets **log returns** with reconstructed price outputs for display
- Models: `lstm`, `gru`, `transformer`, plus a `tft` model path (TFT-compatible regressor scaffold)
- Training safeguards:
  - gradient clipping
  - ReduceLROnPlateau scheduler
  - early stopping
- Uncertainty:
  - MC dropout intervals
  - VIX regime widening
  - split-conformal correction
- Ensemble:
  - Ridge stacking meta-model
  - rolling residual spread for interval radius
- Regime detection:
  - Gaussian HMM when available (`hmmlearn`)
  - fallback rules when unavailable

## Step 9 Progress Snapshot

In progress and partially implemented:

- Task 9.1: enriched features (`DXY`, `FedFunds`, `CPI_MoM`, `Sentiment_5D`, `Earnings_Next5D`, `Corr_SPY_20`) and local feature-store artifacts
- Task 9.2: conformal interval calibration
- Task 9.3: stacking ensemble
- Task 9.4: regime detection module
- Task 9.5: TFT model path scaffold
- Task 9.6: constrained allocation suggestion endpoint (`POST /allocation/suggest`)

Still pending for full Step 9 completion:

- full FinBERT headline ingestion pipeline
- full cross-asset correlation matrix feature block
- PostgreSQL feature-store sync
- full `pytorch-forecasting` TFT training pipeline
- Stable Baselines3 PPO allocator training

## Local Run

### 1) Install dependencies

```bash
/usr/bin/python3 -m pip install --user -r requirements.txt
```

```bash
cd frontend
npm install
cd ..
```

### 2) Run backend

```bash
PYTHONPATH=src /usr/bin/python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### 3) Run frontend

```bash
cd frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

### 4) (Optional) Run Streamlit app

```bash
PYTHONPATH=src python3 -m streamlit run src/wealthsense_ai/app.py --server.headless true --server.address 127.0.0.1 --server.port 8522
```

## Environment Variables

See `.env.example`. Common optional keys:

- `ANTHROPIC_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `STRIPE_SECRET_KEY`
- `SENTRY_DSN`
- `NEXT_PUBLIC_SENTRY_DSN`
- `MODEL_VERSION`
- `DRIFT_BASELINE_MAE`
- `DRIFT_THRESHOLD_MULTIPLIER`

## Key Artifacts

- `artifacts/metrics.json`
- `artifacts/forecasts.csv`
- `artifacts/strategy_results.csv`
- `artifacts/models/*.pt`
- `artifacts/feature_store/*.csv`

## Testing

```bash
PYTHONPATH=src /usr/bin/python3 -m pytest tests/test_backend_api.py
```

## Notes

- Do not manually edit generated files in `artifacts/`; regenerate by running training.
- Current branch may include local model/cache artifacts not intended for commit.
