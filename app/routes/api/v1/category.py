from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import ORJSONResponse
import app.http_exception as http_exception
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.oauth2 import get_current_user
from fastapi import Query
from app.schema.token import TokenData
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest

from app.database.models.Category import CategoryCreate
from app.database.repositories.Category import category_repo
from app.database.models.Category import category
from app.utils.cloudinary_client import cloudinary_client


Category = APIRouter()


@Category.post(
    "/create/category", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createCategory(
    category_name: str = Form(...),
    description: str = Form(None),
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

    category_data = {
        "category_name": category_name,
        "user_id": current_user.user_id,
        "is_deleted": False,
        "image": image_url,
        "description": description,
    }

    response = await category_repo.new(category(**category_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Category Already Exists"
        )

    return {"success": True, "message": "Category Created Successfully", "data": response}


@Category.get(
    "/get/category",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def getCategory(
    category_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    categories = await category_repo.findOne(
        {"_id": category_id, "user_id": current_user.user_id, "is_deleted": False},
        {"created_at": 0, "updated_at": 0},
    )
    if not categories:
        raise http_exception

    return {
        "success": True,
        "data": categories,
        "message": "Category Fetched Successfully",
    }


@Category.get(
    "/view/all/category", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_category(
    current_user: TokenData = Depends(get_current_user),
    search: str = None,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=60),
    is_deleted: bool = False,
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await category_repo.viewAllCategories(
        search=search,
        pagination=page_request,
        sort=sort,
        is_deleted=is_deleted,
        current_user=current_user,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@Category.get(
    "/view/categories", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_categories(
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    categories = await category_repo.collection.aggregate(
        [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                }
            },
            {
                "$project": {
                    "user_id": 0,
                    "is_deleted": 0,
                    "image": 0,
                    "description": 0,
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


@Category.put(
    "/update/category/{category_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateCategory(
    category_id: str = "",
    category_name: str = Form(...),
    description: str = Form(None),
    image: UploadFile = File(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    categoryExists = await category_repo.findOne(
        {"_id": category_id, "user_id": current_user.user_id, "is_deleted": False},
    )
    if categoryExists is None:
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
        "is_deleted": False,
        "description": description,
        "category_name": category_name,
    }
    if image:
        update_fields["image"] = image_url

    await category_repo.update_one(
        {"_id": category_id, "user_id": current_user.user_id, "is_deleted": False},
        {"$set": update_fields},
    )

    return {
        "success": True,
        "message": "Category Updated Successfully",
    }


@Category.delete(
    "/delete/category/${category_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def deleteCategory(
    category_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    response = await category_repo.update_one(
        {"_id": category_id, "user_id": current_user.user_id, "is_deleted": False},
        {"$set": {"is_deleted": True}},
    )

    if not response:
        raise http_exception.ResourceNotFoundException(detail="Category Not Found")

    return {"success": True, "message": "Product Deleted Successfully"}
