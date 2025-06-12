from fastapi import APIRouter, BackgroundTasks, Depends, status, Response, Header
from fastapi.responses import ORJSONResponse
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from app.Config import ENV_PROJECT
from app.database.models.user import User, UserCreate
from loguru import logger
from pydantic import BaseModel
import app.http_exception as http_exception
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.utils.hashing import verify_hash, hash_password
from app.oauth2 import get_current_user
from app.database.repositories.token import refresh_token_repo

# from app.database.connections.mongo import conn
from app.database import mongodb

# from app.database.repositories.token import refresh_token_repo
from app.oauth2 import (
    create_access_token,
    # create_forgot_password_access_token,
    # create_signup_access_token,
    get_new_access_token,
    # verify_forgot_password_access_token,
    # verify_signup_access_token,
    get_refresh_token,
    set_cookies,
)
from app.schema.token import TokenData
from app.utils import generatePassword, hashing
from app.database.repositories.user import user_repo
from app.utils.generatePassword import generatePassword

# from app.utils.mailer_module import mail, template
from app.Config import ENV_PROJECT
from app.utils.mailer_module import template
from app.utils.mailer_module import mail
from app.database.repositories.companyRepo import company_repo, Company

# from app.schema.password import SetPassword
from typing import Optional
from app.schema.enums import UserTypeEnum


auth = APIRouter()


class TenantID(BaseModel):
    tenant_id: Optional[str] = None
    tenant_email: Optional[str] = None


class Email_Body(BaseModel):
    email: str


@auth.post("/login", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def login(
    response: Response,
    user_type: UserTypeEnum,
    creds: OAuth2PasswordRequestForm = Depends(),
):
    user = None
    if user_type == UserTypeEnum.ADMIN and creds.username == ENV_PROJECT.ADMIN_EMAIL:
        user = {
            "password": ENV_PROJECT.ADMIN_PASSWORD,
            "_id": "",
        }
    elif user_type in [UserTypeEnum.USER]:
        user = await user_repo.findOne(
            {"email": creds.username},
            {"_id", "password"},
        )
    if not user:
        raise http_exception.CredentialsInvalidException()

    if hashing.verify_hash(creds.password, user["password"]):
        token_data = TokenData(
            user_id=user["_id"], user_type=user_type.value, scope="login"
        )
        token_generated = await create_access_token(token_data)
        set_cookies(response, token_generated.access_token, token_generated.refresh_token)
        return {"ok": True, "accessToken": token_generated.access_token}

    raise http_exception.CredentialsInvalidException()


@auth.post("/register", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def register(
    response: Response,
    user: UserCreate,
):

    userExists = await user_repo.findOne({"email": user.email})
    if userExists is not None:
        raise http_exception.ResourceNotFoundException()

    password = await generatePassword.createPassword()

    mail.send(
        "Welcome to Vyapar Drishti",
        user.email,
        template.Onboard(role="user", email=user.email, password=password),
    )

    inserted_dict = {}

    keys = ["password", "email", "phone", "user_type", "name"]
    values = [hash_password(password=password), user.email, user.phone, "user", user.name]

    for k, v in zip(keys, values):
        inserted_dict[k] = v

    user_res = await user_repo.new(User(**inserted_dict))

    token_data = TokenData(
        user_id=user_res.id, user_type=user_res.user_type.value, scope="login"
    )
    token_generated = await create_access_token(token_data)
    set_cookies(response, token_generated.access_token, token_generated.refresh_token)
    return {"ok": True, "accessToken": token_generated.access_token}


@auth.get("/current/user", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def get_current_user_details(
    current_user: TokenData = Depends(get_current_user),
):
    user = await user_repo.findOne({"_id": current_user.user_id})
    if user is None:
        if current_user.user_type == "admin":
            return {
                "success": True,
                "message": "User Profile Fetched Successfully",
                "data": [
                    {
                        "_id": "adim-0001",
                        "email": "admin@dristi.com",
                        "user_type": "admin",
                        "name": {
                            "first": "Tohid",
                            "last": "Khan",
                        },
                        "phone": {
                            "code": "+91",
                            "number": "6367097548",
                        },
                        "image": "",
                        "created_at": "2023-10-01T00:00:00Z",
                    }
                ],
            }
        else:
            raise http_exception.ResourceNotFoundException()

    user_pipeline = [
        {"$match": {"_id": current_user.user_id}},
        {
            "$project": {
                "password": 0,
                "updated_at": 0,
            }
        },
    ]

    company_pipeline = [
        {"$match": {"user_id": current_user.user_id, "is_deleted": False}},
        {
            "$project": {
                "company_id": "$_id",
                "company_name": 1,
                "image": 1,
                "address_1": 1,
                "address_2": 1,
                "pinCode": 1,
                "state": 1,
                "country": 1,
                "phone": 1,
                "email": 1,
                "financial_year_start": 1,
                "books_begin_from": 1,
                'is_selected': 1,
            },
        },
    ]

    response = await user_repo.collection.aggregate(pipeline=user_pipeline).to_list(None)
    if not response:
        raise http_exception.ResourceNotFoundException("User not found")

    company = await company_repo.collection.aggregate(pipeline=company_pipeline).to_list(
        None
    )
    
    data = response[0]
    if company:
        data["company"] = company
    else:
        data["company"] = []

    return {
        "success": True,
        "message": "User Profile Fetched Successfully",
        "data": response,
    }


@auth.post("/refresh", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def token_refresh(
    response: Response, refresh_token: str = Depends(get_refresh_token)
):
    token_generated = await get_new_access_token(refresh_token)
    set_cookies(response, token_generated.access_token, token_generated.refresh_token)
    return {"ok": True}


@auth.post("/logout", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def logout(response: Response, refresh_token: str = Depends(get_refresh_token)):
    await refresh_token_repo.deleteOne({"refresh_token": refresh_token})
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        max_age=0,
        secure=True,
        samesite="none",
    )
    response.set_cookie(
        key="refresh_token",
        value="",
        httponly=True,
        max_age=0,
        secure=True,
        samesite="none",
    )
    return {"ok": True}
