from fastapi import (
    APIRouter,
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
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.oauth2 import get_current_user
from app.schema.token import TokenData
from app.utils.cloudinary_client import cloudinary_client
from app.database.repositories.companyRepo import company_repo, Company
from typing import Optional


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
        "name": name,
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
        "financial_year_start": financial_year_start,
        "books_begin_from": books_begin_from,
        "is_deleted": False,
    }

    response = await company_repo.new(Company(**company_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Company Already Exists. Please try with different company name."
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
            "$project": {
                "_id": 1,
                "name": 1,
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
                "is_selected": 1,
                "website": 1,
                "created_at": 1,
                "updated_at": 1,
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


@user.post(
    "/create/company/billing",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def create_company_billing(
    company_id: str = Form(...),
    state: str = Form(...),
    address_1: str = Form(...),
    address_2: str = Form(None),
    pinCode: str = Form(None),
    city: str = Form(None),
    country: str = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    billing_data = {
        "user_id": current_user.user_id,
        # "company_id": company_id,
        "state": state,
        "address_1": address_1,
        "address_2": address_2,
        "pinCode": pinCode,
        "city": city,
        "country": country,
        "is_deleted": False,
    }

    # response = await billing_repo.new(Billing(**billing_data))
    await company_repo.update_one(
        {"_id": company_id, "user_id": current_user.user_id},
        {"$set": {"billing": response.billing_id}},
    )
    return {"success": True, "message": "Billing Address Created", "data": response}


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

    pipeline = [
        {
            "$match": {
                "user_id": current_user.user_id,
                "is_selected": True,
                "is_deleted": False,
            }
        },
        # {
        #     "$lookup": {
        #         "from": "Billing",
        #         "localField": "billing",
        #         "foreignField": "_id",
        #         "as": "billing",
        #     }
        # },
        # {"$unwind": {"path": "$billing", "preserveNullAndEmptyArrays": True}},
        # {
        #     "$lookup": {
        #         "from": "Shipping",
        #         "localField": "shipping",
        #         "foreignField": "_id",
        #         "as": "shipping",
        #     }
        # },
        # {"$unwind": {"path": "$shipping", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                "_id": 1,
                "name": 1,
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
                "is_selected": 1,
                "website": 1,
                "created_at": 1,
                "updated_at": 1,
            }
        },
    ]
    company = await company_repo.collection.aggregate(pipeline=pipeline).to_list(None)
    if company is not None:
        return {
            "success": True,
            "message": "Company Fetched Successfully",
            "data": company,
        }
    else:
        raise http_exception.ResourceNotFoundException(
            detail="Company Not Found. Please create a company first."
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
        "name": name,
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
    "/set/company/{company_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateCurrentCompany(
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    companyExists = await company_repo.findOne(
        {"_id": company_id, "user_id": current_user.user_id, "is_deleted": False},
    )
    
    if companyExists is None:
        raise http_exception.ResourceNotFoundException()
    
    await company_repo.update_many(
        {"user_id": current_user.user_id, "is_deleted": False},
        {"$set": {"is_selected": False}},
    )

    await company_repo.update_one(
        {"_id": company_id, "user_id": current_user.user_id},
        {"$set": {"is_selected": True}},
    )

    return {
        "success": True,
        "message": "Current Company selected Successfully",
    }
