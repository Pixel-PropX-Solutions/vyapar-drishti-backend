from datetime import datetime
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    UploadFile,
    status,
    Request,
    Response,
)
from app.database.repositories.user import user_repo
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
import app.http_exception as http_exception
from app.routes.api.v1.userSettings import classify_client
from app.routes.api.v1.voucharCounter import initialize_voucher_counters
from app.routes.api.v1.companySettings import initialize_company_settings
from app.schema.token import TokenData
from app.oauth2 import create_access_token, get_current_user, set_cookies
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.database.repositories.ledgerRepo import ledger_repo, Ledger
from app.utils.cloudinary_client import cloudinary_client
from app.database.repositories.companyRepo import company_repo, Company
from app.database.repositories.CompanySettingsRepo import company_settings_repo
from typing import Any, Dict, Optional
from app.Config import ENV_PROJECT
from motor.motor_asyncio import AsyncIOMotorClient


user = APIRouter()

client = AsyncIOMotorClient(ENV_PROJECT.MONGO_URI)
db = client[ENV_PROJECT.MONGO_DATABASE]

ENTITY_MAP = {
    "customers": {"collection": "Ledger", "name_field": "ledger_name"},
    "creditors": {"collection": "Ledger", "name_field": "ledger_name"},
    "debtors": {"collection": "Ledger", "name_field": "ledger_name"},
    "products": {"collection": "StockItem", "name_field": "stock_item_name"},
    "invoices": {"collection": "Voucher", "name_field": "voucher_number"},
    "sales": {"collection": "Voucher", "name_field": "voucher_number"},
    "purchase": {"collection": "Voucher", "name_field": "voucher_number"},
    "payment": {"collection": "Voucher", "name_field": "voucher_number"},
    "receipt": {"collection": "Voucher", "name_field": "voucher_number"},
}


class Email_Body(BaseModel):
    email: str


