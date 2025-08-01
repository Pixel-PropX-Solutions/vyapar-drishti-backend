from typing import Literal, Optional

from pydantic import BaseModel


class BaseToken(BaseModel):
    access_token: str
    refresh_token: str
    scope: str


class TokenData(BaseModel):
    user_id: str
    # email: str
    user_type: Literal["admin", "user"] = "user"
    scope: Literal["login", "forgot_password", "verify_email"] = "login"
    current_company_id: Optional[str] = None  # ✅ new
    device_type: str
    token_version: Optional[int] = 1  # Add token_version for versioning


class RefreshTokenPost(BaseModel):
    refresh_token: str


class OnlyRefreshToken(BaseModel):
    refresh_token: str
