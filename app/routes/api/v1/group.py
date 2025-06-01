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
from app.database.repositories.groupRepo import group_repo
from app.database.models.Group import Group, GroupDB
from typing import Optional
from typing import Optional
from fastapi import FastAPI, status, Depends, File, UploadFile, Form
from fastapi.responses import ORJSONResponse
from fastapi import APIRouter
from app.schema.token import TokenData
from app.oauth2 import get_current_user
import app.http_exception as http_exception
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest
from fastapi import Query
from app.utils.cloudinary_client import cloudinary_client


group_router = APIRouter()


@group_router.post(
    "/create/group", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createGroup(
    name: str = Form(...),  # Name of the group
    company_id: str = Form(...),  # Company ID to which the group belongs
    description: Optional[str] = Form(None),  # Description of the group
    image: UploadFile = File(None),  # Optional image for the group
    parent: str = Form(None),
    primary_group: Optional[str] = Form(
        None
    ),  # Top-level system group like 'Capital Account'
    is_revenue: Optional[bool] = Form(None),  # True for income/expense groups
    is_deemedpositive: Optional[bool] = Form(None),  # Debit/Credit nature
    is_reserved: Optional[bool] = Form(None),  # True for system-reserved groups
    affects_gross_profit: Optional[bool] = Form(None),  # If affects P&L
    sort_position: Optional[int] = Form(None),
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

    group_data = {
        "name": name,
        "user_id": current_user.user_id,
        "company_id": company_id,
        "parent": parent,
        "description": description,
        "image": image_url,
        "is_deemedpositive": is_deemedpositive,
        "primary_group": primary_group,
        "is_revenue": is_revenue,
        "is_reserved": is_reserved,
        "affects_gross_profit": affects_gross_profit,
        "sort_position": sort_position,
        "_parent": parent,  # Assuming _parent is the same as parent for now
        "is_deleted": False,
    }

    response = await group_repo.new(Group(**group_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Group Already Exists. Please try with different Group name."
        )

    return {"success": True, "message": "Group Created Successfully"}


@group_router.get(
    "/view/all", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_group(
    current_user: TokenData = Depends(get_current_user),
    search: str = None,
    state: str = Query(None),
    parent: str = Query(None),
    company_id: str = Query(None),
    is_deleted: bool = False,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=20),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await group_repo.viewAllGroup(
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


@group_router.get(
    "/view/group/{group_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_group(
    group_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    result = await group_repo.findOne({"_id": group_id, "user_id": current_user.user_id})

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@group_router.get(
    "/view/all/groups", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_groups(
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    result = await group_repo.collection.aggregate(
        [
            {
                "$match": {
                    "company_id": company_id,
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                },
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "user_id": 1,
                    "company_id": 1,
                    "description": 1,
                    "primary_group": 1,
                }
            },
        ]
    ).to_list(None)

    ("result", result)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}
