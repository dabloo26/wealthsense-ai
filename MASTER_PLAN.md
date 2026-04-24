# WealthSense AI — Master Build Plan

You are a senior full-stack + ML engineer working on WealthSense AI — a personal
finance forecasting platform. A working demo exists: Streamlit UI, trained
LSTM/GRU/Transformer models, Monte Carlo engine, ensemble forecasts, strategy
benchmarking.

Your job is to keep making this better — one step at a time — until it is something
people genuinely want to use, pay for, and tell others about.

=======================================================================
HOW YOU WORK
=======================================================================
- Read @STATUS.md before doing anything else. It tells you exactly where we are.
- Complete one step fully before moving to the next.
- After every step, the app must be in a working, runnable state.
- After every step, tell me: what changed, what a user would now experience
  differently, and exactly what to update in STATUS.md.
- Never leave the app broken. If something breaks, fix it before moving on.
- Never redo anything listed in STATUS.md under "Completed steps".
- Never assume a step is done unless STATUS.md says it is.
- If you are unsure about a product decision, default to what feels most
  useful to a real person — not what is most technically interesting.

=======================================================================
CURRENT STATE
=======================================================================
See @STATUS.md for the live state of the project.

=======================================================================
STEP 1 — Make it feel real, not like a demo
=======================================================================
Right now the app runs on CSV files and local model artifacts. A real product
runs on live data and a real backend.

- Build a FastAPI backend in `backend/`. Move ALL model inference and data
  fetching out of Streamlit into API endpoints.
- Replace static CSV data with live price fetching via yfinance.
- Add macro features: pull VIX (^VIX), Fed Funds Rate (FRED), and CPI (FRED)
  and include them as model input features alongside price data.
- Set up PostgreSQL (Supabase free tier). Migrate forecast outputs and
  strategy results from CSV artifacts to DB writes.
- Add a /health endpoint. Add a /forecast endpoint. Add a /goal-plan endpoint.
- Update Streamlit to call the FastAPI backend instead of running Python directly.

When this step is done: the app talks to live data, produces forecasts
backed by macro context, and every result is persisted — not ephemeral.

=======================================================================
STEP 2 — Give users a reason to come back
=======================================================================
Right now there are no users — just anonymous sessions. People do not return
to tools they have no stake in.

- Add user authentication using Clerk (preferred) or Auth0.
- Add a user profile: name, email, risk tolerance (conservative / balanced /
  aggressive), and financial goals (list of: goal name, target amount,
  target date).
- Let users save a portfolio: a named collection of assets with allocations.
- Let users save a goal plan: their Monte Carlo result linked to their goal.
- Show a simple dashboard after login: their saved plan's success probability,
  their portfolio's latest forecast, and one insight sentence.
- Weekly email digest (SendGrid): goal progress, top mover, one tip.

When this step is done: a user can log in, save their plan, and get a
weekly reminder that their money's future lives here.

=======================================================================
STEP 3 — Make the first 3 minutes magical
=======================================================================
Right now a new user lands and has to figure everything out. Most will leave.
The first 3 minutes must do the work of a good financial advisor intake.

- Build a 3-step onboarding wizard (replace the current Start Here flow):
    Step 1 — "What are you working toward?"
             Show 4 cards: Retire early / Buy a home / Build a safety net /
             Grow my wealth. Let them pick one or write their own.
    Step 2 — "How do you feel about risk?"
             A slider with 5 stops. Each stop shows a plain-English sentence
             about what that means for their money, not jargon.
    Step 3 — "Pick your first asset to watch."
             Show the 10 assets as cards with plain names and one-line
             descriptions (not ticker symbols). Pre-select the best match
             for their goal.
- On completion: land them directly on a personalized dashboard with their
  first forecast already rendered and a sentence explaining it in plain English.
- Save all onboarding answers to their user profile.

When this step is done: any person — not just finance people — can get
value from the app in under 3 minutes.

=======================================================================
STEP 4 — Replace Streamlit with a real product UI
=======================================================================
Streamlit is a prototype tool. It signals "demo" to every user who sees it.
A product people want to use needs to feel like a product.

- Scaffold a Next.js + TypeScript + Tailwind CSS frontend in `frontend/`.
- Use shadcn/ui as the component library.
- Rebuild every Streamlit screen as a proper page:
    /               → landing page (value prop, social proof, CTA)
    /onboarding     → the 3-step wizard from Step 3
    /dashboard      → user's home: portfolio summary, goal health,
                      latest forecast, coach panel
    /forecast       → full forecast detail with SHAP explanation
    /goals          → goal planner (Monte Carlo)
    /strategy       → scenario studio and benchmarking
    /settings       → profile, risk tolerance, notifications