@user.put(
    "/update/{user_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def update_user(
    user_id: str,
    first: str = Form(...),
    email: str = Form(...),
    last: str = Form(None),
    code: str = Form(None),
    phone: str = Form(None),
    image: UploadFile = File(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userExists = await user_repo.findOne({"_id": user_id})
    if userExists is None:
        raise http_exception.ResourceNotFoundException()

    image_url = None
    if image:
        if image.content_type not in [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
        ]:
            raise http_exception.BadRequestException(
                detail="Invalid image type. Only JPEG, JPG, PNG, and GIF are allowed."
            )
        if hasattr(image, "size") and image.size > 5 * 1024 * 1024:
            raise http_exception.BadRequestException(
                detail="File size exceeds the 5 MB limit."
            )
        upload_result = await cloudinary_client.upload_file(image)
        image_url = upload_result["url"]

    update_fields = {
        "name": {"first": first, "last": last},
        "phone": {"code": code, "number": phone},
        "email": email,
    }
    if image:
        update_fields["image"] = image_url

    res = await user_repo.update_one(
        {"_id": user_id},
        {"$set": update_fields},
    )
    if res.modified_count == 0:
        raise http_exception.ResourceNotFoundException(
            detail="Can't find user or no changes made."
        )

    if res is None:
        raise http_exception.ResourceNotFoundException(
            detail="Can't find user or no changes made."
        )
    return {
        "success": True,
        "message": "User values updated successfully",
    }


@user.post(
    "/create/company", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createCompany(
    request: Request,
    response: Response,
    name: str = Form(...),
    number: str = Form(None),
    code: str = Form(None),
    email: str = Form(None),
    tin: str = Form(None),
    website: str = Form(None),
    image: UploadFile = File(None),
    mailing_name: str = Form(None),
    address_1: str = Form(None),
    address_2: str = Form(None),
    pinCode: str = Form(None),
    state: str = Form(None),
    country: str = Form(None),
    financial_year_start: str = Form(None),
    books_begin_from: str = Form(None),
    account_holder: str = Form(None),
    account_number: str = Form(None),
    bank_ifsc: str = Form(None),
    bank_name: str = Form(None),
    bank_branch: str = Form(None),
    qr_code_url: UploadFile = File(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    user_settings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    if user_settings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    client_info = classify_client(request.headers.get("user-agent", "unknown"))
    if client_info.get("device_type") in ["Unknown", "Bot"]:
        raise http_exception.UnknownDeviceException(
            detail="Try accessing via another device. This device is compromised or not supported."
        )

    image_url = None
    if image:
        if image.content_type not in [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
        ]:
            raise http_exception.BadRequestException(
                detail="Invalid image type. Only JPEG, JPG, PNG, and GIF are allowed."
            )
        if hasattr(image, "size") and image.size > 5 * 1024 * 1024:
            raise http_exception.BadRequestException(
                detail="File size exceeds the 5 MB limit."
            )
        upload_result = await cloudinary_client.upload_file(image)
        image_url = upload_result["url"]

    # Only include phone and alter_phone if both code and number are provided
    phone_obj = None
    if code is not None and number is not None:
        phone_obj = {"code": code, "number": number}

    company_data = {
        "company_name": name,
        "user_id": current_user.user_id,
        "phone": phone_obj,
        "email": email,
        "tin": tin,
        "website": website,
        "image": image_url,
        "mailing_name": mailing_name,
        "address_1": address_1,
        "address_2": address_2,
        "pinCode": pinCode,
        "state": state,
        "country": country,
        "financial_year_start": (
            financial_year_start
            if financial_year_start
            else (
                str(datetime.today().year)
                if datetime.today().month >= 4
                else str(datetime.today().year - 1)
            )
        ),
        "books_begin_from": (
            books_begin_from
            if books_begin_from
            else (
                str(datetime.today().year)
                if datetime.today().month >= 4
                else str(datetime.today().year - 1)
            )
        ),
        "is_deleted": False,
    }

    res = await company_repo.new(Company(**company_data))

    if not res:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Company Already Exists. Please try with different company name."
        )

    if res:
        qr_url = None
        if qr_code_url:
            if qr_code_url.content_type not in [
                "image/jpeg",
                "image/jpg",
                "image/png",
                "image/gif",
            ]:
                raise http_exception.BadRequestException(
                    detail="Invalid image type. Only JPEG, JPG, PNG, and GIF are allowed."
                )
            if hasattr(qr_code_url, "size") and qr_code_url.size > 5 * 1024 * 1024:
                raise http_exception.BadRequestException(
                    detail="File size exceeds the 5 MB limit."
                )
            upload_result = await cloudinary_client.upload_file(qr_code_url)
            qr_url = upload_result["url"]

        await initialize_voucher_counters(
            user_id=current_user.user_id, company_id=res.company_id
        )

        # Initialize company settings with the provided data
        await initialize_company_settings(
            user_id=current_user.user_id,
            company_id=res.company_id,
            config={
                "company_name": name,
                "country": country,
                "state": state,
                "enable_tax": bool(tin),
                "enable_inventory": True,
                "currency": "INR",
                "financial_year": (
                    (
                        f"{datetime.today().year}-04-01"
                        if datetime.today().month >= 4
                        else f"{datetime.today().year - 1}-04-01"
                    )
                    if not books_begin_from
                    else books_begin_from
                ),
                "tin": tin,
                "tax_registration": "Regular",  # Default or can be passed
                "place_of_supply": state,  # Default or can be passed
                "bank_details": {
                    "account_holder": account_holder,
                    "account_number": account_number,
                    "bank_ifsc": bank_ifsc,
                    "bank_name": bank_name,
                    "bank_branch": bank_branch,
                    "qr_code_url": qr_url,
                },
            },
        )

        if user_settings["current_company_id"] is None:
            await user_settings_repo.update_one(
                {"user_id": current_user.user_id},
                {
                    "$set": {
                        "current_company_id": res.company_id,
                        "current_company_name": name,
                        "updated_at": datetime.now(),
                    }
                },
            )

        ledger_data = [
            {
                "ledger_name": "Purchases",
                "user_id": current_user.user_id,
                "company_id": res.company_id,
                "is_deleted": False,
                "phone": None,
                "email": None,
                "parent": "Purchase Account",
                "parent_id": "e73a4f44-f3af-4851-b36e-103da84580c1",
                "alias": None,
                "is_revenue": False,
                "is_deemed_positive": False,
                "opening_balance": 0.0,
                "image": None,
                "mailing_name": None,
                "mailing_address": None,
                "mailing_state": None,
                "mailing_country": None,
                "mailing_pincode": None,
                "tin": None,
                "account_holder": None,
                "account_number": None,
                "bank_ifsc": None,
                "bank_name": None,
                "bank_branch": None,
            },
            {
                "ledger_name": "Sales",
                "user_id": current_user.user_id,
                "company_id": res.company_id,
                "is_deleted": False,
                "phone": None,
                "email": None,
                "parent": "Sales Account",
                "parent_id": "8d96d7b3-12fc-49f5-8bbb-c416c64f3567",
                "alias": None,
                "is_revenue": True,
                "is_deemed_positive": False,
                "opening_balance": 0.0,
                "image": None,
                "mailing_name": None,
                "mailing_address": None,
                "mailing_state": None,
                "mailing_country": None,
                "mailing_pincode": None,
                "tin": None,
                "account_holder": None,
                "account_number": None,
                "bank_ifsc": None,
                "bank_name": None,
                "bank_branch": None,
            },
            {
                "ledger_name": "Cash",
                "user_id": current_user.user_id,
                "company_id": res.company_id,
                "is_deleted": False,
                "phone": None,
                "email": None,
                "parent": "Cash-in-Hand",
                "parent_id": "ab20fe9a-d267-48a0-9ccb-b8ca3335af89",
                "alias": None,
                "is_revenue": False,
                "is_deemed_positive": False,
                "opening_balance": 0.0,
                "image": None,
                "mailing_name": None,
                "mailing_address": None,
                "mailing_state": None,
                "mailing_country": None,
                "mailing_pincode": None,
                "tin": None,
                "account_holder": None,
                "account_number": None,
                "bank_ifsc": None,
                "bank_name": None,
                "bank_branch": None,
            },
            {
                "ledger_name": "Bank",
                "user_id": current_user.user_id,
                "company_id": res.company_id,
                "is_deleted": False,
                "phone": None,
                "email": None,
                "parent": "Bank Accounts",
                "parent_id": "caea08ac-37fe-4f3b-9577-a6ed78777fa3",
                "alias": None,
                "is_revenue": False,
                "is_deemed_positive": False,
                "opening_balance": 0.0,
                "image": None,
                "mailing_name": None,
                "mailing_address": None,
                "mailing_state": None,
                "mailing_country": None,
                "mailing_pincode": None,
                "tin": None,
                "account_holder": None,
                "account_number": None,
                "bank_ifsc": None,
                "bank_name": None,
                "bank_branch": None,
            },
        ]

        for ledger in ledger_data:
            await ledger_repo.new(Ledger(**ledger))

    new_token_data = TokenData(
        user_id=current_user.user_id,
        user_type=current_user.user_type,
        scope=current_user.scope,
        current_company_id=res.company_id,
        device_type=client_info.get("device_type"),
    )

    token_pair = await create_access_token(
        new_token_data, device_type=client_info.get("device_type")
    )

    set_cookies(response, token_pair.access_token, token_pair.refresh_token)

    return {
        "success": True,
        "message": "Company Created Successfully",
        "data": res.company_id,
        "accessToken": token_pair.access_token,
        "refreshToken": token_pair.refresh_token,
    }


@user.get("/all/company", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def get_all_company(
    current_user: TokenData = Depends(get_current_user),
):
    user = await user_repo.findOne({"_id": current_user.user_id})
    if user is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Not Found. Please create a User first."
        )

    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    pipeline = [
        {
            "$match": {
                "user_id": current_user.user_id,
                "is_deleted": False,
            }
        },
        {
            "$lookup": {
                "from": "CompanySettings",
                "let": {"company_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$company_id", "$$company_id"]}}}
                ],
                "as": "company_settings",
            }
        },
        {
            "$unwind": {
                "path": "$company_settings",
            }
        },
        # {
        #     "$lookup": {
        #         "from": "CompanySettings",
        #         "localField": "_id",
        #         "foreignField": "company_id",
        #         "as": "company_settings",
        #     }
        # },
        # {"$unwind": {"path": "$company_settings", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 1,
                "name": "$company_name",
                "user_id": 1,
                "mailing_name": 1,
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
                "tin": 1,
                # "is_selected": 1,
                "website": 1,
                "created_at": 1,
                "updated_at": 1,
                "bank_name": "$company_settings.bank_details.bank_name",
                "bank_ifsc": "$company_settings.bank_details.bank_ifsc",
                "bank_branch": "$company_settings.bank_details.bank_branch",
                "account_holder": "$company_settings.bank_details.account_holder",
                "account_number": "$company_settings.bank_details.account_number",
                "qr_code_url": "$company_settings.bank_details.qr_code_url",
            }
        },
    ]
    company = await company_repo.collection.aggregate(pipeline=pipeline).to_list(None)
    if company is not None:
        return {
            "success": True,
            "message": "All Companies Fetched Successfully",
            "data": company,
        }
    else:
        raise http_exception.ResourceNotFoundException(
            detail="Company Not Found. Please create a company first."
        )


