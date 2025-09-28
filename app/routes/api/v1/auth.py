import asyncio
import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, Request, status, Response, Header
from fastapi.responses import ORJSONResponse
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from jinja2 import Template
from app.Config import ENV_PROJECT
from app.database.models.user import User, UserCreate


# from app.database.models.OTP import OTP
from loguru import logger
from pydantic import BaseModel
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.utils.hashing import verify_hash, hash_password
from app.oauth2 import get_current_user

from app.database import mongodb

from app.oauth2 import (
    create_access_token,
    create_forgot_password_access_token,
    create_email_verify_access_token,
    verify_email_access_token,
    verify_access_token,
    # create_signup_access_token,
    get_new_access_token,
    verify_forgot_password_access_token,
    # verify_signup_access_token,
    get_refresh_token,
    set_cookies,
)
from app.utils import generatePassword, hashing
from app.utils.generatePassword import generatePassword
from app.routes.api.v1.userSettings import (
    extract_device_info,
    initialize_user_settings,
    classify_client,
)

from app.Config import ENV_PROJECT
from app.utils.mailer_module import template
from app.utils.mailer_module import mail
from app.database.repositories.accountingRepo import accounting_repo
from app.database.repositories.accountingGroupRepo import accounting_group_repo
from app.database.repositories.categoryRepo import category_repo
from app.database.repositories.voucharCounterRepo import vouchar_counter_repo
from app.database.repositories.VoucharTypeRepo import vouchar_type_repo
from app.database.repositories.companyRepo import company_repo
from app.database.repositories.CompanySettingsRepo import company_settings_repo
from app.database.repositories.InventoryRepo import inventory_repo
from app.database.repositories.inventoryGroupRepo import inventory_group_repo
from app.database.repositories.ledgerRepo import ledger_repo
from app.database.repositories.stockItemRepo import stock_item_repo
from app.database.repositories.token import refresh_token_repo
from app.Config import ENV_PROJECT

# from app.database.repositories.otpRepo import otp_repo
from app.database.repositories.UnitOMeasureRepo import units_repo
from app.database.repositories.user import user_repo
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.database.repositories.voucharRepo import vouchar_repo
from typing import Optional
from app.schema.enums import UserTypeEnum
from datetime import datetime
from user_agents import parse


auth = APIRouter()


class TenantID(BaseModel):
    tenant_id: Optional[str] = None
    tenant_email: Optional[str] = None


class Email_Body(BaseModel):
    email: str


class ResetPassword(BaseModel):
    email: str
    new_password: str
    token: str


class EmailQuery(BaseModel):
    firstName: str
    lastName: str
    email: str
    phone: str
    company: str
    industry: str
    employees: str
    message: str
    queryType: str
    time: str
    marketingConsent: bool = True


# class OTPdata(BaseModel):
#     email: str
#     phone_number: str


# @auth.post("/verify/otp", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
# async def login(
#     request: Request,
#     response: Response,
#     user_type: UserTypeEnum,
#     creds: OAuth2PasswordRequestForm = Depends(),
# ):
#     if not creds.username or not creds.password:
#         raise http_exception.CredentialsInvalidException(
#             detail="Username and password are required."
#         )

#     user = None
#     if user_type == UserTypeEnum.ADMIN and creds.username == ENV_PROJECT.ADMIN_EMAIL:
#         user = {
#             "password": ENV_PROJECT.ADMIN_PASSWORD,
#             "_id": "",
#         }


#     elif user_type in [UserTypeEnum.USER]:
#         otp_record = await otp_repo.findOne(
#             {"phone_number": creds.username, "otp": creds.password}
#         )
#         if not otp_record:
#             return ORJSONResponse({"ok": False, "error": "Invalid OTP"}, status_code=400)

#         return {
#             "ok": True,
#             "success": True,
#             "message": "OTP verified successfully. Please proceed to login.",
#         }


