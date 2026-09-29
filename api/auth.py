"""API autentifikatsiyasi.

Har bir so'rovda `Authorization: Bearer <secret>` yoki `X-API-Key: <secret>`
kerak. Noto'g'ri/bo'sh kalit -> 401 Unauthorized.

Xavfsizlik eslatmalari:
  * Solishtirish `hmac.compare_digest` bilan (timing-attackka qarshi).
  * Secret hech qachon loglarga chiqmaydi.
"""
import hmac
import logging

from fastapi import Header, HTTPException, status

import config

log = logging.getLogger("api.auth")


def _extract_token(authorization: str | None, x_api_key: str | None) -> str:
    if x_api_key:
        return x_api_key.strip()
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        return authorization.strip()
    return ""


async def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency — noto'g'ri kalitni 401 bilan rad etadi."""
    secret = config.TEST_API_SECRET
    if not secret:
        # Xato konfiguratsiya — himoyasiz API ochilmasligi kerak.
        log.error("TEST_API_SECRET sozlanmagan — API so'rovlar rad etilmoqda.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API is not configured",
        )

    token = _extract_token(authorization, x_api_key)
    if not token or not hmac.compare_digest(token, secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