@user.get("/company", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def get_company(
    # company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    user = await user_repo.findOne({"_id": current_user.user_id})
    if user is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Not Found. Please create a User first."
        )

    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    pipeline = [
        {
            "$match": {
                "user_id": current_user.user_id,
                "_id": current_user.current_company_id
                or userSettings["current_company_id"],
            }
        },
        {
            "$lookup": {
                "from": "CompanySettings",
                "let": {"company_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$company_id", "$$company_id"]}}}
                ],
                "as": "company_settings",
            }
        },
        {"$unwind": {"path": "$company_settings", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 1,
                "name": "$company_name",
                "user_id": 1,
                "mailing_name": 1,
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
                "tin": 1,
                "website": 1,
                "created_at": 1,
                "updated_at": 1,
                "bank_name": "$company_settings.bank_details.bank_name",
                "bank_ifsc": "$company_settings.bank_details.bank_ifsc",
                "bank_branch": "$company_settings.bank_details.bank_branch",
                "account_holder": "$company_settings.bank_details.account_holder",
                "account_number": "$company_settings.bank_details.account_number",
                "qr_code_url": "$company_settings.bank_details.qr_code_url",
            }
        },
    ]

    company = await company_repo.collection.aggregate(pipeline=pipeline).to_list(length=1)

    if company is None:
        raise http_exception.ResourceNotFoundException(detail="Company not Found.")

    return {
        "success": True,
        "message": "Company Fetched Successfully",
        "data": company,
    }


