"""Opaque access token creation and hashing."""

import hashlib
import hmac
import secrets


class TokenService:
    def __init__(self, pepper: str) -> None:
        if len(pepper) < 16:
            raise ValueError("令牌 Pepper 至少需要 16 个字符")
        self._pepper = pepper.encode()

    def issue_task_token(self) -> str:
        return f"tp_task_{secrets.token_urlsafe(24)}"

    def issue_plan_token(self) -> str:
        return f"tp_plan_{secrets.token_urlsafe(24)}"

    def digest(self, token: str) -> str:
        return hmac.new(self._pepper, token.encode(), hashlib.sha256).hexdigest()
