from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from pydantic import BaseModel
from app.database.repositories.accountingGroupRepo import accounting_group_repo
from app.database.repositories.ledgerRepo import ledger_repo
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.database.models.AccountingGroup import AccountingGroup
from typing import Optional
from fastapi import FastAPI, status, Depends, File, UploadFile, Form
from fastapi.responses import ORJSONResponse
from app.schema.token import TokenData
from app.oauth2 import get_current_user
import app.http_exception as http_exception
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest
from fastapi import Query
from app.utils.cloudinary_client import cloudinary_client
import sys


accounting_group_router = APIRouter()


@accounting_group_router.post(
    "/accounting/create/group",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def createGroup(
    accounting_group_name: str = Form(...),  # Name of the group
    company_id: str = Form(...),  # Company ID to which the group belongs
    description: Optional[str] = Form(None),  # Description of the group
    image: UploadFile = File(None),  # Optional image for the group
    parent: str = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="User is not authorized to create a group."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
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

    group_data = {
        "accounting_group_name": accounting_group_name,
        "user_id": current_user.user_id,
        "company_id": current_user.current_company_id or userSettings["current_company_id"],
        "description": description,
        "image": image_url,
        "is_deleted": False,
        "parent": parent,
        "parent_id": parent,  # Assuming parent_id is the same as parent for now
    }

    response = await accounting_group_repo.new(AccountingGroup(**group_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Group Already Exists. Please try with different Group name."
        )

    return {"success": True, "message": "Group Created Successfully", "data": response}


@accounting_group_router.get(
    "/accounting/view/all", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_group(
    company_id: str = Query(...),
    search: str = None,
    # state: str = Query(None),
    parent: str = Query(None),
    is_deleted: bool = False,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=sys.maxsize),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(
            detail="User is not authorized to view groups."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )
    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await accounting_group_repo.viewAllGroup(
        search=search,
        # state=state,
        parent=parent,
        company_id=current_user.current_company_id or userSettings["current_company_id"],
        is_deleted=is_deleted,
        current_user_id=current_user.user_id,
        pagination=page_request,
        sort=sort,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@accounting_group_router.get(
    "/view/default/accounting/groups",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_default_accounting_group(
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(
            detail="User is not authorized to view default accounting groups."
        )

    result = await accounting_group_repo.collection.aggregate(
        [
            {
                "$match": {
                    "company_id": None,
                    "user_id": None,
                },
            },
            {
                "$project": {
                    "_id": 1,
                    "accounting_group_name": 1,
                    "description": 1,
                    "parent": 1,
                }
            },
        ]
    ).to_list(None)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@accounting_group_router.get(
    "/accounting/view/group/{group_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_group(
    group_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(
            detail="User is not authorized to view the group."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    result = await accounting_group_repo.findOne(
        {
            "_id": group_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
        }
    )

    if result is None:
        raise http_exception.ResourceNotFoundException(
            detail="Group Not Found. Please check the group ID."
        )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@accounting_group_router.get(
    "/accounting/view/all/groups",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_all_groups(
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(
            detail="User is not authorized to view all groups."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    result = await accounting_group_repo.collection.aggregate(
        [
            {
                "$match": {
                    "$or": [
                        {
                            "company_id": current_user.current_company_id or userSettings["current_company_id"],
                            "user_id": current_user.user_id,
                        },
                        {
                            "company_id": None,
                            "user_id": None,
                        },
                    ]
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "name": "$accounting_group_name",
                    "user_id": 1,
                    "company_id": 1,
                    "description": 1,
                    "parent": 1,
                }
            },
        ]
    ).to_list(None)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@accounting_group_router.put(
    "/update/accounting/group/{group_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateGroup(
    group_id: str,
    accounting_group_name: str = Form(...),  # Name of the group
    company_id: str = Form(...),  # Company ID to which the group belongs
    description: Optional[str] = Form(None),  # Description of the group
    image: UploadFile = File(None),  # Optional image for the group
    parent: str = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="User is not authorized to update the group."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    groupExists = await accounting_group_repo.findOne(
        {
            "_id": group_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
            "is_deleted": False,
        },
    )
    if groupExists is None:
        raise http_exception.ResourceNotFoundException(
            detail="Group Not Found. Please check the group ID."
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

    update_fields = {
        "is_deleted": False,
        "description": description,
        "accounting_group_name": accounting_group_name,
        "parent": parent,
        "parent_id": parent,  # Assuming parent_id is the same as parent for now
    }
    if image:
        update_fields["image"] = image_url

    await accounting_group_repo.update_one(
        {
            "_id": group_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
        },
        {"$set": update_fields},
    )

    return {
        "success": True,
        "message": "Accounting Group Updated Successfully",
    }


@accounting_group_router.delete(
    "/delete/group/${group_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def deleteGroup(
    group_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="User is not authorized to delete the group."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    # Check if the user is trying to delete a default group
    defaultGroup = await accounting_group_repo.findOne(
        {
            "_id": group_id,
            "user_id": None,
            "company_id": None,
        },
    )
    if defaultGroup is not None:
        raise http_exception.OperationNotAllowedException(
            detail="Cannot delete default group."
        )

    # Check if the group exists
    groupExists = await accounting_group_repo.findOne(
        {
            "_id": group_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
        },
    )
    if groupExists is None:
        raise http_exception.ResourceNotFoundException(
            detail="Group Not Found. Please check the group ID."
        )

    # Check if the group is associated with any transactions or entries
    associated_entries = await ledger_repo.findOne(
        {
            "parent_id": group_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
        },
    )

    if associated_entries is not None:
        raise http_exception.OperationNotAllowedException(
            detail="Cannot delete group as it is associated with existing Customers or Transactions."
        )

    await accounting_group_repo.deleteOne(
        {
            "_id": group_id,
            "user_id": current_user.user_id,
            "company_id":current_user.current_company_id or  userSettings["current_company_id"],
        },
    )

    return {"success": True, "message": "Group Deleted Successfully"}
