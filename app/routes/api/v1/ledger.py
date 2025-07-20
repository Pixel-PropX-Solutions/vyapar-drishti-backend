from typing import Optional
from fastapi import FastAPI, status, Depends, File, UploadFile, Form
from fastapi.responses import ORJSONResponse
from fastapi import APIRouter
from app.schema.token import TokenData
from app.oauth2 import get_current_user
import app.http_exception as http_exception
from app.database.models.Ledger import Ledger
from app.database.repositories.crud.base import (
    PageRequest,
    Meta,
    PaginatedResponse,
    SortingOrder,
    Sort,
    Page,
)
from fastapi import Query
from app.database.repositories.ledgerRepo import ledger_repo
from app.database.repositories.voucharRepo import vouchar_repo
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.utils.cloudinary_client import cloudinary_client
import sys


ledger = APIRouter()


@ledger.post("/create", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def create_ledger(
    company_id: str = Form(None),
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

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    ledgerExists = await ledger_repo.findOne(
        {
            "ledger_name": name,
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
        }
    )

    if ledgerExists is not None:
        raise http_exception.ResourceConflictException(
            detail="Ledger with this name already exists."
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
        "company_id": userSettings["current_company_id"],
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

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await ledger_repo.viewAllledgers(
        search=search,
        state=state,
        parent=parent,
        company_id=userSettings["current_company_id"],
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

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    result = await ledger_repo.collection.aggregate(
        [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "company_id": userSettings["current_company_id"],
                    "is_deleted": False,
                    "parent": {"$in": ["Debtors", "Creditors"]},
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

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    result = await ledger_repo.collection.aggregate(
        [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "company_id": userSettings["current_company_id"],
                    "parent": type,
                    "is_deleted": False,
                },
            },
            {
                "$project": {"_id": 1, "ledger_name": 1, "parent": 1, "alias": 1},
            },
        ]
    ).to_list(None)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@ledger.post(
    "/view/ledgers/transaction/type",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_ledgers_transaction_type(
    type: list[str],
    company_id: str = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    result = await ledger_repo.collection.aggregate(
        [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "company_id": userSettings["current_company_id"],
                    "parent": {"$in": type},
                },
            },
            {
                "$project": {"_id": 1, "ledger_name": 1, "parent": 1},
            },
        ]
    ).to_list(None)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@ledger.put(
    "/update/{ledger_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def update_ledger(
    ledger_id: str,
    parent: str = Form(...),
    parent_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(""),
    number: str = Form(""),
    code: str = Form(""),
    image: UploadFile = File(None),
    alias: str = Form(None),
    is_revenue: bool = Form(False),
    is_deemed_positive: bool = Form(False),
    opening_balance: float = Form(0.0),
    mailing_name: str = Form(None),
    mailing_address: str = Form(None),
    mailing_state: str = Form(None),
    mailing_country: str = Form(None),
    mailing_pincode: str = Form(None),
    gstin: str = Form(None),
    # gst_registration_type: str = Form(None),
    # gst_supply_type: str = Form(None),
    # gst_duty_head: str = Form(None),
    # tax_rate: float = Form(0.0),
    bank_account_holder: str = Form(None),
    bank_account_number: str = Form(None),
    bank_ifsc: str = Form(None),
    bank_name: str = Form(None),
    bank_branch: str = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    ledgerExists = await ledger_repo.findOne(
        {
            "_id": ledger_id,
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
            "is_deleted": False,
        }
    )

    if ledgerExists is None:
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
        "ledger_name": name,
        "email": email,
        "parent": parent,
        "parent_id": parent_id,
        "alias": alias,
        "is_revenue": is_revenue,
        "is_deemed_positive": is_deemed_positive,
        "opening_balance": opening_balance,
        "mailing_name": mailing_name,
        "mailing_address": mailing_address,
        "mailing_state": mailing_state,
        "mailing_country": mailing_country,
        "mailing_pincode": mailing_pincode,
        "gstin": gstin,
        "bank_account_holder": bank_account_holder,
        "bank_account_number": bank_account_number,
        "bank_ifsc": bank_ifsc,
        "bank_name": bank_name,
        "bank_branch": bank_branch,
    }

    phone_data = None
    if code is not None or phone is not None:
        phone_data = {"code": code, "number": number}
        update_fields["phone"] = phone_data

    if image:
        update_fields["image"] = image_url

    await ledger_repo.update_one(
        {
            "_id": ledger_id,
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
            "is_deleted": False,
        },
        {"$set": update_fields},
    )

    return {
        "success": True,
        "message": "Ledger updated successfully",
    }


@ledger.get(
    "/view/{ledger_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_ledger(
    ledger_id: str,
    company_id: str = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    result = await ledger_repo.collection.aggregate(
        [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "company_id": userSettings["current_company_id"],
                    "_id": ledger_id,
                    "is_deleted": False,
                },
            },
            {
                "$lookup": {
                    "from": "Accounting",
                    "localField": "_id",
                    "foreignField": "ledger_id",
                    "as": "accounts",
                }
            },
            {
                "$addFields": {"total_amount": {"$sum": "$accounts.amount"}},
            },
            {
                "$addFields": {
                    "is_deemed_positive": {
                        "$cond": [
                            {"$lt": [{"$sum": "$accounts.amount"}, 0]},
                            True,
                            False,
                        ]
                    },
                },
            },
            {
                "$project": {
                    "id_deleted": 0,
                    "gst_registration_type": 0,
                    "gst_supply_type": 0,
                    "account_holder": 0,
                    "account_number": 0,
                    "bank_ifsc": 0,
                    "bank_name": 0,
                    "bank_branch": 0,
                    "bank_account_holder": 0,
                    "bank_account_number": 0,
                    "created_at": 0,
                    "updated_at": 0,
                    "is_revenue": 0,
                    "opening_balance": 0,
                    "image": 0,
                    "qr_image": 0,
                    "parent_id": 0,
                    "company_id": 0,
                    "user_id": 0,
                    "is_deleted": 0,
                    "mailing_name": 0,
                    "mailing_address": 0,
                    "mailing_state": 0,
                    "mailing_country": 0,
                    "mailing_pincode": 0,
                    "accounts": 0,
                },
            },
        ]
    ).to_list(length=1)

    print(f"Result: {result}")
    return {
        "success": True,
        "message": "Customer Data Fetched Successfully...",
        "data": result,
    }


@ledger.get(
    "/view/invoices/{ledger_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_ledger_invoices(
    ledger_id: str,
    company_id: str = Query(None),
    search: str = None,
    type: str = None,
    start_date: str = None,
    end_date: str = None,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=60),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await ledger_repo.get_ledger_invoices(
        search=search,
        type=type,
        ledger_id=ledger_id,
        start_date=start_date,
        end_date=end_date,
        current_user=current_user,
        pagination=page_request,
        sort=sort,
        company_id=userSettings["current_company_id"],
    )

    return {
        "success": True,
        "message": "Customer Data Fetched Successfully...",
        "data": result,
    }


# Api endpoint for checking if a user can create a ledger with a given name
@ledger.get("/check/name", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def check_ledger_name(
    ledger_name: str, current_user: TokenData = Depends(get_current_user)
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(detail="Invalid user type")

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    ledgerExists = await ledger_repo.findOne(
        {
            "ledger_name": ledger_name,
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
            "is_deleted": False,
        }
    )
    # If a ledger with the given name exists, return a conflict response with a message indicating that the ledger name is already taken and returns a array of suggested names related to the given name

    if ledgerExists is not None:
        existing_names = await ledger_repo.collection.aggregate(
            [
                {
                    "$match": {
                        "user_id": current_user.user_id,
                        "company_id": userSettings["current_company_id"],
                        "is_deleted": False,
                    }
                },
                {"$project": {"ledger_name": 1}},
            ]
        ).to_list(length=None)

        existing_names = [doc["ledger_name"] for doc in existing_names]
        existing_names = list(set(existing_names))  # Remove duplicates

        suggestions = ledger_repo.generate_name_suggestions(
            ledger_name, existing_names=existing_names, count=5
        )

        return {
            "success": False,
            "message": "Ledger with this name already exists.",
            "data": {"exists": True, "suggested_names": suggestions},
        }
    else:
        #  If no ledger exists with the given name, return success
        return {
            "success": True,
            "message": "Ledger name is available.",
            "data": {"exists": False},
        }


@ledger.delete(
    "/delete/{ledger_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_ledger(
    ledger_id: str = "",
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    ledgerExists = await ledger_repo.findOne(
        {
            "_id": ledger_id,
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
        }
    )

    if ledgerExists is None:
        raise http_exception.ResourceNotFoundException(
            detail="Customer not found or already deleted."
        )

    # Check whether the ledger is associated with any voucher or transaction
    associated_voucher = await vouchar_repo.findOne(
        {
            "party_name_id": ledger_id,
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
        }
    )

    if associated_voucher:
        raise http_exception.ResourceConflictException(
            detail="Customer cannot be deleted as it is associated with existing invoices or transactions."
        )

    await ledger_repo.deleteOne(
        {
            "_id": ledger_id,
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
        },
    )

    return {
        "success": True,
        "message": "Customer deleted successfully",
    }


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
