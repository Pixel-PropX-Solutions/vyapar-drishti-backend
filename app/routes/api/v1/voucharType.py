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
from app.database.repositories.VoucharTypeRepo import vouchar_type_repo
from app.database.models.VoucharType import VoucherType, VoucherTypeDB
from typing import Optional
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
from app.database.repositories.voucharRepo import vouchar_repo
from app.database.repositories.accountingRepo import accounting_repo
from app.database.repositories.InventoryRepo import inventory_repo
from app.database.models.Vouchar import Voucher, VoucherDB, VoucherCreate
from app.database.models.Accounting import Accounting
from typing import Optional, List
from app.database.models.Inventory import InventoryItem
from pydantic import BaseModel
from fastapi import APIRouter, Depends, status, File, UploadFile, Form
from fastapi.responses import ORJSONResponse
import app.http_exception as http_exception
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.oauth2 import get_current_user
from fastapi import Query
from app.schema.token import TokenData
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest

from app.database.models.StockItem import StockItemCreate
from app.database.repositories.stockItemRepo import stock_item_repo
from app.database.models.StockItem import StockItem
from app.utils.cloudinary_client import cloudinary_client
from typing import Optional, Union


VoucharType = APIRouter()


class TenantID(BaseModel):
    tenant_id: Optional[str] = None
    tenant_email: Optional[str] = None


class Email_Body(BaseModel):
    email: str


@VoucharType.post(
    "/create/vouchar/type", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createVoucharType(
    name: str,
    company_id: str = None,
    parent: Optional[str] = "",
    numbering_method: Optional[str] = "",  # e.g., "Automatic", "Manual"
    is_deemedpositive: Optional[bool] = False,  # Credit/Debit direction
    affects_stock: Optional[bool] = False,  # If stock is involved
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    vouchar_type_data = {
        "vouchar_type_name": name,
        "user_id": current_user.user_id,
        "company_id": company_id,
        "parent": parent,
        "numbering_method": numbering_method,
        "is_deemedpositive": is_deemedpositive,
        "affects_stock": affects_stock,
        "_parent": parent,  # Assuming _parent is the same as parent for now
        "is_deleted": False,
    }

    response = await vouchar_type_repo.new(VoucherType(**vouchar_type_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Vouchar type Already Exists. Please try with different vouchar name."
        )

    return {"success": True, "message": "Vouchar type Created Successfully"}


@VoucharType.get(
    "/view/all/vouchar/type",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_all_vouchar_type(
    current_user: TokenData = Depends(get_current_user),
    company_id: str = Query(...),
    search: str = None,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=60),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await vouchar_type_repo.viewAllVoucharType(
        search=search,
        company_id=company_id,
        pagination=page_request,
        sort=sort,
        current_user=current_user,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@VoucharType.get(
    "/get/all/vouchar/type", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def get_all_vouchar_type(
    current_user: TokenData = Depends(get_current_user),
    company_id: str = Query(...),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    result = await vouchar_type_repo.collection.aggregate(
        [
            {
                "$match": {
                    "is_deleted": False,
                    "$or": [
                        {
                            "company_id": company_id,
                            "user_id": current_user.user_id,
                        },
                        {
                            "company_id": None,
                            "user_id": None,
                        },
                    ],
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "name": '$vouchar_type_name',
                }
            },
        ]
    ).to_list(None)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


# @user.get("/all/company", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
# async def get_all_company(
#     current_user: TokenData = Depends(get_current_user),
# ):
#     user = await user_repo.findOne({"_id": current_user.user_id})
#     if user is None:
#         raise http_exception.ResourceNotFoundException(
#             detail="User Not Found. Please create a User first."
#         )

#     if current_user.user_type != "user" and current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()

#     pipeline = [
#         {
#             "$match": {
#                 "user_id": current_user.user_id,
#                 "is_deleted": False,
#             }
#         },
#         {
#             "$project": {
#                 "_id": 1,
#                 "name": 1,
#                 "user_id": 1,
#                 "mailing_name": 1,
#                 "image": 1,
#                 "address_1": 1,
#                 "address_2": 1,
#                 "pinCode": 1,
#                 "state": 1,
#                 "country": 1,
#                 "phone": 1,
#                 "email": 1,
#                 "financial_year_start": 1,
#                 "books_begin_from": 1,
#                 "gstin": 1,
#                 "pan": 1,
#                 "website": 1,
#                 "created_at": 1,
#                 "updated_at": 1,
#             }
#         },
#     ]
#     company = await company_repo.collection.aggregate(pipeline=pipeline).to_list(None)
#     if company is not None:
#         return {
#             "success": True,
#             "message": "All Companies Fetched Successfully",
#             "data": company,
#         }
#     else:
#         raise http_exception.ResourceNotFoundException(
#             detail="Company Not Found. Please create a company first."
#         )
