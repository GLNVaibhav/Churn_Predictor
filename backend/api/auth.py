"""Authentication boundary for the FastAPI service.

Production requests are accepted only from the trusted Next.js BFF. The BFF
validates the HttpOnly session and supplies the verified user identity together
with a shared secret. Direct browser-to-backend authentication is not allowed.
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from backend.config import settings


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    role: str = "member"
    local_development: bool = False


def require_user(request: Request) -> CurrentUser:
    """Require a trusted BFF identity in production; permit local-only mode."""
    if settings.AUTH_MODE == "development":
        return CurrentUser(user_id="local-development", role="admin", local_development=True)

    expected = settings.UCIF_PROXY_SECRET
    presented = request.headers.get("x-ucif-proxy-secret", "")
    user_id = request.headers.get("x-ucif-user-id", "").strip()
    if len(expected) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured.",
        )
    if not presented or not hmac.compare_digest(presented, expected) or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    if len(user_id) > 128:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    role = request.headers.get("x-ucif-user-role", "member")
    if role not in {"admin", "member"}:
        role = "member"
    return CurrentUser(user_id=user_id, role=role)


def owns_resource(record: dict, user: CurrentUser) -> bool:
    """Only allow owner access; legacy ownerless records stay local-only."""
    owner_id = record.get("owner_id")
    if owner_id is None:
        return user.local_development
    return hmac.compare_digest(str(owner_id), user.user_id)
