from fastapi import APIRouter, Depends, status, File, UploadFile, Form
from fastapi.responses import ORJSONResponse
import app.http_exception as http_exception
from app.schema.token import TokenData
from app.oauth2 import get_current_user
from fastapi import Query
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest
from app.database.models.GST_Rate import GSTRate
from app.database.repositories.gstRateRepo import gst_rate_repo
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.database.repositories.stockItemRepo import stock_item_repo
from app.database.repositories.voucharRepo import vouchar_repo
from app.database.repositories.InventoryRepo import inventory_repo
from app.database.models.StockItem import StockItem
from app.utils.cloudinary_client import cloudinary_client


Product = APIRouter()


@Product.post(
    "/create/product", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def create_product(
    stock_item_name: str = Form(...),
    company_id: str = Form(None),
    unit: str = Form(...),
    unit_id: str = Form(...),
    # optional fields
    alias_name: str = Form(None),
    category: str = Form(None),
    category_id: str = Form(None),
    group: str = Form(None),
    group_id: str = Form(None),
    image: UploadFile = File(None),
    description: str = Form(None),
    # Additonal Optional fields
    opening_balance: float = Form(None),
    opening_rate: float = Form(None),
    opening_value: float = Form(None),
    gst_nature_of_goods: str = Form(None),
    gst_hsn_code: str = Form(None),
    gst_taxability: str = Form(None),
    gst_percentage: str = Form(None),
    low_stock_alert: int = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()
    
    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
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

    product_data = {
        # required fields
        "stock_item_name": stock_item_name,
        "company_id": userSettings["current_company_id"],
        "unit": unit,
        "unit_id": unit_id,
        "is_deleted": False,
        "user_id": current_user.user_id,
        # optional fields
        "alias_name": alias_name,
        "category": category,
        "category_id": category_id,
        "group": group,
        "group_id": group_id,
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

    if response:
        gstr_data = {
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
            "item": stock_item_name,
            "item_id": response.stock_item_id,
            "hsn_code": gst_hsn_code,
            "nature_of_goods": gst_nature_of_goods,
            "taxability": gst_taxability,
            "rate": gst_percentage,
        }
        res = await gst_rate_repo.new(GSTRate(**gstr_data))

        if not res:
            raise http_exception.ResourceAlreadyExistsException(
                detail="GST Rate Already Exists for this Product"
            )

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
    
    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    product = await stock_item_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": product_id,
                    "user_id": current_user.user_id,
                    "company_id": userSettings["current_company_id"],
                    "is_deleted": False,
                }
            },
            {
                "$lookup": {
                    "from": "Category",
                    "localField": "category",
                    "foreignField": "category_name",
                    "as": "category",
                }
            },
            {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Group",
                    "localField": "group",
                    "foreignField": "inventory_group_name",
                    "as": "group",
                }
            },
            {"$unwind": {"path": "$group", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Inventory",
                    "localField": "stock_item_name",
                    "foreignField": "item",
                    "as": "inventory_entries",
                }
            },
            {
                "$unwind": {
                    "path": "$inventory_entries",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$lookup": {
                    "from": "Voucher",
                    "localField": "inventory_entries.vouchar_id",
                    "foreignField": "_id",
                    "as": "voucher",
                }
            },
            {"$unwind": {"path": "$voucher", "preserveNullAndEmptyArrays": True}},
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "stock_item_name": {"$first": "$stock_item_name"},
                    "unit": {"$first": "$unit"},
                    "category": {"$first": "$category"},
                    "alias_name": {"$first": "$alias_name"},
                    "image": {"$first": "$image"},
                    "description": {"$first": "$description"},
                    "gst_hsn_code": {"$first": "$gst_hsn_code"},
                    "group": {"$first": "$group"},
                    "voucher": {"$first": "$voucher"},
                    "purchase_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.quantity",
                                0,
                            ]
                        }
                    },
                    "purchase_value": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.amount",
                                0,
                            ]
                        }
                    },
                    "sales_qty": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.quantity"},
                                0,
                            ]
                        }
                    },
                    "sales_value": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.amount"},
                                0,
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "stock_item_name": 1,
                    "company_id": 1,
                    "user_id": 1,
                    "unit": 1,
                    "unit_id": 1,
                    "alias_name": 1,
                    "voucher": 1,
                    "category": {"$ifNull": ["$category.category_name", None]},
                    "category_id": {"$ifNull": ["$category._id", None]},
                    "group": {"$ifNull": ["$group.inventory_group_name", None]},
                    "group_id": {"$ifNull": ["$group._id", None]},
                    "image": 1,
                    "description": 1,
                    "gst_nature_of_goods": 1,
                    "gst_hsn_code": 1,
                    "gst_taxability": 1,
                    "low_stock_alert": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "current_stock": {
                        "$subtract": [
                            {"$sum": {"$ifNull": ["$purchase_qty", 0]}},
                            {"$sum": {"$ifNull": ["$sales_qty", 0]}},
                        ]
                    },
                    "avg_purchase_rate": {
                        "$cond": [
                            {"$gt": ["$purchase_qty", 0]},
                            {"$divide": ["$purchase_value", "$purchase_qty"]},
                            0,
                        ]
                    },
                    "purchase_qty": "$purchase_qty",
                    "purchase_value": "$purchase_value",
                    "sales_qty": "$sales_qty",
                    "sales_value": "$sales_value",
                }
            },
        ]
    ).to_list(None)

    if product:
        return {"success": True, "data": product}
    else:
        raise http_exception.ResourceNotFoundException()


