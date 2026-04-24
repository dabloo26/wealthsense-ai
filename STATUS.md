# WealthSense Build Status

## Current step
6

## Step 1 status
done

## Completed steps
- Step 1: Added FastAPI backend with live yfinance + FRED macro inputs, API-driven Streamlit flows, and persisted forecast/goal results using Supabase-ready storage with sqlite fallback.
- Step 2: Added mock-compatible auth flow, user profiles/goals, portfolio saves, dashboard summary endpoint, and weekly digest preview with persistence.
- Step 3: Added a 3-step onboarding wizard, persisted onboarding answers into user profile, and rendered a personalized first forecast on dashboard completion.
- Step 4: Replaced prototype UI with a Next.js product interface across landing, onboarding, dashboard, forecast detail, goals, strategy, and settings using a teacher-friendly default language and collapsible advanced sections.
- Step 5: Added an AI coach with streaming responses, personalized context injection, daily free-tier message caps, and audit logging of chat interactions.

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

## What is broken or incomplete
- Step 6+ items not started yet (forecast trust layer, billing, ops)
- Streamlit code remains in repo during transition, but Next.js is the primary UI path
- Supabase currently running in local sqlite fallback mode until credentials are provided

## Architecture decisions locked in
- Backend-first architecture: Streamlit is now an API client and does not run forecast services directly.
- Persistence abstraction uses Supabase when configured, with local sqlite fallback to avoid credential blocking.
- Macro feature pipeline is normalized as a backend service dependency for all forecast runs.
- UI language defaults to plain-English guidance for beginners; technical diagnostics are intentionally gated behind explicit "Advanced" expanders.
- Coach responses stream over SSE from backend to frontend to avoid spinner-style waiting and improve perceived responsiveness.

## Do not redo
- Do not move forecasting/data-fetch logic back into Streamlit.
- Do not hardcode service keys; keep environment-driven config only.

## Notes
- System `pip3` is broken on Homebrew Python in this environment; package installs were completed with `/usr/bin/python3 -m pip`.