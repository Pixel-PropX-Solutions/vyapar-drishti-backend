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


Product = APIRouter()


@Product.post(
    "/create/product", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def create_product(
    name: str = Form(...),
    company_id: str= Form(...),
    unit: str = Form(None),
    is_deleted: bool = False,

    # optional fields
    alias_name: Optional[str] = "",
    category: Optional[str] = "",
    group: Optional[str] = "",
    image: Optional[str] = "",
    description: Optional[str] = "",

    # Additonal Optional fields
    opening_balance: Optional[float] = 0,
    opening_rate: Optional[float] = 0,
    opening_value: Optional[float] = 0,
    gst_nature_of_goods: Optional[str] = "",
    gst_hsn_code: Optional[str] = "",
    gst_taxability: Optional[str] = "",
    low_stock_alert: Optional[int] = 0,

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

    product_data = {
        # required fields
        "name": name,
        "company_id": company_id,
        "unit": unit,
        "is_deleted": is_deleted,
        "user_id": current_user.user_id,
        
        # optional fields
        "alias_name": alias_name,
        "category": category,
        "group": group,
        "image": image_url,
        "description": description,
        
        # additonal optional fields
        "opening_balance": opening_balance,
        "opening_rate": opening_rate,
        "opening_value": opening_value,
        "gst_nature_of_goods": gst_nature_of_goods,
        "gst_hsn_code": gst_hsn_code,
        "gst_taxability": gst_taxability,
        "low_stock_alert": low_stock_alert,
    }

    response = await stock_item_repo.new(StockItem(**product_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Product Already Exists"
        )

    return {"success": True, "message": "Product Created Successfully"}


@Product.get(
    "/get/product/{product_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def get_product(
    product_id: str,
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    product = await stock_item_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": product_id,
                    "user_id": current_user.user_id,
                    'company_id': company_id,
                    "is_deleted": False,
                }
            },
            {
                "$lookup": {
                    "from": "Category",
                    "localField": "_category",
                    "foreignField": "_id",
                    "as": "category",
                }
            },
            {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Group",
                    "localField": "_group",
                    "foreignField": "_id",
                    "as": "group",
                }
            },
            {"$unwind": {"path": "$group", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "company_id": 1,
                    "user_id": 1,
                    "unit": 1,
                    "_unit": 1,
                    "is_deleted": 1,
                    
                    # optional fields
                    "alias_name": 1,
                    "category": {"$ifNull": ["$category.name", None]},
                    "_category": {"$ifNull": ["$category._id", None]},
                    "category_desc": {"$ifNull": ["$category.description", None]},
                    "group": {"$ifNull": ["$group.name", None]},
                    "_group": {"$ifNull": ["$group._id", None]},
                    "group_desc": {"$ifNull": ["$group.description", None]},
                    "image": 1,
                    "description": 1,
                    
                    # additional optional fields
                    "opening_balance": 1,
                    "opening_rate": 1,
                    "opening_value": 1,
                    "gst_nature_of_goods": 1,
                    "gst_hsn_code": 1,
                    "gst_taxability": 1,
                    "low_stock_alert": 1,
                    "created_at": 1,
                    "updated_at": 1,
                }
            },
        ]
    ).to_list(None)

    if not product:
        raise http_exception

    return {"success": True, "data": product}


@Product.get(
    "/view/all/product", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_product(
    current_user: TokenData = Depends(get_current_user),
    company_id: str = Query(...),
    search: str = None,
    category: str = None,
    group: str = None,
    is_deleted: bool = False,
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

    result = await stock_item_repo.viewAllProduct(
        search=search,
        company_id=company_id,
        category=category,
        pagination=page_request,
        group=group,
        sort=sort,
        current_user=current_user,
        is_deleted=is_deleted,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@Product.get(
    "/view/products/with_id",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def get_products(
    search: str = "",
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    products = await stock_item_repo.collection.aggregate(
        [
            {
                "$match": {
                    "name": {"$regex": search, "$options": "i"},
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "company_id": 1,
                    "user_id": 1,
                    "unit": 1,
                    "_unit": 1,
                    "is_deleted": 1,
                    
                    # optional fields
                    "alias_name": 1,
                    "category": {"$ifNull": ["$category.name", None]},
                    "_category": {"$ifNull": ["$category._id", None]},
                    "group": {"$ifNull": ["$group.name", None]},
                    "_group": {"$ifNull": ["$group._id", None]},
                    "image": 1,
                    "description": 1,
                }
            },
        ]
    ).to_list(None)
    return {"success": True, "data": products}


@Product.put(
    "/update/product/{product_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def update_product(
    product_id: str = "",
    unit: str = Form(None),
    barcode: str = Form(None),
    category: str = Form(None),
    hsn_code: str = Form(None),
    product_name: str = Form(...),
    description: str = Form(None),
    image: UploadFile = File(None),
    selling_price: float = Form(...),
    low_stock_alert: int = Form(None),
    purchase_price: float = Form(None),
    opening_quantity: int = Form(None),
    show_active_stock: bool = Form(True),
    opening_stock_value: int = Form(None),
    opening_purchase_price: float = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    productExists = await stock_item_repo.findOne(
        {"_id": product_id, "user_id": current_user.user_id, "is_deleted": False},
    )
    if productExists is None:
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
        "unit": unit,
        "barcode": barcode,
        "is_deleted": False,
        "hsn_code": hsn_code,
        "category": category,
        "description": description,
        "product_name": product_name,
        "selling_price": selling_price,
        "purchase_price": purchase_price,
        "low_stock_alert": low_stock_alert,
        "opening_quantity": opening_quantity,
        "show_active_stock": show_active_stock,
        "opening_stock_value": opening_stock_value,
        "opening_purchase_price": opening_purchase_price,
    }
    if image:
        update_fields["image"] = image_url

    await stock_item_repo.update_one(
        {"_id": product_id, "user_id": current_user.user_id, "is_deleted": False},
        {"$set": update_fields},
    )

    return {
        "success": True,
        "message": "Product Updated Successfully",
    }


@Product.delete(
    "/delete/product/{product_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_product(
    product_id: str,
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    product = await stock_item_repo.findOne(
        {"_id": product_id, "user_id": current_user.user_id, "is_deleted": False, "company_id": company_id}
    )

    if not product:
        raise http_exception.NotFoundException(detail="Product Not Found")

    response = await stock_item_repo.update_one(
        {"_id": product_id, "user_id": current_user.user_id, "is_deleted": False, "company_id": company_id},
        {"$set": {"is_deleted": True}},
    )


    return {"success": True, "message": "Product Deleted Successfully"}


@Product.put(
    "/restore/product/{product_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def restore_product(
    product_id: str,
    company_id: str = Query(...),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    product = await stock_item_repo.findOne(
        {"_id": product_id, "user_id": current_user.user_id, "is_deleted": True, "company_id": company_id}
    )

    if not product:
        raise http_exception.NotFoundException(detail="Product Not Found")

    await stock_item_repo.update_one(
        {"_id": product_id, "user_id": current_user.user_id, "is_deleted": True, "company_id": company_id},
        {"$set": {"is_deleted": False}},
    )

    return {"success": True, "message": "Product Restored Successfully"}
