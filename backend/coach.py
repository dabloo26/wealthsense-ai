from __future__ import annotations

import os
from typing import Generator


def build_coach_context(
    profile: dict[str, object],
    portfolio: dict[str, object],
    latest_goal_plan: dict[str, object] | None,
    latest_forecast: dict[str, object] | None,
    macro: dict[str, object],
) -> str:
    return (
        "You are WealthSense AI Financial Coach. Give practical, calm, personalized guidance.\n"
        "Use plain language, avoid generic advice, and keep a supportive tone.\n"
        f"User profile: {profile}\n"
        f"User portfolio: {portfolio}\n"
        f"Latest goal plan: {latest_goal_plan}\n"
        f"Latest forecast: {latest_forecast}\n"
        f"Macro context today: {macro}\n"
    )


def generate_coach_text(context: str, question: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return (
            "Based on your current plan, you are making progress, but your success odds can improve with "
            "either a higher monthly contribution or a longer timeline. If you want, I can walk through both options."
        )
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": f"{context}\nUser question: {question}"}],
        )
        return resp.content[0].text if resp.content else "I couldn't produce a response right now."
    except Exception as exc:  # pragma: no cover - external service fallback
        return f"I hit a temporary issue generating an answer ({exc}). Please try again."


def stream_tokens(text: str) -> Generator[str, None, None]:
    # Simulate token-level streaming for SSE clients.
    words = text.split(" ")
    for w in words:
        yield w + " "

