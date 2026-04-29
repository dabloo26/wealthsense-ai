# WealthSense Build Status

## Current step
9

## Step 1 status
done

## Completed steps
- Step 1: Added FastAPI backend with live yfinance + FRED macro inputs, API-driven Streamlit flows, and persisted forecast/goal results using Supabase-ready storage with sqlite fallback.
- Step 2: Added mock-compatible auth flow, user profiles/goals, portfolio saves, dashboard summary endpoint, and weekly digest preview with persistence.
- Step 3: Added a 3-step onboarding wizard, persisted onboarding answers into user profile, and rendered a personalized first forecast on dashboard completion.
- Step 4: Replaced prototype UI with a Next.js product interface across landing, onboarding, dashboard, forecast detail, goals, strategy, and settings using a teacher-friendly default language and collapsible advanced sections.
- Step 5: Added an AI coach with streaming responses, personalized context injection, daily free-tier message caps, and audit logging of chat interactions.
- Step 6: Added a trust layer with forecast-detail API output, walk-forward backtest diagnostics, explicit likely-range/disclaimer presentation, and advanced technical breakdown sections.
- Step 7: Added subscription-tier enforcement in backend routes, billing trial/checkout/portal/webhook APIs with Stripe-mock fallback, and contextual upgrade surfaces in the frontend.
- Step 8: Added operational hardening with structured request logging, drift-status checks, GDPR export/delete endpoints, Sentry-ready hooks, and weekly retraining automation.

## What is working right now
- FastAPI backend in `backend/` with `/health`, `/forecast`, and `/goal-plan`
- Live price and volatility context via yfinance
- Macro context enrichment via VIX, Fed Funds (FRED), and CPI YoY (FRED)
- Forecast and goal-plan persistence to Supabase (when configured) or sqlite fallback
- Streamlit app calls backend endpoints instead of running forecast logic locally
- `.env.example` and local `.env` are in place for all required keys
- Login endpoint with Clerk/Auth0-ready mock fallback mode
- User profile save/retrieve with risk tolerance and goal list
- Portfolio save and dashboard endpoint with success probability + insight sentence
- Weekly digest preview endpoint (SendGrid mock mode)
- Streamlit onboarding wizard with goal, risk, and first-asset selection
- Onboarding answers persist to profile and drive first personalized dashboard forecast
- Next.js frontend scaffold in `frontend/` with Tailwind and reusable shadcn-style UI primitives
- Product-style routes live: `/`, `/onboarding`, `/dashboard`, `/forecast`, `/goals`, `/strategy`, `/settings`
- Frontend route smoke checks are passing locally on port 3000
- Forecast detail routes are live at `/forecast/:asset` (plain-language top section + advanced collapsed diagnostics)
- Dashboard now includes the three-zone layout with goal snapshot, investment cards, and coach panel with mobile bottom-sheet entry
- Goals and strategy pages now use plain-language scenario/planning experiences with collapsed advanced sections
- Dashboard coach panel now supports live message sending and streaming token-by-token replies.
- Coach backend endpoint `/coach/stream` injects profile, investments, goals, forecasts, and macro context into responses.
- Free users are capped at 10 coach messages/day; caps are enforced server-side and logged.
- `audit_log` persistence now tracks coach messages and related metadata.
- Training now targets log returns instead of raw prices and reconstructs display prices from predicted returns.
- Macro features (`VIX_Zscore`, `Yield_Spread`) are merged into model inputs with live refresh.
- Uncertainty now uses MC dropout with regime-adjusted interval widening by VIX level.
- Data cache now has 24-hour expiry and auto-refreshes stale market files.
- Ensemble now uses dynamic rolling weights and writes per-ticker weights to `metrics.json`.
- Goal planner now applies a capped model-outlook tilt from recent ensemble forecasts and displays it in plain language.
- Forecast detail now loads enriched backend context (driver sentence, walk-forward metrics, model breakdown, and disclaimer payload).
- Billing endpoints now exist for `/billing/start-trial`, `/billing/checkout`, `/billing/portal`, and `/billing/webhook`.
- Free-tier limits are server-enforced (asset count, forecast horizon, coach usage) with upgrade-directed error messaging.
- Settings page now includes plan actions for trial start, checkout, and billing portal access.
- Frontend now includes the `graphify` npm package for assistant-related graph features.
- Backend now logs request-level telemetry (user, endpoint, latency, model version) and emits drift status via `/ops/drift`.
- GDPR basics are live via `/account/export` and `/account/delete`, with audit entries for export/delete requests.
- Forecast saves and goal-plan saves now create audit-log events in addition to coach and billing audit events.
- Sentry configuration is wired for backend (`SENTRY_DSN`) and frontend (`NEXT_PUBLIC_SENTRY_DSN`) with safe no-op defaults.
- Weekly scheduled retraining pipeline is configured in GitHub Actions with a promotion gate on ensemble directional accuracy.
- Step 9.1 has started: training data now includes enriched macro features (`DXY`, `FedFunds`, `CPI_MoM`) in addition to VIX and yield spread.
- Feature engineering now includes `Sentiment_5D` (rolling return-sign proxy), `Earnings_Next5D` flag, and `Corr_SPY_20` cross-asset correlation.
- Enriched per-ticker feature sets are now persisted to `artifacts/feature_store/` as a local feature-store artifact.
- Step 9.2 has started: uncertainty intervals now include split-conformal calibration using validation residuals before serving test intervals.
- Step 9.3 has started: ensemble now uses a Ridge stacking meta-model on validation predictions (with dynamic residual spread still used for interval radius).
- Step 9.4 has started: market regime detection module added (Gaussian HMM when available, rule-based fallback otherwise) and regime output is written to training metrics.
- Step 9.5 has started: training now includes a TFT model path (`tft`) via a TFT-compatible regressor interface integrated into the ensemble pipeline.
- Step 9.6 has started: added constrained allocation suggestion logic (max 40% weight) and a new backend endpoint `/allocation/suggest` with audit logging and disclaimer.

## What is broken or incomplete
- Step 9 is in progress: full FinBERT headline ingestion, full cross-asset correlation matrix block, and PostgreSQL feature-store sync are still pending.
- Step 9.5 currently uses a TFT-compatible fallback regressor rather than full `pytorch-forecasting` Temporal Fusion Transformer training workflow.
- Step 9.6 currently provides a constrained model-driven allocator API, but Stable Baselines3 PPO training is still pending.
- Streamlit code remains in repo during transition, but Next.js is the primary UI path
- Supabase currently running in local sqlite fallback mode until credentials are provided

## Architecture decisions locked in
- Backend-first architecture: Streamlit is now an API client and does not run forecast services directly.
- Persistence abstraction uses Supabase when configured, with local sqlite fallback to avoid credential blocking.
- Macro feature pipeline is normalized as a backend service dependency for all forecast runs.
- UI language defaults to plain-English guidance for beginners; technical diagnostics are intentionally gated behind explicit "Advanced" expanders.
- Coach responses stream over SSE from backend to frontend to avoid spinner-style waiting and improve perceived responsiveness.
- Monetization controls are enforced at API level first, then surfaced in UI contextually when limits are reached.
- Operational guardrails default to local-safe behavior: drift detection, Sentry, and retraining gates run without requiring paid services.

## Do not redo
- Do not move forecasting/data-fetch logic back into Streamlit.
- Do not hardcode service keys; keep environment-driven config only.
- Do not remove `/ops/drift`, `/account/export`, or `/account/delete`; they are baseline operational/compliance endpoints.

## Notes
- System `pip3` is broken on Homebrew Python in this environment; package installs were completed with `/usr/bin/python3 -m pip`.