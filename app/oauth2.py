import datetime

from fastapi import Depends, status, Request, Response
from fastapi.security import OAuth2
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel

from jose import JWTError, jwt
import app.http_exception as http_exception
from app.Config import ENV_PROJECT
from app.database.models.token import RefreshTokenCreate
from app.database.repositories.token import refresh_token_repo
from app.schema.token import BaseToken, TokenData
import requests
from typing import Optional, Dict


class OAuth2PasswordBearerWithCookie(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: Optional[str] = None,
        scopes: Optional[Dict[str, str]] = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlowsModel(password={"tokenUrl": tokenUrl, "scopes": scopes})
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[str]:
        access_token: str = request.cookies.get("access_token", "")
        refresh_token: str = request.cookies.get("refresh_token", "")

        if refresh_token:
            return {"access_token": access_token, "refresh_token": refresh_token}
        else:
            if self.auto_error:
                raise http_exception.CredentialsInvalidException(
                    detail="Not authenticated. Please login again."
                )
            else:
                return None


oauth2_scheme = OAuth2PasswordBearerWithCookie(
    tokenUrl=ENV_PROJECT.BASE_API_V1 + "/auth/login",
    scheme_name="User Authentication",
)

async def get_current_user(
    tokens: dict = Depends(oauth2_scheme),
) -> TokenData:
    token: TokenData = await verify_access_token(tokens["access_token"])
    # Check token_version in DB
    db_token = await refresh_token_repo.findOne(
        {
            "user_id": token.user_id,
            "device_type": token.device_type,
            "user_type": token.user_type,
        },
        {"token_version"},
    )
    if not db_token or db_token.get("token_version", 1) != token.token_version:
        raise http_exception.CredentialsInvalidException(
            detail="Token is invalid or has been revoked."
        )
    return token


async def create_refresh_token(data: TokenData):
    to_encode = data.model_dump()
    to_encode.update()
    encoded_jwt = jwt.encode(
        to_encode, ENV_PROJECT.REFRESH_TOKEN_SECRET, algorithm="HS256"
    )
    return encoded_jwt


async def verify_refresh_token(refresh_token: str) -> TokenData:
    try:
        payload = jwt.decode(
            refresh_token, ENV_PROJECT.REFRESH_TOKEN_SECRET, algorithms="HS256"
        )

        user_id: str = payload.get("user_id", None)
        user_type: str = payload.get("user_type", None)
        scope: str = payload.get("scope", None)
        device_type: str = payload.get("device_type")  # ⬅️ Important
        if not all([user_id, user_type, scope, device_type]):
            raise http_exception.CredentialsInvalidException(
                detail="Invalid refresh token payload."
            )

        token_in_db = await refresh_token_repo.findOne({"refresh_token": refresh_token})

        if not token_in_db:
            raise http_exception.CredentialsInvalidException(
                detail="Refresh token not found in database."
            )
        if user_id is None or user_type is None or scope is None:
            raise http_exception.CredentialsInvalidException(
                detail="Invalid refresh token payload."
            )
        token_data = TokenData(
            user_id=user_id,
            user_type=user_type,
            scope=scope,
            device_type=device_type,
        )
        return token_data
    except JWTError:
        raise http_exception.CredentialsInvalidException(
            detail="Invalid refresh token. Please login again."
        )


async def create_access_token(
    data: TokenData,
    device_type: str,
    old_refresh_token: str = None,
) -> BaseToken:
    to_encode = data.model_dump()
    to_encode.update(
        {"device_type": data.device_type, "token_version": data.token_version}
    )  # include token_version
    access_token = jwt.encode(
        to_encode, ENV_PROJECT.ACCESS_TOKEN_SECRET, algorithm="HS256"
    )
    refresh_token = await create_refresh_token(data=data)

    refresh_token_data: RefreshTokenCreate = RefreshTokenCreate(
        refresh_token=refresh_token,
        user_id=data.user_id,
        user_type=data.user_type,
        device_type=device_type,
        token_version=data.token_version,
    )

    if old_refresh_token:
        res = await refresh_token_repo.update_one(
            {"refresh_token": old_refresh_token, "user_id": data.user_id},
            {
                "$set": {
                    "refresh_token": refresh_token,
                    "updated_at": datetime.datetime.now(),
                }
            },
        )
        if res.matched_count == 0:
            raise http_exception.CredentialsInvalidException(
                detail="Old refresh token not found."
            )
    else:
        # 🧼 First delete any existing token for this user/device_type
        await refresh_token_repo.deleteOne(
            {
                "user_id": data.user_id,
                "user_type": data.user_type,
                "device_type": device_type,
            }
        )
        res = await refresh_token_repo.new(data=refresh_token_data)
    if res:
        token: BaseToken = BaseToken(
            access_token=access_token, refresh_token=refresh_token, scope=data.scope
        )
        return token
    raise http_exception.InternalServerErrorException()


async def get_new_access_token(refresh_token: str):
    token_data = await verify_refresh_token(refresh_token)
    return await create_access_token(
        data=token_data,
        old_refresh_token=refresh_token,
        device_type=token_data.device_type,  # ✅ Pass the decoded device_type
    )


async def create_forgot_password_access_token(data: TokenData):
    to_encode = data.model_dump()
    expire = datetime.datetime.now() + datetime.timedelta(
        minutes=ENV_PROJECT.EMAIL_CONFIRMATION_TOKEN_EXPIRE_MINUTES * 10
    )
    to_encode.update({"exp": expire})
    access_token = jwt.encode(
        to_encode, ENV_PROJECT.FORGOT_PASSWORD_TOKEN_SECRET, algorithm="HS256"
    )
    return access_token


async def create_email_verify_access_token(data: TokenData, timeout: int = 10):
    to_encode = data.model_dump()
    expire = datetime.datetime.now() + datetime.timedelta(
        minutes=ENV_PROJECT.EMAIL_CONFIRMATION_TOKEN_EXPIRE_MINUTES * timeout
    )
    to_encode.update({"exp": expire})
    access_token = jwt.encode(
        to_encode, ENV_PROJECT.FORGOT_PASSWORD_TOKEN_SECRET, algorithm="HS256"
    )
    return access_token


async def verify_email_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token,
            ENV_PROJECT.FORGOT_PASSWORD_TOKEN_SECRET,
            algorithms=["HS256"],
        )
        user_id = payload.get("user_id", None)
        user_type: str = payload.get("user_type", None)
        scope: str = payload.get("scope", None)
        device_type: str = payload.get("device_type", None)
        if (
            user_id is None
            or user_type is None
            or device_type is None
            or scope != "verify_email"
        ):
            raise http_exception.CredentialsInvalidException(
                detail="Invalid email verification token payload."
            )
        token_data = TokenData(
            user_id=user_id, user_type=user_type, scope=scope, device_type=device_type
        )
        return token_data
    except JWTError:
        raise http_exception.CredentialsInvalidException(
            detail="Invalid forgot password token. Please request a new one."
        )


