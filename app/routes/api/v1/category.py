from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import ORJSONResponse
import app.http_exception as http_exception
from app.oauth2 import get_current_user
from fastapi import Query
from app.schema.token import TokenData
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest

from app.database.models.Category import CategoryCreate
from app.database.repositories.categoryRepo import category_repo
from app.database.repositories.stockItemRepo import stock_item_repo
from app.database.repositories.UserSettingsRepo import user_settings_repo
import sys

from app.utils.cloudinary_client import cloudinary_client


category_router = APIRouter()


@category_router.post(
    "/create/category", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createCategory(
    category_name: str = Form(...),
    description: str = Form(None),
    image: UploadFile = File(None),
    company_id: str = Form(...),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    user_settings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if user_settings is None:
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

    category_data = {
        "category_name": category_name,
        "user_id": current_user.user_id,
        "company_id": current_user.current_company_id or user_settings["current_company_id"],
        "is_deleted": False,
        "image": image_url,
        "description": description,
    }

    response = await category_repo.new(CategoryCreate(**category_data))

    if not response:
        raise http_exception.ResourceConflictException(detail="Category Already Exists")

    return {"success": True, "message": "Category Created Successfully", "data": response}


@category_router.get(
    "/get/category",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def getCategory(
    category_id: str,
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    categories = await category_repo.findOne(
        {
            "_id": category_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
            "is_deleted": False,
        },
    )
    if not categories:
        raise http_exception.ResourceNotFoundException(detail="Category not found.")

    return {
        "success": True,
        "data": categories,
        "message": "Category Fetched Successfully",
    }


@category_router.get(
    "/view/all/category", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_category(
    company_id: str,
    search: str = None,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=sys.maxsize),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    user_settings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if user_settings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await category_repo.viewAllCategories(
        search=search,
        pagination=page_request,
        company_id=current_user.current_company_id or user_settings["current_company_id"],
        sort=sort,
        current_user=current_user,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@category_router.get(
    "/view/categories", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_categories(
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    categories = await category_repo.collection.aggregate(
        [
            {
                "$match": {
                    "company_id": current_user.current_company_id or userSettings["current_company_id"],
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                }
            },
            {
                "$project": {
                    "user_id": 0,
                    "company_id": 0,
                    "is_deleted": 0,
                    "image": 0,
                    # "description": 0,
                    "created_at": 0,
                    "updated_at": 0,
                }
            },
        ]
    ).to_list(None)

    return {
        "success": True,
        "message": "Data Fetched Successfully...",
        "data": categories,
    }


@category_router.get(
    "/view/default/category",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def view_default_category(
    company_id: str = Query(None),
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

    result = await category_repo.collection.aggregate(
        [
            {
                "$match": {
                    "company_id":current_user.current_company_id or  userSettings["current_company_id"],
                    "user_id": current_user.user_id,
                },
            },
            {
                "$project": {
                    "_id": 1,
                    "category_name": 1,
                    "description": 1,
                }
            },
        ]
    ).to_list(None)

    ("result", result)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@category_router.put(
    "/update/category/{category_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateCategory(
    category_id: str = "",
    category_name: str = Form(...),
    company_id: str = Form(...),
    description: str = Form(None),
    image: UploadFile = File(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    categoryExists = await category_repo.findOne(
        {
            "_id": category_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
            "is_deleted": False,
        },
    )
    if categoryExists is None:
        raise http_exception.ResourceNotFoundException(detail="Category not found.")

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
        "category_name": category_name,
    }
    if image:
        update_fields["image"] = image_url

    await category_repo.update_one(
        {
            "_id": category_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or userSettings["current_company_id"],
            "is_deleted": False,
        },
        {"$set": update_fields},
    )

    return {
        "success": True,
        "message": "Category Updated Successfully",
    }


@category_router.delete(
    "/delete/category/{category_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def deleteCategory(
    category_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to perform this action."
        )

    user_settings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    if user_settings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    # Check if the category exists
    category_exists = await category_repo.findOne(
        {
            "_id": category_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or user_settings["current_company_id"],
        }
    )

    if not category_exists:
        raise http_exception.ResourceNotFoundException(
            detail="Category Not Found or Already Deleted."
        )

    # Check if the category is associated with any products or items
    associated_items = await stock_item_repo.findOne(
        {
            "category_id": category_id,
            "user_id": current_user.user_id,
            "company_id":current_user.current_company_id or  user_settings["current_company_id"],
        }
    )

    if associated_items:
        raise http_exception.ResourceConflictException(
            detail="Category is associated with products or items."
        )
    # Proceed to delete the category
    await category_repo.deleteOne(
        {
            "_id": category_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id or user_settings["current_company_id"],
        },
    )

    return {"success": True, "message": "Category Deleted Successfully"}


# @category_router.put(
#     "/restore/category/${category_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def restore_category(
#     category_id: str,
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "user" and current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()

#     response = await category_repo.update_one(
#         {"_id": category_id, "user_id": current_user.user_id, "is_deleted": True},
#         {"$set": {"is_deleted": False}},
#     )

#     if not response:
#         raise http_exception.ResourceNotFoundException(detail="Category Not Found")

#     return {"success": True, "message": "Category restored Successfully"}