@user.put(
    "/update/company/{company_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateCompany(
    company_id: str,
    name: str = Form(...),
    number: str = Form(None),
    code: str = Form(None),
    email: str = Form(None),
    tin: str = Form(None),
    website: str = Form(None),
    image: UploadFile = File(None),
    mailing_name: str = Form(None),
    address_1: str = Form(None),
    address_2: str = Form(None),
    pinCode: str = Form(None),
    state: str = Form(None),
    country: str = Form(None),
    financial_year_start: str = Form(None),
    books_begin_from: str = Form(None),
    account_holder: str = Form(None),
    account_number: str = Form(None),
    bank_ifsc: str = Form(None),
    bank_name: str = Form(None),
    bank_branch: str = Form(None),
    qr_code_url: UploadFile = File(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    companyExists = await company_repo.findOne(
        {"_id": company_id, "user_id": current_user.user_id, "is_deleted": False},
    )
    if companyExists is None:
        raise http_exception.ResourceNotFoundException()

    image_url = None
    if image:
        if image.content_type not in [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
        ]:
            raise http_exception.BadRequestException(
                detail="Invalid image type. Only JPEG, JPG, PNG, and GIF are allowed."
            )
        if hasattr(image, "size") and image.size > 5 * 1024 * 1024:
            raise http_exception.BadRequestException(
                detail="File size exceeds the 5 MB limit."
            )
        upload_result = await cloudinary_client.upload_file(image)
        image_url = upload_result["url"]

    phone_obj = None
    if code is not None and number is not None:
        phone_obj = {"code": code, "number": number}

    update_fields = {
        "company_name": name,
        "phone": phone_obj,
        "email": email,
        "tin": tin,
        "website": website,
        "mailing_name": mailing_name,
        "address_1": address_1,
        "address_2": address_2,
        "pinCode": pinCode,
        "state": state,
        "country": country,
        "financial_year_start": financial_year_start,
        "books_begin_from": books_begin_from,
    }
    if image:
        update_fields["image"] = image_url

    res = await company_repo.update_one(
        {"_id": company_id, "user_id": current_user.user_id},
        {"$set": update_fields},
    )

    if res is not None:
        settings_dict = {
            "company_name": name,
            "country": country,
            "state": state,
            "currency": "INR",
            "tin": tin,
            "tax_registration_type": "Regular",  # Default or can be passed
            "place_of_supply": state,  # Default or can be passed
            "bank_details": {
                "account_holder": account_holder,
                "account_number": account_number,
                "bank_ifsc": bank_ifsc,
                "bank_name": bank_name,
                "bank_branch": bank_branch,
            },
        }

        if qr_code_url:
            if qr_code_url.content_type not in [
                "image/jpeg",
                "image/jpg",
                "image/png",
                "image/gif",
            ]:
                raise http_exception.BadRequestException(
                    detail="Invalid image type. Only JPEG, JPG, PNG, and GIF are allowed."
                )
            if hasattr(qr_code_url, "size") and qr_code_url.size > 5 * 1024 * 1024:
                raise http_exception.BadRequestException(
                    detail="File size exceeds the 5 MB limit."
                )

            upload_result = await cloudinary_client.upload_file(qr_code_url)
            settings_dict["bank_details"]["qr_code_url"] = upload_result["url"]

        await company_settings_repo.update_one(
            {"company_id": company_id, "user_id": current_user.user_id},
            {"$set": settings_dict, "$currentDate": {"updated_at": True}},
        )

    return {
        "success": True,
        "message": "Company Updated Successfully",
    }


@user.put(
    "/update/company/details/{company_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateCompanyDetails(
    company_id: str,
    company_details: Dict[str, Any] = Body(...),
    company_settings: Dict[str, Any] = Body(...),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    company = await company_repo.findOne(
        {"_id": company_id, "user_id": current_user.user_id, "is_deleted": False},
    )

    if company is None:
        raise http_exception.ResourceNotFoundException()

    updated_dict = {}
    updated_settings_dict = {}

    for k, v in dict(company_details).items():
        if v is not None:
            updated_dict[k] = v

    for k, v in dict(company_settings).items():
        if isinstance(v, str) and v not in ["", None]:
            updated_settings_dict[k] = v
        elif isinstance(v, dict):
            temp_dict = {}
            for k1, v1 in v.items():
                if isinstance(v1, str) and v1 not in ["", None]:
                    temp_dict[k1] = v1

            if temp_dict:  #
                updated_settings_dict[k] = temp_dict

    await company_repo.update_one(
        {"_id": company_id, "user_id": current_user.user_id},
        {"$set": updated_dict, "$currentDate": {"updated_at": True}},
    )
    if not updated_settings_dict:
        return {
            "success": True,
            "message": "Company Details Updated Successfully",
            "data": company,
        }

    await company_settings_repo.update_one(
        {"company_id": company_id, "user_id": current_user.user_id},
        {"$set": updated_settings_dict, "$currentDate": {"updated_at": True}},
    )

    # # Fetch the updated document after update
    # updatedCompany = await company_repo.findOne(
    #     {"_id": company_id, "user_id": current_user.user_id, "is_deleted": False},
    # )

    return {
        "success": True,
        "message": "Company Details Updated Successfully",
        # "data": updatedCompany,
    }


@user.get("/entity-name/{entity}/{id}", response_class=ORJSONResponse)
async def get_entity_name(
    entity: str, id: str, current_user: TokenData = Depends(get_current_user)
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(detail="Unauthorized access")

    if entity not in ENTITY_MAP:
        raise http_exception.ResourceNotFoundException(detail="Entity type not found")
    config = ENTITY_MAP[entity]
    collection = db[config["collection"]]
    name_field = config["name_field"]
    doc = await collection.find_one({"_id": id}, {name_field: 1})
    if not doc:
        raise http_exception.ResourceNotFoundException(detail="Entity not found")
    return {
        "success": True,
        "message": "Entity name fetched successfully",
        "data": doc.get(name_field),
    }
