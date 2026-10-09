"""NIO-specific OAuth response helpers."""

from __future__ import annotations

from typing import Any


class InvalidTokenResponseError(ValueError):
    """The NIO OAuth response did not contain a usable token."""

    def __init__(self, message: str, *, result_code: str | None = None) -> None:
        super().__init__(message)
        self.result_code = result_code


REAUTH_RESULT_CODES = frozenset(
    {"invalid_grant", "invalid_token", "access_denied", "unauthorized"}
)
TRANSIENT_RESULT_CODES = frozenset(
    {"server_error", "temporarily_unavailable", "internal_error", "rate_limited"}
)


def unwrap_token_response(payload: object) -> dict[str, Any]:
    """Extract and validate NIO's OAuth token from its API envelope."""
    if not isinstance(payload, dict):
        raise InvalidTokenResponseError("NIO OAuth response is not an object")
    result_code = payload.get("result_code", payload.get("error"))
    if result_code != "success":
        raise InvalidTokenResponseError(
            "NIO OAuth request was unsuccessful",
            result_code=result_code if isinstance(result_code, str) else None,
        )
    token = payload.get("data")
    if not isinstance(token, dict):
        raise InvalidTokenResponseError("NIO OAuth response has no data object")
    required = ("access_token", "refresh_token", "expires_in", "token_type")
    if any(not token.get(key) for key in required):
        raise InvalidTokenResponseError("NIO OAuth response is missing token fields")
    return dict(token)