@Product.get(
    "/get/product/details/{product_id}",
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
    
    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    product = await stock_item_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": product_id,
                    "user_id": current_user.user_id,
                    "company_id": userSettings["current_company_id"],
                    "is_deleted": False,
                }
            },
            {
                "$lookup": {
                    "from": "Category",
                    "localField": "category",
                    "foreignField": "category_name",
                    "as": "category",
                }
            },
            {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Group",
                    "localField": "group",
                    "foreignField": "inventory_group_name",
                    "as": "group",
                }
            },
            {"$unwind": {"path": "$group", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Inventory",
                    "localField": "stock_item_name",
                    "foreignField": "item",
                    "as": "inventory_entries",
                }
            },
            {
                "$unwind": {
                    "path": "$inventory_entries",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$lookup": {
                    "from": "Voucher",
                    "localField": "inventory_entries.vouchar_id",
                    "foreignField": "_id",
                    "as": "voucher",
                }
            },
            {"$unwind": {"path": "$voucher", "preserveNullAndEmptyArrays": True}},
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "stock_item_name": {"$first": "$stock_item_name"},
                    "unit": {"$first": "$unit"},
                    "category": {"$first": "$category"},
                    "alias_name": {"$first": "$alias_name"},
                    "image": {"$first": "$image"},
                    "description": {"$first": "$description"},
                    "user_id": {"$first": "$user_id"},
                    "unit_id": {"$first": "$unit_id"},
                    "category_id": {"$first": "$category_id"},
                    "group_id": {"$first": "$group_id"},
                    "gst_nature_of_goods": {"$first": "$gst_nature_of_goods"},
                    "gst_taxability": {"$first": "$gst_taxability"},
                    "low_stock_alert": {"$first": "$low_stock_alert"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                    "gst_hsn_code": {"$first": "$gst_hsn_code"},
                    "opening_balance": {"$first": "$opening_balance"},
                    "opening_rate": {"$first": "$opening_rate"},
                    "opening_value": {"$first": "$opening_value"},
                    # "gst_hsn_code": {"$first": "$gst_hsn_code"},
                    # "gst_hsn_code": {"$first": "$gst_hsn_code"},
                    # "gst_hsn_code": {"$first": "$gst_hsn_code"},
                    # "gst_hsn_code": {"$first": "$gst_hsn_code"},
                    "group": {"$first": "$group"},
                    "purchase_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.quantity",
                                0,
                            ]
                        }
                    },
                    "purchase_value": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.amount",
                                0,
                            ]
                        }
                    },
                    "sales_qty": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.quantity"},
                                0,
                            ]
                        }
                    },
                    "sales_value": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.amount"},
                                0,
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "stock_item_name": 1,
                    "company_id": 1,
                    "user_id": 1,
                    "unit": 1,
                    "unit_id": 1,
                    "alias_name": 1,
                    "category": {"$ifNull": ["$category.category_name", None]},
                    "category_id": {"$ifNull": ["$category._id", None]},
                    "group": {"$ifNull": ["$group.inventory_group_name", None]},
                    "group_id": {"$ifNull": ["$group._id", None]},
                    "image": 1,
                    "description": 1,
                    "gst_nature_of_goods": 1,
                    "gst_hsn_code": 1,
                    "gst_taxability": 1,
                    "low_stock_alert": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "current_stock": {
                        "$subtract": [
                            {"$sum": {"$ifNull": ["$purchase_qty", 0]}},
                            {"$sum": {"$ifNull": ["$sales_qty", 0]}},
                        ]
                    },
                    "avg_purchase_rate": {
                        "$cond": [
                            {"$gt": ["$purchase_qty", 0]},
                            {"$divide": ["$purchase_value", "$purchase_qty"]},
                            0,
                        ]
                    },
                    "purchase_qty": "$purchase_qty",
                    "purchase_value": "$purchase_value",
                    "sales_qty": "$sales_qty",
                    "sales_value": "$sales_value",
                    "opening_balance": 1,
                    "opening_rate": 1,
                    "opening_value": 1,
                }
            },
        ]
    ).to_list(None)

    if product:
        return {"success": True, "data": product}
    else:
        raise http_exception.ResourceNotFoundException()


