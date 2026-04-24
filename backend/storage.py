from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - import guard for local fallback
    Client = Any  # type: ignore[assignment]
    create_client = None


class PersistenceStore:
    def __init__(self) -> None:
        self._sqlite_path = Path("artifacts/wealthsense_backend.db")
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._supabase = self._build_supabase_client()
        self._ensure_sqlite_tables()

    def save_forecast(self, payload: dict[str, Any]) -> None:
        if self._supabase is not None:
            self._supabase.table("forecast_results").insert(payload).execute()
            return
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                "INSERT INTO forecast_results (ticker, payload_json) VALUES (?, ?)",
                (payload.get("ticker", "UNKNOWN"), json.dumps(payload, default=str)),
            )
            conn.commit()

    def save_goal_plan(self, payload: dict[str, Any]) -> None:
        if self._supabase is not None:
            self._supabase.table("goal_plans").insert(payload).execute()
            return
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                "INSERT INTO goal_plans (target_amount, payload_json) VALUES (?, ?)",
                (float(payload.get("target_amount", 0.0)), json.dumps(payload, default=str)),
            )
            conn.commit()

    def backend_mode(self) -> str:
        return "supabase" if self._supabase is not None else "sqlite-fallback"

    def save_user_profile(self, token: str, payload: dict[str, Any]) -> None:
        payload = {"token": token, **payload}
        if self._supabase is not None:
            self._supabase.table("user_profiles").upsert(payload).execute()
            return
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_profiles (token, payload_json) VALUES (?, ?)",
                (token, json.dumps(payload, default=str)),
            )
            conn.commit()

    def get_user_profile(self, token: str) -> dict[str, Any] | None:
        if self._supabase is not None:
            resp = self._supabase.table("user_profiles").select("*").eq("token", token).limit(1).execute()
            data = resp.data or []
            return data[0] if data else None
        with sqlite3.connect(self._sqlite_path) as conn:
            row = conn.execute("SELECT payload_json FROM user_profiles WHERE token = ?", (token,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_portfolio(self, token: str, payload: dict[str, Any]) -> None:
        payload = {"token": token, **payload}
        if self._supabase is not None:
            self._supabase.table("portfolios").insert(payload).execute()
            return
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                "INSERT INTO portfolios (token, payload_json) VALUES (?, ?)",
                (token, json.dumps(payload, default=str)),
            )
            conn.commit()

    def latest_portfolio(self, token: str) -> dict[str, Any] | None:
        if self._supabase is not None:
            resp = (
                self._supabase.table("portfolios")
                .select("*")
                .eq("token", token)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            data = resp.data or []
            return data[0] if data else None
        with sqlite3.connect(self._sqlite_path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM portfolios WHERE token = ? ORDER BY id DESC LIMIT 1",
                (token,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def latest_goal_plan(self) -> dict[str, Any] | None:
        with sqlite3.connect(self._sqlite_path) as conn:
            row = conn.execute("SELECT payload_json FROM goal_plans ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def latest_forecast(self, token: str | None = None) -> dict[str, Any] | None:
        # Token is reserved for future per-user partitioning.
        _ = token
        with sqlite3.connect(self._sqlite_path) as conn:
            row = conn.execute("SELECT payload_json FROM forecast_results ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def log_audit_event(self, token: str, event_type: str, payload: dict[str, Any]) -> None:
        record = {
            "token": token,
            "event_type": event_type,
            "payload": payload,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if self._supabase is not None:
            self._supabase.table("audit_log").insert(record).execute()
            return
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                "INSERT INTO audit_log (token, event_type, payload_json) VALUES (?, ?, ?)",
                (token, event_type, json.dumps(record, default=str)),
            )
            conn.commit()

    def count_daily_coach_messages(self, token: str) -> int:
        if self._supabase is not None:
            today = datetime.now(timezone.utc).date().isoformat()
            resp = (
                self._supabase.table("audit_log")
                .select("event_type", count="exact")
                .eq("token", token)
                .eq("event_type", "coach_message")
                .gte("ts", f"{today}T00:00:00")
                .execute()
            )
            return int(resp.count or 0)
        with sqlite3.connect(self._sqlite_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM audit_log
                WHERE token = ?
                  AND event_type = 'coach_message'
                  AND DATE(created_at) = DATE('now')
                """,
                (token,),
            ).fetchone()
        return int(row[0] if row else 0)

    def _build_supabase_client(self) -> Client | None:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not key or create_client is None:
            return None
        try:
            return create_client(url, key)
        except Exception:
            return None

    def _ensure_sqlite_tables(self) -> None:
        with sqlite3.connect(self._sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS forecast_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS goal_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_amount REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    token TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

