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
from app.database.repositories.company import company_repo, Company, billing_repo, Billing
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
    compnay_name: str = Form(...),
    brand_name: str = Form(...),
    phone: str = Form(None),
    code: str = Form(None),
    email: str = Form(None),
    gstin: str = Form(None),
    alter_phone: str = Form(None),
    business_type: str = Form(None),
    alter_code: str = Form(None),
    website: str = Form(None),
    pan_number: str = Form(None),
    image: UploadFile = File(None),
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
        print("upload_result", upload_result)
        image_url = upload_result["url"]

    # Only include phone and alter_phone if both code and number are provided
    phone_obj = None
    if code is not None and phone is not None:
        phone_obj = {"code": code, "number": phone}
    
    alter_phone_obj = None
    if alter_code is not None and alter_phone is not None:
        alter_phone_obj = {"code": alter_code, "number": alter_phone}

    company_data = {
        "brand_name": brand_name,
        "company_name": compnay_name,
        "user_id": current_user.user_id,
        "phone": phone_obj,
        "email": email,
        "gstin": gstin,
        "pan_number": pan_number,
        "business_type": business_type,
        "website": website,
        "image": image_url,
        "alter_phone": alter_phone_obj,
    }

    print("company_data", company_data)
    response = await company_repo.new(Company(**company_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Company Already Exists. Please try with different company name."
        )

    return {"success": True, "message": "Company Created Successfully"}


@user.post(
    "/create/company/billing", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
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

    response = await billing_repo.new(Billing(**billing_data))
    print("response", response)
    await company_repo.update_one(
        {"_id": company_id, "user_id": current_user.user_id},
        {"$set": {"billing": response.billing_id}},
    )
    return {"success": True, "message": "Billing Address Created", "data": response}


@user.get("/company", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def get_company(
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
            }
        },
        {
            "$lookup": {
                "from": "Billing",
                "localField": "billing",
                "foreignField": "_id",
                "as": "billing",
            }
        },
        {"$unwind": {"path": "$billing", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "Shipping",
                "localField": "shipping",
                "foreignField": "_id",
                "as": "shipping",
            }
        },
        {"$unwind": {"path": "$shipping", "preserveNullAndEmptyArrays": True}},
        {
            "$project": {
                # "billing.user_id": 0,
                "billing.created_at": 0,
                "billing.updated_at": 0,
                # "billing.is_deleted": 0,
                # "billing.company_id": 0,
                # "shipping.user_id": 0,
                # "shipping.company_id": 0,
                # "shipping.is_deleted": 0,
                "shipping.created_at": 0,
                "shipping.updated_at": 0,
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
    company_name: str = Form(...),
    brand_name: str = Form(...),
    number: str = Form(None),
    code: str = Form(None),
    email: str = Form(None),
    gstin: str = Form(None),
    alter_number: str = Form(None),
    business_type: str = Form(None),
    alter_code: str = Form(None),
    website: str = Form(None),
    pan_number: str = Form(None),
    image: UploadFile = File(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    companyExists = await company_repo.findOne(
        {"_id": company_id, "user_id": current_user.user_id},
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

    update_fields = {
        "company_name": company_name,
        "brand_name": brand_name,
        "phone": {"code": code, "number": number},
        "alter_phone": {"code": alter_code, "number": alter_number},
        "email": email,
        "gstin": gstin,
        "pan_number": pan_number,
        "business_type": business_type,
        "website": website,
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