@Product.get(
    "/view/all/product", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_product(
    current_user: TokenData = Depends(get_current_user),
    company_id: str = Query(None),
    search: str = None,
    category: str = None,
    group: str = None,
    # is_deleted: bool = False,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=60),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()
    
    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await stock_item_repo.viewAllProduct(
        search=search,
        company_id=userSettings["current_company_id"],
        category=category,
        pagination=page_request,
        group=group,
        sort=sort,
        current_user=current_user,
        # is_deleted=is_deleted,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@Product.get(
    "/view/all/stock/items", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_stock_items(
    current_user: TokenData = Depends(get_current_user),
    company_id: str = Query(None),
    search: str = None,
    category: str = None,
    group: str = None,
    # is_deleted: bool = False,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=60),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()
    
    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await stock_item_repo.view_all_stock_items(
        search=search,
        company_id=userSettings["current_company_id"],
        category=category,
        pagination=page_request,
        group=group,
        sort=sort,
        current_user=current_user,
        # is_deleted=is_deleted,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@Product.get(
    "/view/products/with_id",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def get_products(
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()
    
    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    products = await stock_item_repo.collection.aggregate(
        [
            {
                "$match": {
                    "company_id": userSettings["current_company_id"],
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                }
            },
            {
                "$lookup": {
                    "from": "GSTRate",
                    "localField": "_id",
                    "foreignField": "item_id",
                    "as": "gst_rate",
                }
            },
            {"$unwind": {"path": "$gst_rate", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 1,
                    "stock_item_name": 1,
                    "unit": 1,
                    "hsn_code": '$gst_rate.hsn_code',
                    "rate": '$gst_rate.rate',
                    "cgst": '$gst_rate.cgst', # CGST rate
                    "sgst": '$gst_rate.sgst', # SGST rate
                    "igst": '$gst_rate.igst', # IGST rate
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
    name: str = Form(...),
    company_id: str = Form(...),
    unit: str = Form(...),
    # optional fields
    alias_name: str = Form(None),
    category: str = Form(None),
    group: str = Form(None),
    image: UploadFile = File(None),
    description: str = Form(None),
    # Additonal Optional fields
    opening_balance: float = Form(None),
    opening_rate: float = Form(None),
    opening_value: float = Form(None),
    gst_nature_of_goods: str = Form(None),
    gst_hsn_code: str = Form(None),
    gst_taxability: str = Form(None),
    low_stock_alert: int = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()
    
    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    productExists = await stock_item_repo.findOne(
        {
            "_id": product_id,
            "user_id": current_user.user_id,
            "is_deleted": False,
            "company_id": userSettings["current_company_id"],
        },
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
        "stock_item_name": name,
        "unit": unit,
        # optional fields
        "alias_name": alias_name,
        "category": category,
        "group": group,
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
    if image:
        update_fields["image"] = image_url

    await stock_item_repo.update_one(
        {
            "_id": product_id,
            "user_id": current_user.user_id,
            "is_deleted": False,
            "company_id": userSettings["current_company_id"],
        },
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
    
    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})
    
    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    product = await stock_item_repo.findOne(
        {
            "_id": product_id,
            "user_id": current_user.user_id,
            "is_deleted": False,
            "company_id": userSettings["current_company_id"],
        }
    )

    if not product:
        raise http_exception.NotFoundException(detail="Product Not Found")

    if product:
        vouchar_id_list = await inventory_repo.findAll(
            {
                "item": product.name,
                "item_id": product_id,
            },
            {"project": {"vouchar_id": 1, "_id": 1}},
        )

        # Check if the product is associated with any inventory items
        if vouchar_id_list:
            for vouchar in vouchar_id_list:
                vouchar_id = vouchar.get("vouchar_id")

                is_vouchar_present = await vouchar_repo.findAll(
                    {
                        "_id": vouchar_id,
                        "company_id": userSettings["current_company_id"],
                        "user_id": current_user.user_id,
                    }
                )
                if is_vouchar_present:
                    raise http_exception.BadRequestException(
                        detail="Product cannot be deleted as it is associated with invoices."
                    )

            raise http_exception.BadRequestException(
                detail="Product cannot be deleted as it is associated with inventory items."
            )

        if not vouchar_id_list:
            # If no inventory items are associated, proceed to delete the product
            await stock_item_repo.deleteOne(
                {
                    "_id": product_id,
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                    "company_id": userSettings["current_company_id"],
                },
            )

    return {"success": True, "message": "Product Deleted Successfully"}


# @Product.put(
#     "/restore/product/{product_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def restore_product(
#     product_id: str,
#     company_id: str = Query(...),
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "user" and current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()

#     product = await stock_item_repo.findOne(
#         {
#             "_id": product_id,
#             "user_id": current_user.user_id,
#             "is_deleted": True,
#             "company_id": company_id,
#         }
#     )

#     if not product:
#         raise http_exception.NotFoundException(detail="Product Not Found")

#     await stock_item_repo.update_one(
#         {
#             "_id": product_id,
#             "user_id": current_user.user_id,
#             "is_deleted": True,
#             "company_id": company_id,
#         },
#         {"$set": {"is_deleted": False}},
#     )

#     return {"success": True, "message": "Product Restored Successfully"}