- Mobile responsive. Works on a phone without horizontal scrolling.
- Keep the beginner/advanced split: advanced controls are collapsed by
  default, one click to expand.
- Remove Streamlit entirely once parity is reached.

When this step is done: it looks and feels like a funded product, not
a hackathon project.

=======================================================================
STEP 5 — Add the feature that no competitor has
=======================================================================
Bloomberg has data. Robinhood has simplicity. Personal Capital has net worth
tracking. WealthSense's unique edge is a financial coach that knows YOUR
specific numbers and goals — not generic advice.

- Add an AI Financial Coach chat panel to the dashboard (right sidebar
  on desktop, bottom sheet on mobile).
- Powered by Claude API (claude-sonnet-4-20250514, streaming via SSE).
- System prompt must inject: user's portfolio, their goals, their risk
  profile, their latest forecast results, and today's macro context (VIX,
  Fed rate). The coach must answer questions about THEIR situation, not
  general finance.
- Example queries the coach must handle well:
    "Am I on track to retire at 60?"
    "What would happen if I invested $300 more per month?"
    "Explain my forecast like I'm 25 and scared of the stock market."
    "Should I be worried about this VIX spike?"
    "What's my biggest financial risk right now?"
- Responses stream token by token. No loading spinners.
- Log all conversations to the DB (audit_log table).
- Cap free-tier users at 10 messages/day. No cap for paid users.

When this step is done: users will say "this thing actually understands
my situation" — which is something no existing product can say.

=======================================================================
STEP 6 — Make forecasts trustworthy, not just impressive
=======================================================================
Right now forecasts are technically good but visually unaccountable —
users have no reason to believe them beyond hoping the model is smart.
Trust is earned through transparency.

- Implement walk-forward backtesting for all models:
    * Rolling window: 18 months train, 3 months test, step 1 month
    * Report per model and per asset: MAE, Sharpe ratio, Hit Rate,
      Max Drawdown
    * Include transaction cost model: 0.05% slippage per trade
- Add SHAP values to every forecast:
    * Show top 3 drivers: "VIX rising = higher uncertainty, Fed rate
      stable = neutral, 30-day momentum = bullish"
    * Render as a horizontal bar chart in the forecast detail page
- Add plain-language explanation generated by Claude API:
    * One paragraph, written for the specific user's risk profile
    * "Your cautious profile means we weighted downside risk more heavily.
       Here's what's driving the uncertainty..."
- Show model confidence intervals prominently — not hidden. Users should
  see the range, not just the line.
- Add a visible disclaimer on every forecast card:
    "Not financial advice. Forecasts carry uncertainty.
     Past performance does not predict future results."

When this step is done: a skeptical user can look at a forecast and
understand why it says what it says — and that is rare.

=======================================================================
STEP 7 — Add a revenue engine
=======================================================================
A product people want to pay for is a product they believe in.
Charging for it is proof that it works.

- Integrate Stripe Checkout + Customer Portal.
- Three tiers:
    Free   — 3 assets, 30-day forecast horizon, 10 coach messages/day
    Pro    — $19/mo — unlimited assets, 1-year horizon, unlimited coach,
             weekly digest, scenario studio, backtest reports
    Advisor — $99/mo — everything in Pro, plus: client sub-accounts (up to 25),
              white-label (firm name + logo), bulk PDF export of goal plans
- Enforce limits via middleware on all API routes, not just UI.
- Stripe webhook → update user.tier in DB on payment/cancellation.
- 14-day free trial for Pro. No credit card required to start.
- Upgrade prompt: show contextually when a free user hits a limit,
  not as a popup on first visit.

When this step is done: the product makes money, which means it is
sustainable, which means users can trust it will still exist next year.

=======================================================================
STEP 8 — Make it operationally solid
=======================================================================
A product people recommend is one that never goes down, never loses
their data, and gets better over time without them noticing.

- Add MLflow for experiment tracking: log all model runs, hyperparams,
  and backtest metrics. Tag models as staging vs production.
- Add scheduled retraining: GitHub Actions cron every Sunday.
  Retrain on latest data → run backtest → promote only if metrics improve.
  Send Slack/email alert with outcome.
- Add drift detection: alert if rolling forecast error exceeds 2x baseline.
- Add Sentry for error tracking (backend + frontend).
- Add structured logging (loguru): every request logs user_id,
  endpoint, latency, model version used.
- Add GDPR basics: /account/export and /account/delete endpoints.
- Add audit log entries for every forecast, plan save, and coach message.
- Set up uptime monitoring (UptimeRobot free tier).

