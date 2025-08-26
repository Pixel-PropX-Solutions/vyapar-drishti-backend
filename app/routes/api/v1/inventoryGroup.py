from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from fastapi.responses import ORJSONResponse
import app.http_exception as http_exception
from app.schema.token import TokenData
from app.oauth2 import get_current_user
from app.utils.cloudinary_client import cloudinary_client
from app.database.repositories.inventoryGroupRepo import inventory_group_repo
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.database.repositories.stockItemRepo import stock_item_repo
from app.database.models.InventoryGroup import InventoryGroup
from typing import Optional
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest
from fastapi import Query
import sys


inventory_group_router = APIRouter()


@inventory_group_router.post(
    "/inventory/create/group",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def createGroup(
    inventory_group_name: str = Form(...),  # Name of the group
    company_id: str = Form(...),  # Company ID to which the group belongs
    description: Optional[str] = Form(None),  # Description of the group
    image: UploadFile = File(None),  # Optional image for the group
    # nature_of_goods: Optional[str] = Form(None),
    # hsn_code: Optional[str] = Form(None),
    # taxability: Optional[str] = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="User is not authorized to create groups."
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
        "inventory_group_name": inventory_group_name,
        "user_id": current_user.user_id,
        "company_id": current_user.current_company_id or userSettings["current_company_id"],
        "description": description,
        "image": image_url,
        # "nature_of_goods": nature_of_goods,
        # "hsn_code": hsn_code,
        # "taxability": taxability,
        "is_deleted": False,
    }

    response = await inventory_group_repo.new(InventoryGroup(**group_data))

    if not response:
        raise http_exception.ResourceConflictException(
            detail="Group Already Exists. Please try with different Group name."
        )

    return {"success": True, "message": "Group Created Successfully", "data": response}


@inventory_group_router.get(
    "/inventory/group/view/all",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_all_group(
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
    search: str = None,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=sys.maxsize),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await inventory_group_repo.viewAllGroup(
        search=search,
        company_id=current_user.current_company_id or userSettings["current_company_id"],
        current_user_id=current_user.user_id,
        pagination=page_request,
        sort=sort,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@inventory_group_router.get(
    "/inventory/view/group/{group_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_group(
    group_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    result = await inventory_group_repo.findOne(
        {
            "_id": group_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
        }
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@inventory_group_router.get(
    "/inventory/view/all/groups",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_all_groups(
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    result = await inventory_group_repo.collection.aggregate(
        [
            {
                "$match": {
                    "company_id": userSettings["current_company_id"],
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                },
            },
            {
                "$project": {
                    "_id": 1,
                    "inventory_group_name": 1,
                    "description": 1,
                }
            },
        ]
    ).to_list(None)

    ("result", result)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@inventory_group_router.put(
    "/update/group/{group_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateGroup(
    group_id: str = "",
    inventory_group_name: str = Form(...),
    company_id: str = Form(...),
    description: str = Form(None),
    image: UploadFile = File(None),
    # nature_of_goods: Optional[str] = Form(None),
    # hsn_code: Optional[str] = Form(None),
    # taxability: Optional[str] = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="User is not authorized to update groups."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    groupExists = await inventory_group_repo.findOne(
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
        "inventory_group_name": inventory_group_name,
        # "nature_of_goods": nature_of_goods,
        # "hsn_code": hsn_code,
        # "taxability": taxability,
    }
    if image:
        update_fields["image"] = image_url

    await inventory_group_repo.update_one(
        {
            "_id": group_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
            "is_deleted": False,
        },
        {"$set": update_fields},
    )

    return {
        "success": True,
        "message": "Group Updated Successfully",
    }


@inventory_group_router.delete(
    "/delete/group/{group_id}",
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

    # Check if the group exists
    groupExists = await inventory_group_repo.findOne(
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
    associated_items = await stock_item_repo.findOne(
        {
            "group_id": group_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
        }
    )

    if associated_items:
        raise http_exception.ResourceConflictException(
            detail="Group is associated with products or items."
        )

    await inventory_group_repo.deleteOne(
        {
            "_id": group_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
        },
    )

    return {"success": True, "message": "Group Deleted Successfully"}