@auth.post("/login", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def login(
    request: Request,
    response: Response,
    user_type: UserTypeEnum,
    creds: OAuth2PasswordRequestForm = Depends(),
):
    """Login endpoint for users and admin."""
    if not creds.username or not creds.password:
        raise http_exception.CredentialsInvalidException(
            detail="Username and password are required."
        )

    user = None
    if user_type == UserTypeEnum.ADMIN and creds.username == ENV_PROJECT.ADMIN_EMAIL:
        user = {
            "password": ENV_PROJECT.ADMIN_PASSWORD,
            "_id": "admin-0001",
        }
        token_version = 1
        if hashing.verify_hash(creds.password, user["password"]):
            token_data = TokenData(
                user_id=user["_id"],
                user_type=user_type.value,
                scope="login",
                current_company_id=None,  # ✅ include this
                device_type="PC",  # Assuming admin logs in from a PC
                token_version=token_version,  # Use updated token_version
            )
            token_generated = await create_access_token(
                token_data,
                device_type="PC",  # Assuming admin logs in from a PC
                old_refresh_token=None,
            )
            set_cookies(
                response, token_generated.access_token, token_generated.refresh_token
            )

            return {
                "ok": True,
                "accessToken": token_generated.access_token,
                "refreshToken": token_generated.refresh_token,
            }

        else:
            raise http_exception.InvalidPasswordException(
                detail="Invalid password. Please try again."
            )
    elif user_type in [UserTypeEnum.USER]:
        user = await user_repo.findOne(
            {"email": creds.username},
            {"_id", "password"},
        )

    if not user:
        raise http_exception.ResourceNotFoundException(
            detail="User not found. Please check your username."
        )

    db_password = user["password"]

    user_settings = await user_settings_repo.findOne({"user_id": user["_id"]})

    if not user_settings:
        raise http_exception.ResourceNotFoundException(
            detail="User settings not found. Please contact support."
        )

    company_id = user_settings.get("current_company_id") if user_settings else None

    client_info = classify_client(request.headers.get("user-agent", "unknown"))
    if client_info.get("device_type") in ["Unknown", "Bot"]:
        raise http_exception.UnknownDeviceException(
            detail="Try accessing via another device. This device is compromised or not supported."
        )

    # Check if the user is logged in from the same device type
    existing_token = await refresh_token_repo.findOne(
        {
            "user_id": user["_id"],
            "user_type": user_type,
            "device_type": client_info.get("device_type"),
        }
    )

    if existing_token:

        await refresh_token_repo.update_one(
            {
                "user_id": user["_id"],
                "user_type": user_type,
                "device_type": client_info.get("device_type"),
            },
            {"$inc": {"token_version": 1}},
        )

        db_token = await refresh_token_repo.findOne(
            {
                "user_id": user["_id"],
                "user_type": user_type,
                "device_type": client_info.get("device_type"),
            },
        )

        new_token_version = db_token.get("token_version", 1)
        if hashing.verify_hash(creds.password, db_password):

            token_data = TokenData(
                user_id=user["_id"],
                user_type=user_type.value,
                scope="login",
                current_company_id=company_id,  # ✅ include this
                device_type=client_info.get("device_type"),
                token_version=new_token_version,  # Use updated token_version
            )

            token_generated = await create_access_token(
                token_data,
                device_type=client_info.get("device_type"),
                old_refresh_token=None,
            )

            set_cookies(
                response, token_generated.access_token, token_generated.refresh_token
            )

            await user_settings_repo.update_one(
                {"user_id": user["_id"]},
                {
                    "$set": {
                        "last_login": datetime.now(),
                        "last_login_ip": request.client.host,
                        "last_login_device": client_info.get("info"),
                    }
                },
            )
            # await otp_repo.delete_one({"phone_number": creds.username, "otp": creds.password})
            return {
                "ok": True,
                "accessToken": token_generated.access_token,
                "refreshToken": token_generated.refresh_token,
            }
        else:
            raise http_exception.InvalidPasswordException(
                detail="Invalid password. Please try again."
            )
    else:
        token_version = 1
        if hashing.verify_hash(creds.password, db_password):
            token_data = TokenData(
                user_id=user["_id"],
                user_type=user_type.value,
                scope="login",
                current_company_id=company_id,  # ✅ include this
                device_type=client_info.get("device_type"),
                token_version=token_version,  # Use updated token_version
            )
            token_generated = await create_access_token(
                token_data,
                device_type=client_info.get("device_type"),
                old_refresh_token=None,
            )
            set_cookies(
                response, token_generated.access_token, token_generated.refresh_token
            )

            await user_settings_repo.update_one(
                {"user_id": user["_id"]},
                {
                    "$set": {
                        "last_login": datetime.now(),
                        "last_login_ip": request.client.host,
                        "last_login_device": client_info.get("info"),
                    }
                },
            )

            return {
                "ok": True,
                "accessToken": token_generated.access_token,
                "refreshToken": token_generated.refresh_token,
            }

        else:
            raise http_exception.InvalidPasswordException(
                detail="Invalid password. Please try again."
            )


@auth.post("/register", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def register(
    request: Request,
    response: Response,
    user: UserCreate,
):

    userExists = await user_repo.findOne({"email": user.email})
    if userExists is not None:
        raise http_exception.ResourceConflictException(
            detail="User already exists with the same email. Please try logging in or use a different email."
        )

    client_info = classify_client(request.headers.get("user-agent", "unknown"))
    if client_info.get("device_type") in ["Unknown", "Bot"]:
        raise http_exception.UnknownDeviceException(
            detail="Try accessing via another device. This device is compromised or not supported."
        )

    token_data = TokenData(
        user_id=user.email,
        user_type="user",
        scope="verify_email",
        device_type=client_info.get("device_type"),
    )

    token_generated = await create_email_verify_access_token(
        token_data, timeout=4320
    )  # 3 days

    verification_link = (
        f"{ENV_PROJECT.FRONTEND_DOMAIN}/verify?token={token_generated}&email={user.email}"
    )

    mail.send(
        "Welcome to Vyapar Drishti",
        user.email,
        template.Onboard(
            name=user.name.first,
            verification_link=verification_link,
        ),
    )

    inserted_dict = {}

    keys = ["password", "email", "phone", "user_type", "name"]
    values = [
        hash_password(password=user.password),
        user.email,
        user.phone,
        "user",
        user.name,
    ]

    for k, v in zip(keys, values):
        inserted_dict[k] = v

    user_res = await user_repo.new(User(**inserted_dict))

    ip_address = request.client.host

    await initialize_user_settings(
        user_id=user_res.id,
        last_login_ip=ip_address,
        last_login_device=client_info.get("info"),
        role=user_res.user_type.value,
    )

    return {
        "ok": True,
        "message": "User registered successfully. Please verify your email.",
    }


@auth.post("/verify/email", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def verify_email(email: str, token: str):
    """Verify email endpoint."""
    # Check if the user exists
    userExists = await user_repo.findOne(
        {"email": email}, {"_id", "email", "user_type", "name", "is_verified"}
    )

    if not userExists:
        raise http_exception.ResourceNotFoundException(
            detail="User not found. Please register first."
        )

    if userExists["is_verified"]:
        raise http_exception.AlreadyVerifiedException(detail="Email is already verified.")

    verified_token = await verify_email_access_token(token)
    # Verify the token
    if not verified_token:
        raise http_exception.CredentialsInvalidException(
            detail="Invalid email verification token. Please request a new one."
        )

    if verified_token.user_id != email:
        raise http_exception.CredentialsInvalidException(
            detail="Email verification token does not match the provided email."
        )

    await user_repo.update_one(
        {"_id": userExists["_id"], "email": email},
        {"$set": {"is_verified": True, "updated_at": datetime.now()}},
    )

    return {"success": True, "message": "Email verified successfully"}


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
            raise http_exception.CredentialsInvalidException(detail="Invalid user type.")

    user_pipeline = [
        {"$match": {"_id": current_user.user_id}},
        {
            "$lookup": {
                "from": "UserSettings",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "user_settings",
            }
        },
        {
            "$unwind": {
                "path": "$user_settings",
                "preserveNullAndEmptyArrays": True,
            }
        },
        {
            "$project": {
                "password": 0,
                "updated_at": 0,
                # 'user_settings._id': 0,
                "user_settings.user_id": 0,
                "user_settings.created_at": 0,
                "user_settings.updated_at": 0,
            }
        },
    ]

    company_pipeline = [
        {"$match": {"user_id": current_user.user_id, "is_deleted": False}},
        {
            "$lookup": {
                "from": "CompanySettings",
                "localField": "_id",
                "foreignField": "company_id",
                "as": "company_settings",
            }
        },
        {"$unwind": {"path": "$company_settings", "preserveNullAndEmptyArrays": True}},
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
                "company_settings": 1,
            },
        },
    ]

    response = await user_repo.collection.aggregate(pipeline=user_pipeline).to_list(None)
    if not response:
        raise http_exception.ResourceNotFoundException(detail="Can't find user")

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


# Endpoint to delete the user data completely
@auth.delete(
    "/delete/user/company/{company_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_user_company(
    request: Request,
    response: Response,
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    user_settings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if user_settings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    if current_user.current_company_id != company_id:
        raise http_exception.ResourceNotFoundException(
            detail="First switch to the company you want to delete."
        )

    voucher_docs = await vouchar_repo.findMany({"company_id": company_id})
    voucher_ids = [doc["_id"] for doc in voucher_docs]

    # Delete related data
    await asyncio.gather(
        accounting_repo.deleteAll({"vouchar_id": {"$in": voucher_ids}}),
        inventory_repo.deleteAll({"vouchar_id": {"$in": voucher_ids}}),
        vouchar_repo.deleteAll(
            {"company_id": company_id, "user_id": current_user.user_id}
        ),
        accounting_group_repo.deleteAll(
            {"company_id": company_id, "user_id": current_user.user_id}
        ),
        category_repo.deleteAll(
            {"company_id": company_id, "user_id": current_user.user_id}
        ),
        vouchar_counter_repo.deleteAll(
            {"company_id": company_id, "user_id": current_user.user_id}
        ),
        vouchar_type_repo.deleteAll(
            {"company_id": company_id, "user_id": current_user.user_id}
        ),
        inventory_group_repo.deleteAll(
            {"company_id": company_id, "user_id": current_user.user_id}
        ),
        ledger_repo.deleteAll(
            {"company_id": company_id, "user_id": current_user.user_id}
        ),
        stock_item_repo.deleteAll(
            {"company_id": company_id, "user_id": current_user.user_id}
        ),
        units_repo.deleteAll({"company_id": company_id, "user_id": current_user.user_id}),
        company_settings_repo.deleteAll(
            {"company_id": company_id, "user_id": current_user.user_id}
        ),
    )

    # Delete the company
    await company_repo.deleteOne({"_id": company_id, "user_id": current_user.user_id})

    # Find fallback company
    remaining_companies = await company_repo.collection.aggregate(
        [
            {"$match": {"user_id": current_user.user_id, "is_deleted": False}},
        ]
    ).to_list(None)

    fallback_company = remaining_companies[0] if remaining_companies else None

    if fallback_company:
        if user_settings["current_company_id"] == company_id:
            # Update user_settings with fallback company
            await user_settings_repo.update_one(
                {"user_id": current_user.user_id},
                {
                    "$set": {
                        "current_company_id": fallback_company["_id"],
                        "current_company_name": fallback_company["company_name"],
                    }
                },
            )

    else:
        # No fallback, clear user_settings
        await user_settings_repo.update_one(
            {"user_id": current_user.user_id},
            {
                "$set": {
                    "current_company_id": "",
                    "current_company_name": "",
                }
            },
        )

    client_info = classify_client(request.headers.get("user-agent", "unknown"))

    new_token_data = TokenData(
        user_id=current_user.user_id,
        user_type=current_user.user_type,
        scope=current_user.scope,
        current_company_id=str(fallback_company["_id"]) if fallback_company else None,
        device_type=client_info.get("device_type"),
    )

    token_pair = await create_access_token(
        new_token_data, device_type=client_info.get("device_type")
    )

    set_cookies(response, token_pair.access_token, token_pair.refresh_token)

    return {
        "success": True,
        "accessToken": token_pair.access_token,
        "refreshToken": token_pair.refresh_token,
        "company_id": fallback_company["_id"] if fallback_company else None,
        "message": (
            "Company and all associated data deleted successfully. Switched to fallback company."
            if fallback_company
            else "Company deleted. No fallback company available."
        ),
    }


# Endpoint to delete the user data completely
@auth.delete(
    "/delete/user",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_user(
    response: Response,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    user_settings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if user_settings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )
    user = await user_repo.findOne({"_id": current_user.user_id})

    if user is None:
        raise http_exception.ResourceNotFoundException(
            detail="Can't find User. Aborting deletion."
        )

    voucher_docs = await vouchar_repo.findMany({"user_id": current_user.user_id})
    voucher_ids = [doc["_id"] for doc in voucher_docs]

    # Delete related data
    await asyncio.gather(
        accounting_repo.deleteAll({"vouchar_id": {"$in": voucher_ids}}),
        inventory_repo.deleteAll({"vouchar_id": {"$in": voucher_ids}}),
        vouchar_repo.deleteAll({"user_id": current_user.user_id}),
        accounting_group_repo.deleteAll({"user_id": current_user.user_id}),
        category_repo.deleteAll({"user_id": current_user.user_id}),
        vouchar_counter_repo.deleteAll({"user_id": current_user.user_id}),
        vouchar_type_repo.deleteAll({"user_id": current_user.user_id}),
        inventory_group_repo.deleteAll({"user_id": current_user.user_id}),
        ledger_repo.deleteAll({"user_id": current_user.user_id}),
        stock_item_repo.deleteAll({"user_id": current_user.user_id}),
        units_repo.deleteAll({"user_id": current_user.user_id}),
        company_settings_repo.deleteAll({"user_id": current_user.user_id}),
        company_repo.deleteAll({"user_id": current_user.user_id}),
    )
    # Delete the user settings
    await user_settings_repo.deleteOne({"user_id": current_user.user_id})

    # Delete the refresh tokens associated with the user

    # Delete the user
    await user_repo.deleteOne({"_id": current_user.user_id})
    await refresh_token_repo.deleteAll({"user_id": current_user.user_id})
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
    response.set_cookie(
        key="current_company_id",
        value="",
        httponly=True,
        max_age=0,
        secure=True,
        samesite="none",
    )
    return {
        "success": True,
        "message": "User and all associated data deleted successfully",
    }


@auth.post("/refresh", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def token_refresh(
    response: Response, refresh_token: str = Depends(get_refresh_token)
):
    token_generated = await get_new_access_token(refresh_token)
    set_cookies(response, token_generated.access_token, token_generated.refresh_token)
    return {"ok": True}


@auth.get("/app-version", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def app_version():
    """Endpoint to get the app version."""
    return {
        "success": True,
        "message": "App version fetched successfully",
        "latest_version": "3.0",
        "minimum_version": "3.1.0",
    }


@auth.post("/logout", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str = Depends(get_refresh_token),
):
    client_info = classify_client(request.headers.get("user-agent", "unknown"))

    if client_info.get("device_type") in ["Unknown", "Bot"]:
        raise http_exception.UnknownDeviceException(
            detail="Try accessing via another device. This device is compromised or not supported."
        )

    await refresh_token_repo.deleteOne(
        {
            "refresh_token": refresh_token,
            "device_type": client_info.get("device_type"),
        }
    )

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
    response.set_cookie(
        key="current_company_id",
        value="",
        httponly=True,
        max_age=0,
        secure=True,
        samesite="none",
    )
    return {"ok": True}


# @auth.post("/send/otp", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
# async def send_otp(response: Response, data: OTPdata):
#     otp = await generatePassword.createPassword()  # Generate OTP
#     # Store OTP in DB/cache with phone_number
#     otp_data = OTP(
#         phone_number=data.phone_number,
#         otp=otp,
#         user_type=UserTypeEnum.USER,
#     )
#     await otp_repo.new(otp_data)
#     mail.send(
#         "Welcome to Vyapar Drishti",
#         data.email,
#         template.Onboard(role="user", email=data.email, password=otp),
#     )
#     res = await send_whatsapp_message(otp, data.phone_number)
#     print("WhatsApp response:", res)
#     return {"ok": True, "message": "OTP sent"}


@auth.post(
    "/send/email/query", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def send_email_query(
    email_query: EmailQuery,
):
    queryId = await generatePassword.createPassword()
    mail.send(
        "New Query from Vyapar Drishti Website",
        ENV_PROJECT.EMAIL_ADDRESS,
        template.QueryEmail(
            firstName=email_query.firstName,
            lastName=email_query.lastName,
            email=email_query.email,
            phone=email_query.phone,
            companyName=email_query.company,
            industry=email_query.industry,
            companySize=email_query.employees,
            message=email_query.message,
            queryId=queryId.capitalize(),
            queryType=email_query.queryType,
            time=email_query.time,
        ),
    )
    return {"success": True, "message": "Query email sent successfully"}


@auth.post(
    "/forgot/password/{email}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def forgot_password(request: Request, email: str):
    """Endpoint to initiate the forgot password process."""
    # Check if the user exists
    userExists = await user_repo.findOne(
        {"email": email}, {"_id", "email", "user_type", "name"}
    )
    if not userExists:
        raise http_exception.ResourceNotFoundException(
            detail="Can't find user with this email"
        )

    user_settings = await user_settings_repo.findOne({"user_id": userExists["_id"]})
    if not user_settings:
        raise http_exception.ResourceNotFoundException(
            detail="User settings not found. Please contact support."
        )

    client_info = classify_client(request.headers.get("user-agent", "unknown"))

    if client_info.get("device_type") in ["Unknown", "Bot"]:
        raise http_exception.UnknownDeviceException(
            detail="Try accessing via another device. This device is compromised or not supported."
        )

    token_data = TokenData(
        user_id=userExists["_id"],
        user_type=userExists["user_type"],
        scope="forgot_password",
        device_type=client_info.get("device_type"),
    )

    token_generated = await create_forgot_password_access_token(token_data)

    forgot_password_link = f"{ENV_PROJECT.FRONTEND_DOMAIN}/reset-password?token={token_generated}&email={userExists['email']}"

    mail.send(
        "Password Reset Request",
        userExists["email"],
        template.ForgotPassword(link=forgot_password_link, agenda="forgot_password"),
    )
    return {
        "success": True,
        "message": "Password reset email sent successfully.",
        "link": forgot_password_link,
    }


@auth.post(
    "/reset/password", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def reset_password(request: Request, response: Response, data: ResetPassword):
    """Reset password endpoint."""
    # Check if the user exists
    userExists = await user_repo.findOne(
        {"email": data.email}, {"_id", "email", "user_type", "name"}
    )

    if not userExists:
        raise http_exception.ResourceNotFoundException(
            detail="Can't find user with this email"
        )

    user_settings = await user_settings_repo.findOne({"user_id": userExists["_id"]})
    if not user_settings:
        raise http_exception.ResourceNotFoundException(
            detail="User settings not found. Please contact support."
        )

    # Verify the token
    if not verify_forgot_password_access_token(data.token):
        raise http_exception.CredentialsInvalidException(
            detail="Invalid forgot password token. Please request a new one."
        )

    # Hash the new password
    hashed_password = hash_password(password=data.new_password)

    if not hashed_password:
        raise http_exception.CredentialsInvalidException(
            detail="Failed to hash the new password. Please try again."
        )

    await user_repo.update_one(
        {"_id": userExists["_id"], "email": data.email},
        {"$set": {"password": hashed_password}},
    )

    company_id = user_settings.get("current_company_id") if user_settings else None
    client_info = classify_client(request.headers.get("user-agent", "unknown"))

    if client_info.get("device_type") in ["Unknown", "Bot"]:
        raise http_exception.UnknownDeviceException(
            detail="Try accessing via another device. This device is compromised or not supported."
        )

    # Check if the user is logged in from the same device type
    existing_token = await refresh_token_repo.findOne(
        {
            "user_id": userExists["_id"],
            "user_type": userExists["user_type"],
            "device_type": client_info.get("device_type"),
        }
    )

    if existing_token:
        await refresh_token_repo.update_one(
            {
                "user_id": userExists["_id"],
                "user_type": userExists["user_type"],
                "device_type": client_info.get("device_type"),
            },
            {"$inc": {"token_version": 1}},
        )
        db_token = await refresh_token_repo.findOne(
            {
                "user_id": userExists["_id"],
                "user_type": userExists["user_type"],
                "device_type": client_info.get("device_type"),
            },
        )

        new_token_version = db_token.get("token_version", 1)
        token_data = TokenData(
            user_id=userExists["_id"],
            user_type=userExists["user_type"],
            scope="login",
            current_company_id=company_id,  # ✅ include this
            device_type=client_info.get("device_type"),
            token_version=new_token_version,  # Use updated token_version
        )

        token_generated = await create_access_token(
            token_data,
            device_type=client_info.get("device_type"),
            old_refresh_token=None,
        )

        set_cookies(response, token_generated.access_token, token_generated.refresh_token)

        await user_settings_repo.update_one(
            {"user_id": userExists["_id"]},
            {
                "$set": {
                    "last_login": datetime.now(),
                    "last_login_ip": request.client.host,
                    "last_login_device": client_info.get("info"),
                }
            },
        )
        return {
            "success": True,
            "accessToken": token_generated.access_token,
            "refreshToken": token_generated.refresh_token,
            "message": "Password changed successfully",
        }

    else:
        token_version = 1
        token_data = TokenData(
            user_id=userExists["_id"],
            user_type=userExists["user_type"],
            scope="login",
            current_company_id=company_id,  # ✅ include this
            device_type=client_info.get("device_type"),
            token_version=token_version,  # Use updated token_version
        )
        token_generated = await create_access_token(
            token_data,
            device_type=client_info.get("device_type"),
            old_refresh_token=None,
        )
        set_cookies(response, token_generated.access_token, token_generated.refresh_token)

        await user_settings_repo.update_one(
            {"user_id": userExists["_id"]},
            {
                "$set": {
                    "last_login": datetime.now(),
                    "last_login_ip": request.client.host,
                    "last_login_device": client_info.get("info"),
                }
            },
        )
        return {
            "success": True,
            "accessToken": token_generated.access_token,
            "refreshToken": token_generated.refresh_token,
            "message": "Password changed successfully",
        }