When this step is done: the product runs itself, improves itself,
and a user who trusts it with their financial future can trust
it to stay alive and honest.

=======================================================================
STEP 9 — Make the models actually good
=======================================================================
This step upgrades the core ML from "technically deep learning" to 
"state of the art for financial time series."

TASK 9.1 — ENRICH FEATURES
- Add macro features to all model inputs:
    * VIX (^VIX) — fear index
    * 10Y-2Y yield spread (T10Y2Y from FRED) — recession signal
    * DXY (DX-Y.NYB) — dollar strength
    * CPI month-over-month change (FRED)
    * Fed Funds Rate (FRED)
- Add sentiment features:
    * Integrate FinBERT (ProsusAI/finbert on HuggingFace)
    * Score daily news headlines per asset: positive / negative / neutral
    * Rolling 5-day sentiment score as a feature
- Add cross-asset correlation matrix as a feature block
- Add earnings calendar binary flag: earnings in next 5 days = 1
- Store enriched feature set in PostgreSQL feature store

TASK 9.2 — FIX UNCERTAINTY QUANTIFICATION
- Replace static confidence intervals with Monte Carlo Dropout:
    * Run inference 100 times with dropout active
    * Report mean, 10th percentile, 90th percentile
    * Intervals must widen during high-VIX regimes automatically
- Add conformal prediction calibration:
    * Calibrate intervals on held-out data so "90% interval" actually 
      contains the true value 90% of the time

TASK 9.3 — UPGRADE ENSEMBLE
- Replace simple averaging with a stacking meta-model:
    * Train a Ridge regression meta-model on LSTM/GRU/Transformer outputs
    * Meta-model trained on rolling validation window, not full history
- Add dynamic model weighting:
    * Weight each base model by its inverse rolling 30-day MAE
    * Recompute weights weekly during scheduled retraining

TASK 9.4 — ADD REGIME DETECTION
- Train a Gaussian HMM (hmmlearn) on VIX + returns + volume:
    * 3 regimes: low volatility bull / high volatility bull / bear
- Route each prediction to a regime-specific ensemble
- Show current regime on the dashboard: 
    "Market is currently in a high-volatility regime — 
     forecasts carry wider uncertainty"

TASK 9.5 — REPLACE TRANSFORMER WITH TFT
- Implement Temporal Fusion Transformer using pytorch-forecasting library
- Inputs: price history, macro features, sentiment, earnings flag,
  static asset metadata (sector, asset class)
- Outputs: multi-horizon forecast (7d, 30d, 90d, 180d, 365d) with 
  quantile predictions (10th, 50th, 90th percentile)
- Keep LSTM and GRU as ensemble members alongside TFT
- Run head-to-head backtest: TFT vs old Transformer, promote only if better

TASK 9.6 — ADD RL PORTFOLIO ALLOCATION (stretch goal)
- Frame portfolio allocation as an RL problem:
    * State: current allocations, forecast outputs, macro regime, 
      user risk tolerance
    * Action: rebalancing weights across 10 assets
    * Reward: risk-adjusted return (Sharpe ratio) minus transaction costs
- Train using Stable Baselines3 (PPO agent)
- Constraints: max 40% in any single asset, must match user risk profile
- Show suggested allocation on dashboard:
    "Based on current forecasts and your risk profile, here is the 
     suggested allocation for the next 30 days"
- This is not financial advice — show disclaimer prominently

When this step is done: the models understand market context, 
not just price history. Uncertainty is honest. The ensemble is 
smart. And the product answers "what should I do" not just 
"what might happen."

=======================================================================
EXECUTION RULES
=======================================================================
1. Before starting each step, read the existing relevant files first.
2. State clearly what you are about to build and what files will change.
3. Write tests for every new service or API endpoint (pytest, >80% coverage).
4. Never hardcode secrets. All environment variables go in .env.example.
5. After completing each step, confirm the app runs end-to-end before
   declaring the step done.
6. Commit message format: `feat(step1): add FastAPI backend with live data`
7. Tell me exactly what to update in STATUS.md after every step.
8. If a decision has multiple valid approaches, pick the simpler one
   and note the trade-off in a comment.

=======================================================================
START
=======================================================================
Read @STATUS.md first. Then read the current step listed there.

Before writing any code:
- Audit the relevant files for the current step
- List every file that will change
- Propose any new directory structure needed
- Check for dependency conflicts
- Ask for my confirmation before writing a single line of code

Do not proceed to the next step until the current one is fully
working and I have confirmed I am satisfied with it.