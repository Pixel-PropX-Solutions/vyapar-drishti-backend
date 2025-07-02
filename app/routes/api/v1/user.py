from datetime import datetime
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from app.database.repositories.user import user_repo
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
import app.http_exception as http_exception
from app.routes.api.v1.voucharCounter import initialize_voucher_counters
from app.routes.api.v1.companySettings import initialize_company_settings
from app.schema.token import TokenData
from app.oauth2 import get_current_user
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.utils.cloudinary_client import cloudinary_client
from app.database.repositories.companyRepo import company_repo, Company
from typing import Any, Dict, Optional


user = APIRouter()


class TenantID(BaseModel):
    tenant_id: Optional[str] = None
    tenant_email: Optional[str] = None


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
            detail="User not found or no changes made."
        )

    if res is None:
        raise http_exception.ResourceNotFoundException(
            detail="User not found or no changes made."
        )
    return {
        "success": True,
        "message": "User values updated successfully",
    }


@user.post(
    "/create/company", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createCompany(
    name: str = Form(...),
    number: str = Form(None),
    code: str = Form(None),
    email: str = Form(None),
    gstin: str = Form(None),
    website: str = Form(None),
    pan_number: str = Form(None),
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
        "gstin": gstin,
        "pan_number": pan_number,
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

    response = await company_repo.new(Company(**company_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Company Already Exists. Please try with different company name."
        )

    # print("Company Created Successfully", response)
    if response:
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
            user_id=current_user.user_id, company_id=response.company_id
        )

        # Initialize company settings with the provided data
        await initialize_company_settings(
            user_id=current_user.user_id,
            company_id=response.company_id,
            config={
                "company_name": name,
                "country": country,
                "state": state,
                "enable_gst": bool(gstin),
                "enable_inventory": True,
                "currency": "INR",
                "financial_year": (
                    books_begin_from
                    if books_begin_from
                    else (
                        datetime.today().year
                        if datetime.today().month >= 4
                        else datetime.today().year - 1
                    )
                ),
                "gstin": gstin,
                "gst_registration_type": "Regular",  # Default or can be passed
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

        await user_settings_repo.update_one(
            {"user_id": current_user.user_id},
            {"$set": {"current_company_id": response.company_id}},
        )

    return {"success": True, "message": "Company Created Successfully"}


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
                "localField": "_id",
                "foreignField": "company_id",
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
                "gstin": 1,
                "pan": 1,
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
    # print("User Settings:", userSettings)

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )
    # if not userSettings.current_company_id:
    pipeline = [
        {
            "$match": {
                "user_id": current_user.user_id,
                "_id": userSettings["current_company_id"],
                # "is_selected": True,
                "is_deleted": False,
            }
        },
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
                "gstin": 1,
                "pan": 1,
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
    if company:
        return {
            "success": True,
            "message": "Company Fetched Successfully",
            "data": company,
        }
    else:
        raise http_exception.ResourceNotFoundException(
            # detail="Company Not Found. Please create a company first."
        )


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
    gstin: str = Form(None),
    website: str = Form(None),
    pan_number: str = Form(None),
    image: UploadFile = File(None),
    mailing_name: str = Form(None),
    address_1: str = Form(None),
    address_2: str = Form(None),
    pinCode: str = Form(None),
    state: str = Form(None),
    country: str = Form(None),
    financial_year_start: str = Form(None),
    books_begin_from: str = Form(None),
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
        "gstin": gstin,
        "website": website,
        "pan": pan_number,
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

    await company_repo.update_one(
        {"_id": company_id, "user_id": current_user.user_id},
        {"$set": update_fields},
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

    for k, v in dict(company_details).items():
        if isinstance(v, str) and v not in ["", None]:
            updated_dict[k] = v
        elif isinstance(v, dict):
            temp_dict = {}
            for k1, v1 in v.items():
                if isinstance(v1, str) and v1 not in ["", None]:
                    temp_dict[k1] = v1

            if temp_dict:  #
                updated_dict[k] = temp_dict

    await company_repo.update_one(
        {"_id": company_id, "user_id": current_user.user_id},
        {"$set": updated_dict, "$currentDate": {"updated_at": True}},
    )

    # Fetch the updated document after update
    updatedCompany = await company_repo.findOne(
        {"_id": company_id, "user_id": current_user.user_id, "is_deleted": False},
    )

    return {
        "success": True,
        "message": "Company Details Updated Successfully",
        "data": updatedCompany,
    }


# @user.put(
#     "/set/company/{company_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def updateCurrentCompany(
#     company_id: str,
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "user" and current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()

#     companyExists = await company_repo.findOne(
#         {"_id": company_id, "user_id": current_user.user_id, "is_deleted": False},
#     )

#     if companyExists is None:
#         raise http_exception.ResourceNotFoundException()

#     await company_repo.update_many(
#         {"user_id": current_user.user_id, "is_deleted": False},
#         {"$set": {"is_selected": False}},
#     )

#     await company_repo.update_one(
#         {"_id": company_id, "user_id": current_user.user_id},
#         {"$set": {"is_selected": True}},
#     )

#     return {
#         "success": True,
#         "message": "Current Company selected Successfully",
#     }
