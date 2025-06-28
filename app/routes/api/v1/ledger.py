from typing import Optional
from fastapi import FastAPI, status, Depends, File, UploadFile, Form
from fastapi.responses import ORJSONResponse
from fastapi import APIRouter
from app.schema.token import TokenData
from app.oauth2 import get_current_user
import app.http_exception as http_exception
from app.database.models.Ledger import Ledger, LedgerDB
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest
from fastapi import Query
from app.database.repositories.ledgerRepo import ledger_repo
from app.utils.cloudinary_client import cloudinary_client
import sys


ledger = APIRouter()


@ledger.post("/create", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def create_ledger(
    company_id: str = Form(...),
    parent: str = Form(...),  # Group in which the ledger (e.g."Sales Accounts")
    parent_id: str = Form(...),  # Group ID in which the ledger (e.g."Sales Accounts")
    name: str = Form(...),
    email: str = Form(""),
    number: str = Form(""),
    code: str = Form(""),
    image: UploadFile = File(None),
    alias: str = Form(None),
    is_revenue: bool = Form(False),
    is_deemed_positive: bool = Form(False),  # Indicates and Controls Debit/Credit nature
    opening_balance: float = Form(
        0.0
    ),  # Opening balance for the ledger, can be positive or negative, Amount if ledger is not zeroed
    mailing_name: str = Form(None),
    mailing_address: str = Form(None),
    mailing_state: str = Form(None),
    mailing_country: str = Form(None),
    mailing_pincode: str = Form(None),
    it_pan: str = Form(None),
    gstin: str = Form(None),
    # gst_registration_type: str = Form(None),
    # gst_supply_type: str = Form(None),
    # gst_duty_head: str = Form(None),
    # tax_rate: float = Form(0.0),
    bank_account_holder: str = Form(None),
    bank_account_number: str = Form(None),
    bank_ifsc: str = Form(None),
    # bank_swift:str = Form(None),
    bank_name: str = Form(None),
    bank_branch: str = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    ledgerExists = await ledger_repo.findOne(
        {
            "ledger_name": name,
            "user_id": current_user.user_id,
            "company_id": company_id,
        }
    )

    if ledgerExists is not None:
        raise http_exception.ResourceConflictException(
            message="Ledger with this name already exists."
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

    phone_data = None
    if code is not None or number is not None:
        phone_data = {"code": code, "number": number}

    ledger_data = {
        "ledger_name": name,
        "user_id": current_user.user_id,
        "company_id": company_id,
        "is_deleted": False,
        "phone": phone_data,
        "email": email,
        "parent": parent,  # Assuming parent_id is the same as parent for now
        "parent_id": parent_id,  # This is the name or id of the parent Ledger for internal reference
        "alias": alias,
        "is_revenue": is_revenue,
        "is_deemed_positive": is_deemed_positive,  # Indicates and Controls Debit/Credit nature
        "opening_balance": opening_balance,
        "image": image_url,
        "mailing_name": mailing_name,
        "mailing_address": mailing_address,
        "mailing_state": mailing_state,
        "mailing_country": mailing_country,
        "mailing_pincode": mailing_pincode,
        "it_pan": it_pan,
        "gstin": gstin,
        # "gst_registration_type": gst_registration_type,
        # "gst_supply_type": gst_supply_type,
        # "gst_duty_head": gst_duty_head,
        # "tax_rate": tax_rate,
        "account_holder": bank_account_holder,
        "account_number": bank_account_number,
        "bank_ifsc": bank_ifsc,
        # "bank_swift": bank_swift,
        "bank_name": bank_name,
        "bank_branch": bank_branch,
    }

    response = await ledger_repo.new(Ledger(**ledger_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Creditor Already Exists"
        )

    return {"success": True, "message": "Ledger Created Successfully"}


@ledger.get("/view/all", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def view_all_ledger(
    current_user: TokenData = Depends(get_current_user),
    search: str = None,
    state: str = Query(None),
    parent: str = Query(None),
    company_id: str = Query(None),
    is_deleted: bool = False,
    limit: int = Query(10, le=sys.maxsize),
    # limit: int = Query(10, le=INT_MAX_VALUE),
    page_no: int = Query(1, ge=1),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await ledger_repo.viewAllledgers(
        search=search,
        state=state,
        parent=parent,
        company_id=company_id,
        is_deleted=is_deleted,
        current_user_id=current_user.user_id,
        pagination=page_request,
        sort=sort,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@ledger.get(
    "/view/all/ledgers", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_ledgers(
    company_id: str = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    result = await ledger_repo.collection.aggregate(
        [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "company_id": company_id,
                    "is_deleted": False,
                },
            },
            {
                "$project": {"_id": 1, "ledger_name": 1, "parent": 1, "alias": 1},
            },
        ]
    ).to_list(None)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@ledger.get(
    "/view/ledgers/with/type",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_ledgers_with_type(
    type: str,
    company_id: str = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    print(f"Type: {type}, Company ID: {company_id}")
    
    result = await ledger_repo.collection.aggregate(
        [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "company_id": company_id,
                    "parent": type,
                    "is_deleted": False,
                },
            },
            {
                "$project": {"_id": 1, "ledger_name": 1, "parent": 1, "alias": 1},
            },
        ]
    ).to_list(None)
    
    print(f"Result: {result}")

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


# @creditor.get("/view/{creditor_id}", response_class=ORJSONResponse)
# async def view_creditor(
#     current_user: TokenData = Depends(get_current_user), creditor_id: str = ""
# ):
#     if current_user.user_type != "admin" and current_user.user_type != "user":
#         raise http_exception.CredentialsInvalidException()

#     creditorExists = await creditor_repo.findOne(
#         {"_id": creditor_id, "user_id": current_user.user_id, "is_deleted": False}
#     )

#     if creditorExists is None:
#         raise http_exception.ResourceNotFoundException()

#     pipeline = [
#         {
#             "$match": {
#                 "_id": creditor_id,
#                 "user_id": current_user.user_id,
#                 "is_deleted": False,
#             }
#         },
#         {
#             "$lookup": {
#                 "from": "Billing",
#                 "localField": "billing",
#                 "foreignField": "_id",
#                 "as": "billing",
#             }
#         },
#         {"$unwind": {"path": "$billing", "preserveNullAndEmptyArrays": True}},
#         {
#             "$lookup": {
#                 "from": "Shipping",
#                 "localField": "shipping",
#                 "foreignField": "_id",
#                 "as": "shipping",
#             }
#         },
#         {"$unwind": {"path": "$shipping", "preserveNullAndEmptyArrays": True}},
#         {
#             "$project": {
#                 "billing.user_id": 0,
#                 "shipping.user_id": 0,
#             }
#         },
#     ]

#     response = await creditor_repo.collection.aggregate(pipeline=pipeline).to_list(None)

#     return {
#         "success": True,
#         "message": "Creditor Profile Fetched Successfully",
#         "data": response,
#     }


# @creditor.put(
#     "/update/{creditor_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def update_creditor(
#     creditor_id: str = "",
#     name: str = Form(...),
#     billing: str = Form(...),
#     email: str = Form(None),
#     company_name: str = Form(None),
#     phone: str = Form(None),
#     code: str = Form(None),
#     gstin: str = Form(None),
#     # opening_balance: str = Form(None),
#     # balance_type: str = Form(None),
#     # credit_limit: str = Form(None),
#     image: UploadFile = File(None),
#     tags: str = Form(None),
#     pan_number: str = Form(None),
#     # due_date: str = Form(None),
#     shipping: str = Form(None),
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "admin" and current_user.user_type != "user":
#         raise http_exception.CredentialsInvalidException()

#     creditorExists = await creditor_repo.findOne(
#         {"_id": creditor_id, "user_id": current_user.user_id, "is_deleted": False}
#     )

#     if creditorExists is None:
#         raise http_exception.ResourceNotFoundException()

#     image_url = None
#     if image:
#         if image.content_type not in [
#             "image/jpeg",
#             "image/jpg",
#             "image/png",
#             "image/gif",
#         ]:
#             raise http_exception.BadRequestException(
#                 detail="Invalid image type. Only JPEG, JPG, PNG, and GIF are allowed."
#             )
#         if hasattr(image, "size") and image.size > 5 * 1024 * 1024:
#             raise http_exception.BadRequestException(
#                 detail="File size exceeds the 5 MB limit."
#             )
#         upload_result = await cloudinary_client.upload_file(image)
#         image_url = upload_result["url"]

#     update_fields = {
#         "name": name,
#         "billing": billing,
#         "email": email,
#         "company_name": company_name,
#         "gstin": gstin,
#         # "opening_balance": opening_balance,
#         # "balance_type": balance_type,
#         "pan_number": pan_number,
#         # "credit_limit": credit_limit,
#         "tags": tags,
#         # "due_date": due_date,
#         "shipping": shipping,
#     }

#     phone_data = None
#     if code is not None or phone is not None:
#         phone_data = {"code": code, "number": phone}
#         update_fields["phone"] = phone_data

#     if image:
#         update_fields["image"] = image_url

#     await creditor_repo.collection.update_one(
#         {"_id": creditor_id, "user_id": current_user.user_id, "is_deleted": False},
#         {"$set": update_fields},
#     )

#     return {
#         "success": True,
#         "message": "Creditor updated successfully",
#     }


# @creditor.delete(
#     "/delete/{creditor_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def delete_creditor(
#     creditor_id: str = "",
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "admin" and current_user.user_type != "user":
#         raise http_exception.CredentialsInvalidException()

#     creditorExists = await creditor_repo.findOne(
#         {"_id": creditor_id, "user_id": current_user.user_id, "is_deleted": False}
#     )

#     if creditorExists is None:
#         raise http_exception.ResourceNotFoundException()

#     await creditor_repo.collection.update_one(
#         {"_id": creditor_id, "user_id": current_user.user_id, "is_deleted": False},
#         {
#             "$set": {
#                 "is_deleted": True,
#             }
#         },
#     )

#     return {
#         "success": True,
#         "message": "Creditor deleted successfully",
#         "data": {"creditor_id": creditor_id},
#     }


# @creditor.put(
#     "/restore/{creditor_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def restore_creditor(
#     creditor_id: str = "",
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "admin" and current_user.user_type != "user":
#         raise http_exception.CredentialsInvalidException()

#     creditorExists = await creditor_repo.findOne(
#         {"_id": creditor_id, "user_id": current_user.user_id, "is_deleted": True}
#     )

#     if creditorExists is None:
#         raise http_exception.ResourceNotFoundException()

#     await creditor_repo.collection.update_one(
#         {"_id": creditor_id, "user_id": current_user.user_id, "is_deleted": True},
#         {
#             "$set": {
#                 "is_deleted": False,
#             }
#         },
#     )

#     return {
#         "success": True,
#         "message": "Creditor restored successfully",
#         "data": {"creditor_id": creditor_id},
#     }
