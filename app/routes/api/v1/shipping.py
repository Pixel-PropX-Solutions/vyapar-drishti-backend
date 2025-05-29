from fastapi import (
    APIRouter,
    Depends,
    Form,
    status,
)
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
import app.http_exception as http_exception
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.oauth2 import get_current_user
from app.database.repositories.company import shipping_repo, Shipping
from app.schema.token import TokenData
from app.database.repositories.company import company_repo
from typing import Optional


shipping = APIRouter()


class TenantID(BaseModel):
    tenant_id: Optional[str] = None
    tenant_email: Optional[str] = None


class Email_Body(BaseModel):
    email: str


@shipping.post(
    "/create/shipping", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def create_shipping(
    company_id: str = Form(...),
    state: str = Form(...),
    address_1: str = Form(...),
    address_2: str = Form(None),
    pinCode: str = Form(None),
    city: str = Form(None),
    country: str = Form(None),
    title: str = Form(None),
    notes: str = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    shipping_data = {
        "user_id": current_user.user_id,
        # "company_id": company_id,
        "state": state,
        "address_1": address_1,
        "address_2": address_2,
        "pinCode": pinCode,
        "city": city,
        "country": country,
        "title": title,
        "notes": notes,
        "is_deleted": False,
    }

    response = await shipping_repo.new(Shipping(**shipping_data))

    await company_repo.update_one(
        {"_id": company_id, "user_id": current_user.user_id},
        {"$set": {"shipping": response.shipping_id}},
    )

    return {"success": True, "message": "Shipping Address Created", "data": response}


@shipping.get(
    "/get/shipping/{shipping_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def get_shipping(
    shipping_id: str, current_user: TokenData = Depends(get_current_user)
):
    from app.database.repositories.company import shipping_repo

    shipping = await shipping_repo.findOne(
        {"_id": shipping_id, "user_id": current_user.user_id}
    )
    if not shipping:
        raise http_exception.ResourceNotFoundException(
            detail="Shipping Address Not Found"
        )
    return {"success": True, "data": shipping}


@shipping.get(
    "/get/all/shipping",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def get_all_shipping(current_user: TokenData = Depends(get_current_user)):

    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    shipping = await shipping_repo.collection.aggregate(
        [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                }
            },
            {
                "$project": {
                    "created_at": 0,
                    "updated_at": 0,
                }
            },
        ]
    ).to_list(None)

    if not shipping:
        raise http_exception.ResourceNotFoundException(
            detail="Shipping Address Not Found"
        )

    return {"success": True, "data": shipping}


@shipping.put(
    "/update/shipping/{shipping_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def update_shipping(
    shipping_id: str,
    state: str = Form(...),
    address_1: str = Form(...),
    address_2: str = Form(None),
    pinCode: str = Form(None),
    city: str = Form(None),
    country: str = Form(None),
    title: str = Form(None),
    notes: str = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    update_fields = {
        "state": state,
        "address_1": address_1,
        "address_2": address_2,
        "pinCode": pinCode,
        "city": city,
        "country": country,
        "title": title,
        "notes": notes,
    }
    await shipping_repo.update_one(
        {"_id": shipping_id, "user_id": current_user.user_id}, {"$set": update_fields}
    )
    return {"success": True, "message": "Shipping Address Updated"}


@shipping.delete(
    "/delete/shipping/{shipping_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_shipping(
    shipping_id: str, current_user: TokenData = Depends(get_current_user)
):
    shipping = await shipping_repo.findOne(
        {"_id": shipping_id, "user_id": current_user.user_id}
    )

    if not shipping:
        raise http_exception.ResourceNotFoundException(
            detail="Shipping Address Not Found"
        )

    if shipping.get("is_deleted", True):
        raise http_exception.ResourceNotFoundException(
            detail="Shipping Address Already Deleted"
        )

    await shipping_repo.update_one(
        {"_id": shipping_id, "user_id": current_user.user_id},
        {"$set": {"is_deleted": True}},
    )

    return {"success": True, "message": "Shipping Address Deleted"}


@shipping.put(
    "/restore/shipping/{shipping_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def restored_shipping(
    shipping_id: str, current_user: TokenData = Depends(get_current_user)
):
    shipping = await shipping_repo.findOne(
        {"_id": shipping_id, "user_id": current_user.user_id, "is_deleted": True}
    )

    if not shipping:
        raise http_exception.ResourceNotFoundException(
            detail="Shipping Address Not Found"
        )

    await shipping_repo.update_one(
        {"_id": shipping_id, "user_id": current_user.user_id, "is_deleted": True},
        {"$set": {"is_deleted": False}},
    )

    return {"success": True, "message": "Shipping Address Restored"}