async def verify_forgot_password_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(
            token,
            ENV_PROJECT.FORGOT_PASSWORD_TOKEN_SECRET,
            algorithms=["HS256"],
        )
        user_id = payload.get("user_id", None)
        user_type: str = payload.get("user_type", None)
        scope: str = payload.get("scope", None)
        if user_id is None or user_type is None or scope != "forgot_password":
            raise http_exception.CredentialsInvalidException(
                detail="Invalid forgot password token payload."
            )
        token_data = TokenData(user_id=user_id, user_type=user_type, scope=scope)
        return token_data
    except JWTError:
        raise http_exception.CredentialsInvalidException(
            detail="Invalid forgot password token. Please request a new one."
        )


async def verify_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, ENV_PROJECT.ACCESS_TOKEN_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id", None)
        user_type: str = payload.get("user_type", None)
        device_type: str = payload.get("device_type", None)
        scope: str = payload.get("scope", None)
        current_company_id = payload.get("current_company_id", None)
        token_version = payload.get("token_version", 1)
        if (
            user_id is None
            or user_type is None
            or scope is None
            or scope != "login"
            or device_type is None
        ):
            raise http_exception.CredentialsInvalidException(
                detail="Invalid access token payload."
            )
        token_data = TokenData(
            user_id=user_id,
            user_type=user_type,
            device_type=device_type,
            scope=scope,
            current_company_id=current_company_id,
            token_version=token_version,
        )
        return token_data
    except JWTError:
        raise http_exception.CredentialsInvalidException(
            detail="Invalid access token. Please login again."
        )


async def get_refresh_token(tokens: dict = Depends(oauth2_scheme)) -> str:
    return tokens["refresh_token"]


def set_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ENV_PROJECT.LOGIN_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        secure=True,
        samesite="none",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=ENV_PROJECT.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        secure=True,
        samesite="none",
    )


# async def send_whatsapp_message(message: str, to_number: str):
#     print("Sending WhatsApp message:", message, "to", to_number)
#     url = f"https://graph.facebook.com/v22.0/{ENV_PROJECT.PHONE_NUMBER_ID}/messages"
#     headers = {
#         "Authorization": f"Bearer {ENV_PROJECT.WHATSAPP_TOKEN}",
#         "Content-Type": "application/json",
#     }

#     payload = {
#         "messaging_product": "whatsapp",
#         "to": to_number,
#         "type": "template",
#         "template": {
#             "name": "logincode",
#             "language": {"code": "en_US"},
#             "components": [
#                 {"type": "body", "parameters": [{"type": "text", "text": message}]},
#                 {
#                     "type": "button",
#                     "sub_type": "url",
#                     "index": "0",
#                     "parameters": [
#                         {
#                             "type": "text",
#                             "text": message,
#                         }
#                     ],
#                 },
#             ],
#         },
#     }
#     print("WhatsApp API payload:", payload)
#     response = requests.post(url, headers=headers, json=payload)
#     print("WhatsApp API response:", response.status_code, response.text)
#     print("WhatsApp API response JSON:", response.json())
#     return response.json()


# async def create_signup_access_token(data: TokenData):
#     to_encode = data.model_dump()
#     expire = datetime.datetime.now() + datetime.timedelta(
#         minutes=ENV_PROJECT.EMAIL_CONFIRMATION_TOKEN_EXPIRE_MINUTES
#     )
#     to_encode.update({"exp": expire})
#     access_token = jwt.encode(
#         to_encode, ENV_PROJECT.SIGNUP_TOKEN_SECRET, algorithm="HS256"
#     )
#     return access_token


# async def verify_signup_access_token(token: str) -> TokenData:
#     try:
#         payload = jwt.decode(
#             token,
#             ENV_PROJECT.SIGNUP_TOKEN_SECRET,
#             algorithms=["HS256"],
#         )
#         id = payload.get("id", None)
#         type: str = payload.get("type", None)
#         scope: str = payload.get("scope", None)
#         if id is None or type is None or scope is None:
#             raise http_exception.TOKEN_CREDENTIALS_INVALID
#         token_data = TokenData(id=id, type=type, scope=scope)
#         if scope != "signup":
#             raise http_exception.OUT_OF_SCOPE_ACCESS_TOKEN
#         return token_data
#     except JWTError:
#         raise http_exception.TOKEN_CREDENTIALS_INVALID
