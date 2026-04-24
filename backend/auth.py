from __future__ import annotations

import os
import secrets


def issue_mock_token(email: str) -> str:
    return f"ws_{secrets.token_hex(16)}_{email.lower()}"


def validate_token(auth_header: str | None) -> str:
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ValueError("Missing bearer token")
    token = auth_header.replace("Bearer ", "", 1).strip()
    if not token.startswith("ws_"):
        raise ValueError("Invalid token format")
    return token


def auth_provider_mode() -> str:
    if os.getenv("CLERK_SECRET_KEY"):
        return "clerk-configured"
    if os.getenv("AUTH0_DOMAIN"):
        return "auth0-configured"
    return "mock-local"

