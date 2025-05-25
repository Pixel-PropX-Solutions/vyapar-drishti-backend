from fastapi import APIRouter, Depends, status, File, UploadFile, Form
from fastapi.responses import ORJSONResponse
import app.http_exception as http_exception
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.oauth2 import get_current_user
from fastapi import Query
from app.schema.token import TokenData
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest

from app.database.models.Product import ProductCreate
from app.database.repositories.Product import product_repo
from app.database.models.Product import product
from app.utils.cloudinary_client import cloudinary_client


Product = APIRouter()


@Product.post(
    "/create/product", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createProduct(
    product_name: str = Form(...),
    selling_price: float = Form(...),
    unit: str = Form(None),
    hsn_code: str = Form(None),
    purchase_price: float = Form(None),
    barcode: str = Form(None),
    category: str = Form(None),
    description: str = Form(None),
    opening_quantity: int = Form(None),
    opening_purchase_price: float = Form(None),
    opening_stock_value: int = Form(None),
    low_stock_alert: int = Form(None),
    show_active_stock: bool = Form(True),
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

    product_data = {
        "product_name": product_name,
        "selling_price": selling_price,
        "user_id": current_user.user_id,
        "is_deleted": False,
        "unit": unit,
        "hsn_code": hsn_code,
        "purchase_price": purchase_price,
        "barcode": barcode,
        "category": category,
        "image": image_url,
        "description": description,
        "opening_quantity": opening_quantity,
        "opening_purchase_price": opening_purchase_price,
        "opening_stock_value": opening_stock_value,
        "low_stock_alert": low_stock_alert,
        "show_active_stock": show_active_stock,
    }

    print("product_data", product_data)
    response = await product_repo.new(product(**product_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Product Already Exists"
        )

    return {"success": True, "message": "Product Created Successfully"}


@Product.get(
    "/view/all/product", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_product(
    current_user: TokenData = Depends(get_current_user),
    search: str = None,
    category: str = None,
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

    result = await product_repo.viewAllProduct(
        search=search,
        category=category,
        pagination=page_request,
        sort=sort,
        current_user=current_user,
        is_deleted=is_deleted,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@Product.get(
    "/get/product/{product_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def getProduct(
    product_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    product = await product_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": product_id,
                    "user_id": current_user.user_id,
                }
            },
            {
                "$lookup": {
                    "from": "Category",
                    "localField": "category",
                    "foreignField": "_id",
                    "as": "categoryDetails",
                }
            },
            {"$unwind": {"path": "$categoryDetails", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 1,
                    "product_name": 1,
                    "selling_price": 1,
                    "user_id": 1,
                    "is_deleted": 1,
                    "unit": 1,
                    "hsn_code": 1,
                    "purchase_price": 1,
                    "barcode": 1,
                    "image": 1,
                    "description": 1,
                    "opening_quantity": 1,
                    "opening_purchase_price": 1,
                    "opening_stock_value": 1,
                    "low_stock_alert": 1,
                    "show_active_stock": 1,
                    "category": {"$ifNull": ["$categoryDetails.category_name", None]},
                    "category_desc": {"$ifNull": ["$categoryDetails.description", None]},
                    "created_at": 1,
                    "updated_at": 1,
                }
            },
        ]
    ).to_list(None)

    if not product:
        raise http_exception

    return {"success": True, "data": product}


@Product.delete(
    "/delete/product/{product_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def deleteProduct(
    product_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    product = await product_repo.findOne(
        {"_id": product_id, "user_id": current_user.user_id, "is_deleted": False}
    )

    print("product", product)
    if not product:
        raise http_exception.NotFoundException(detail="Product Not Found")

    response = await product_repo.update_one(
        {"_id": product_id, "user_id": current_user.user_id, "is_deleted": False},
        {"$set": {"is_deleted": True}},
    )

    print("response", response)

    return {"success": True, "message": "Product Deleted Successfully"}


@Product.put(
    "/update/product/{product_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateProduct(
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

    productExists = await product_repo.findOne(
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

    await product_repo.update_one(
        {"_id": product_id, "user_id": current_user.user_id, "is_deleted": False},
        {"$set": update_fields},
    )

    return {
        "success": True,
        "message": "Product Updated Successfully",
    }


@Product.get(
    "/view/products/with_id",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def getProducts(
    search: str = "",
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    products = await product_repo.collection.aggregate(
        [
            {
                "$match": {
                    "product_name": {"$regex": search, "$options": "i"},
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                }
            },
            {
                "$project": {
                    "storage_requirement": 0,
                    "category": 0,
                    "state": 0,
                    "expiry_date": 0,
                    "description": 0,
                    "created_at": 0,
                    "updated_at": 0,
                }
            },
        ]
    ).to_list(None)
    return {"success": True, "data": products}
