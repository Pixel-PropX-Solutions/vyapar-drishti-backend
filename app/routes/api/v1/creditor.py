from fastapi import FastAPI, status, Depends, File, UploadFile, Form
from fastapi.responses import ORJSONResponse
from fastapi import APIRouter
from app.schema.token import TokenData
from app.oauth2 import get_current_user
from app.schema.enums import UserRole

import app.http_exception as http_exception
from app.utils.mailer_module import mail
from app.database.models.user import User
from app.database.repositories.user import user_repo
from app.utils.generatePassword import generatePassword
from app.utils.hashing import hash_password
import re
from app.database.repositories.Product_Stock import product_stock_repo
from app.database.repositories.Stock_Movement import stock_movement_repo
import asyncio

from app.utils.mailer_module import template
from app.database.models.user import UserCreate
from app.database.models.Creditor import CreditorCreate
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest
from fastapi import Query
from app.database.repositories.user import user_repo
from app.database.repositories.creditor import creditor_repo
from app.database.models.Company import CompanyCreate

from app.database.models.Company import Company

from app.database.repositories.Product import product_repo
from app.database.repositories.Chemist import chemist_repo
from app.database.models.Chemist import Chemist, ChemistCreate
from app.database.repositories.company import company_repo, Company
from app.utils.cloudinary_client import cloudinary_client


creditor = APIRouter()


@creditor.post("/create", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def create_creditor(
    name: str = Form(...),
    billing: str = Form(...),
    email: str = Form(None),
    company_name: str = Form(None),
    phone: str = Form(None),
    code: str = Form(None),
    gstin: str = Form(None),
    opening_balance: str = Form(None),
    balance_type: str = Form(None),
    credit_limit: str = Form(None),
    image: UploadFile = File(None),
    tags: str = Form(None),
    pan_number: str = Form(None),
    due_date: str = Form(None),
    shipping: str = Form(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin" and current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    creditorExists = await creditor_repo.findOne(
        {"name": name, "user_id": current_user.user_id}
    )
    if creditorExists is not None:
        raise http_exception.ResourceConflictException(
            message="Creditor with this name already exists."
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
        print("upload_result", upload_result)
        image_url = upload_result["url"]

    phone_data = None
    if code is not None or phone is not None:
        phone_data = {"code": code, "number": phone}

    creditor_data = {
        "name": name,
        "user_id": current_user.user_id,
        "is_deleted": False,
        "phone": phone_data,
        "email": email,
        "gstin": gstin,
        "company_name": company_name,
        "billing": billing,
        "shipping": shipping,
        "opening_balance": opening_balance,
        "balance_type": balance_type,
        "image": image_url,
        "pan_number": pan_number,
        "credit_limit": credit_limit,
        "tags": tags,
        "due_date": due_date,
    }

    print("creditor_data", creditor_data)
    response = await creditor_repo.new(CreditorCreate(**creditor_data))

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Creditor Already Exists"
        )

    return {"success": True, "message": "Creditor Created Successfully"}


@creditor.get(
    "/view/all/creditor", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_creditor(
    current_user: TokenData = Depends(get_current_user),
    search: str = None,
    id_deleted: bool = False,
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

    result = await creditor_repo.viewAllCreditors(
        search=search, id_deleted=id_deleted, current_user_id=current_user.user_id,  pagination=page_request, sort=sort
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


# @creditor.post(
#     "/create/stockist/{user_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def create_stockist(
#     user: StockistCreate,
#     current_user: TokenData = Depends(get_current_user),
#     user_id: str = "",
# ):
#     if current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()

#     userExists = await user_repo.findOne({"_id": user_id, "role": "Stockist"})
#     if userExists is None:
#         raise http_exception.ResourceNotFoundException()

#     accountExists = await stockist_repo.findOne({"user_id": user_id})
#     if accountExists is not None:
#         raise http_exception.ResourceConflictException()

#     user = user.model_dump()
#     user["user_id"] = user_id

#     await stockist_repo.new(Stockist(**user))

#     return {
#         "success": True,
#         "message": "Stockist Created Successfully",
#     }


@creditor.get(
    "/view/all/chemist", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_chemist_user(
    current_user: TokenData = Depends(get_current_user),
    search: str = None,
    state: str = None,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=20),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await user_repo.viewAllChemist(
        search=search,
        state=state,
        pagination=page_request,
        sort=sort,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@creditor.post(
    "/create/chemist/{user_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def createChemistUser(
    user: ChemistCreate,
    current_user: TokenData = Depends(get_current_user),
    user_id: str = "",
):
    if current_user.user_type != "Admin":
        raise http_exception.CredentialsInvalidException()

    userExists = await user_repo.findOne({"_id": user_id, "role": "Chemist"})
    if userExists is None:
        raise http_exception.ResourceNotFoundException()

    account_create = await chemist_repo.findOne({"user_id": user_id})
    if account_create is not None:
        raise http_exception.ResourceConflictException()

    user = user.model_dump()
    user["user_id"] = user_id
    await chemist_repo.new(Chemist(**user))

    return {"success": True, "message": "Chemist Created Successfully"}


# @creditor.put(
#     "/update/stockist/{user_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def update_stockist(
#     user: StockistCreate,
#     current_user: TokenData = Depends(get_current_user),
#     user_id: str = "",
# ):
#     if current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()

#     userExists = await user_repo.findOne({"_id": user_id, "role": "Stockist"})
#     if userExists is None:
#         raise http_exception.ResourceNotFoundException()

#     accountExists = await stockist_repo.findOne({"user_id": user_id})
#     if accountExists is None:
#         raise http_exception.ResourceNotFoundException()

#     user = user.model_dump()

#     updated_dict = {}

#     updated_dict = {}

#     for k, v in dict(user).items():
#         if isinstance(v, str) and v not in ["", None]:
#             updated_dict[k] = v
#         elif isinstance(v, dict):
#             temp_dict = {}
#             for k1, v1 in v.items():
#                 if isinstance(v1, str) and v1 not in ["", None]:
#                     temp_dict[k1] = v1

#             if temp_dict:  #
#                 updated_dict[k] = temp_dict

#     await stockist_repo.collection.update_one(
#         {"user_id": user_id}, {"$set": updated_dict}
#     )

#     return {
#         "success": True,
#         "message": "Stockist values updated successfully",
#     }


@creditor.put(
    "/update/chemist/{user_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def update_chemist(
    user: ChemistCreate,
    current_user: TokenData = Depends(get_current_user),
    user_id: str = "",
):
    if current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userExists = await user_repo.findOne({"_id": user_id, "role": "Chemist"})
    if userExists is None:
        raise http_exception.ResourceNotFoundException()

    accountExists = await chemist_repo.findOne({"user_id": user_id})
    if accountExists is None:
        raise http_exception.ResourceNotFoundException()

    user = user.model_dump()

    updated_dict = {}

    for k, v in dict(user).items():
        if isinstance(v, str) and v not in ["", None]:
            updated_dict[k] = v
        elif isinstance(v, dict):
            temp_dict = {}
            for k1, v1 in v.items():
                if isinstance(v1, str) and v1 not in ["", None]:
                    temp_dict[k1] = v1

            if temp_dict:
                updated_dict[k] = temp_dict
    await chemist_repo.collection.update_one({"user_id": user_id}, {"$set": updated_dict})

    return {
        "success": True,
        "message": "Chemist values updated successfully",
    }


@creditor.get("/view/stockist/profile/{user_id}", response_class=ORJSONResponse)
async def viewStockistProfile(
    current_user: TokenData = Depends(get_current_user), user_id: str = ""
):
    if current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userExists = await user_repo.findOne({"_id": user_id, "role": "Stockist"})
    if userExists is None:
        raise http_exception.ResourceNotFoundException()

    pipeline = [
        {"$match": {"_id": user_id}},
        {
            "$lookup": {
                "from": "Stockist",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "StockistData",
            }
        },
        {
            "$set": {
                "StockistData": {
                    "$cond": [
                        {"$eq": [{"$size": "$StockistData"}, 0]},
                        None,
                        {"$arrayElemAt": ["$StockistData", 0]},
                    ]
                }
            }
        },
        {
            "$project": {
                "password": 0,
                "created_at": 0,
                "updated_at": 0,
                "StockistData._id": 0,
                "StockistData.user_id": 0,
                "StockistData.created_at": 0,
                "StockistData.updated_at": 0,
            }
        },
    ]

    response = await user_repo.collection.aggregate(pipeline=pipeline).to_list(None)

    return {
        "success": True,
        "message": "Stockist Profile Fetched Successfully",
        "data": response,
    }


@creditor.get("/view/chemist/profile/{user_id}", response_class=ORJSONResponse)
async def viewChemistProfile(
    current_user: TokenData = Depends(get_current_user), user_id: str = ""
):
    if current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userExists = await user_repo.findOne({"_id": user_id, "role": "Chemist"})
    if userExists is None:
        raise http_exception.ResourceNotFoundException()

    pipeline = [
        {"$match": {"_id": user_id}},
        {
            "$lookup": {
                "from": "Chemist",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "ChemistData",
            }
        },
        {
            "$set": {
                "ChemistData": {
                    "$cond": [
                        {"$eq": [{"$size": "$ChemistData"}, 0]},
                        None,
                        {"$arrayElemAt": ["$ChemistData", 0]},
                    ]
                }
            }
        },
        {
            "$project": {
                "password": 0,
                "created_at": 0,
                "updated_at": 0,
                "ChemistData.user_id": 0,
                "ChemistData.created_at": 0,
                "ChemistData.updated_at": 0,
            }
        },
    ]

    response = await user_repo.collection.aggregate(pipeline=pipeline).to_list(None)

    return {
        "success": True,
        "message": "Chemist Profile Fetched Successfully",
        "data": response,
    }


# @creditor.get(
#     "/view/stockists/shops",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def getStockistShops(
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "user" and current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()

#     shops = await stockist_repo.collection.aggregate(
#         [
#             {
#                 "$project": {
#                     "address": 0,
#                     "phone_number": 0,
#                     "user_id": 0,
#                     "name": 0,
#                     "created_at": 0,
#                     "updated_at": 0,
#                 },
#             },
#             {"$sort": {"company_name": 1}},
#         ]
#     ).to_list(None)
#     return {"success": True, "data": shops}


@creditor.get("/get/analytics", response_class=ORJSONResponse)
async def get_analytics(
    current_user: TokenData = Depends(get_current_user),
    month: int = "",
    year: int = "",
):
    if current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    user_id = current_user.user_id

    response = await asyncio.gather(
        stock_movement_repo.get_total_sales(chemist_id=user_id, movement="OUT"),
        stock_movement_repo.get_total_sales(chemist_id=user_id, movement="IN"),
        product_stock_repo.product_stock_movement(chemist_id=user_id),
        product_stock_repo.return_pending_stock_amount(chemist_id=user_id),
        product_stock_repo._return_pending_stock_amount(chemist_id=user_id),
        stock_movement_repo.get_sales_trends(
            chemist_id=user_id, movement="OUT", month=None, year=year
        ),
        stock_movement_repo.get_sales_trends_mont_wise(
            chemist_id=user_id, movement="OUT", month=month, year=year
        ),
        stock_movement_repo.get_sales_trends_mont_wise(
            chemist_id=user_id, movement="IN", month=month, year=year
        ),
        stock_movement_repo.get_total_sales_category(
            chemist_id=user_id, movement="OUT", month=month, year=year
        ),
        product_stock_repo.group_products_by_stock_level(chemist_id=user_id),
        # Added: top 5 selling categories of all time
        stock_movement_repo.get_top_category_monthly_user(
            chemist_id=user_id, movement="OUT", month=month, year=year
        ),
        stock_movement_repo.get_sales_trends(
            chemist_id=user_id, movement="OUT", month=month, year=year
        ),
    )

    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    sales_trends_month_wise_out = response[6]
    sales_trends_month_wise_in = response[7]
    TopMonths = [
        {
            "id": str(i + 1),
            "name": month_names[i],
            "totalSales": sales_trends_month_wise_out["data"][i],
            "stockPurchased": sales_trends_month_wise_in["data"][i],
        }
        for i in range(12)
    ]
    return {
        "success": True,
        "data": {
            "total_sales": response[0][0]["total_amount"],
            "total_purchased": response[1][0]["total_amount"],
            "remaining_stock": response[2][0]["_amount"],
            "pending_returns": response[3][0]["_amount"],
            "dead_stocks": response[4][0]["_amount"] if response[4] != [] else 0,
            "sales_trends_yearly": response[5],
            "top_month_sales": TopMonths,
            "category_wise_percent": response[8],
            "stock_level": response[9],
            "top_5_categories_all_time": response[10],
            "sales_trends_monthly": response[11],
        },
    }


@creditor.get("/get/analytics/admin", response_class=ORJSONResponse)
async def get_analytics(
    # current_user : TokenData = Depends(get_current_user)
    month: int = "",
    year: int = "",
):
    # if current_user.user_type != "user":
    #     raise http_exception.CredentialsInvalidException()
    from collections import defaultdict

    user_id = ""
    response = await asyncio.gather(
        stock_movement_repo.get_total_sales(chemist_id=user_id, movement="OUT"),
        stock_movement_repo.get_total_sales(chemist_id=user_id, movement="IN"),
        product_stock_repo.product_stock_movement(chemist_id=user_id),
        product_stock_repo.return_pending_stock_amount(chemist_id=user_id),
        product_stock_repo._return_pending_stock_amount(chemist_id=user_id),
        stock_movement_repo.get_sales_trends(
            chemist_id=user_id, movement="OUT", month=month, year=year
        ),
        stock_movement_repo.get_sales_trends_mont_wise(
            chemist_id=user_id, movement="OUT", month=month, year=year
        ),
        stock_movement_repo.get_sales_trends_mont_wise(
            chemist_id=user_id, movement="IN", month=month, year=year
        ),
        stock_movement_repo.get_total_sales_category(
            chemist_id=user_id, movement="OUT", month=month, year=year
        ),
        product_stock_repo.group_products_by_stock_level(chemist_id=user_id),
        stock_movement_repo.get_total_sales_chemist_wise(
            chemist_id=user_id, movement="OUT"
        ),
        stock_movement_repo.get_total_sales_chemist_wise(
            chemist_id=user_id, movement="IN"
        ),
        stock_movement_repo.get_top_category_yearly_admin(
            chemist_id=None, movement="OUT", month=month, year=year
        ),
    )

    month_names = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    sales_trends_month_wise_out = response[6]
    sales_trends_month_wise_in = response[7]
    TopMonths = [
        {
            "id": str(i + 1),
            "name": month_names[i],
            "totalSales": sales_trends_month_wise_out["data"][i],
            "stockPurchased": sales_trends_month_wise_in["data"][i],
        }
        for i in range(12)
    ]
    # Add sales data
    sales_trends_month_wise_out_chemist = response[10]
    sales_trends_month_wise_in_chemist = response[11]

    from collections import defaultdict

    chemist_data = defaultdict(
        lambda: {
            "totalSales": 0.0,
            "stockPurchased": 0.0,
            "name": "",
            "pendingStockAmount": 0.0,
            "remainingStock": 0.0,
            "data": [],
        }
    )

    # Add sales data
    for entry in sales_trends_month_wise_out_chemist:
        chemist_id = entry["_id"]
        chemist_data[chemist_id]["totalSales"] = entry["total_amount"]
        chemist_data[chemist_id]["name"] = (
            entry.get("chemist_name_first_name", "")
            + " "
            + entry.get("chemist_name_last_name", "")
        ).strip()
        chemist_data[chemist_id]["shop_name"] = (entry.get("shop_name", "")).strip()

    # Add purchase data
    for entry in sales_trends_month_wise_in_chemist:
        chemist_id = entry["_id"]
        chemist_data[chemist_id]["stockPurchased"] = entry["total_amount"]
        if not chemist_data[chemist_id]["name"]:
            chemist_data[chemist_id]["name"] = (
                entry.get("chemist_name_first_name", "")
                + " "
                + entry.get("chemist_name_last_name", "")
            ).strip()
        chemist_data[chemist_id]["shop_name"] = (entry.get("shop_name", "")).strip()
        chemist_data[chemist_id]["data"] = await stock_movement_repo.get_sales_trends(
            chemist_id=chemist_id, movement="OUT", month=None, year=year
        )

    # Add pending stock amount
    for entry in sales_trends_month_wise_in_chemist:
        chemist_id = entry["_id"]
        res = await product_stock_repo.return_pending_stock_amount(chemist_id=chemist_id)
        pending_amount = res[0]["_amount"] if res and "_amount" in res[0] else 0
        chemist_data[chemist_id]["pendingStockAmount"] = pending_amount
        if not chemist_data[chemist_id]["name"]:
            chemist_data[chemist_id]["name"] = (
                entry.get("chemist_name_first_name", "")
                + " "
                + entry.get("chemist_name_last_name", "")
            ).strip()

    # Add remaining stock
    for entry in sales_trends_month_wise_in_chemist:
        chemist_id = entry["_id"]
        res = await product_stock_repo.product_stock_movement(chemist_id=chemist_id)
        remaining_amount = res[0]["_amount"] if res and "_amount" in res[0] else 0
        chemist_data[chemist_id]["remainingStock"] = remaining_amount
        if not chemist_data[chemist_id]["name"]:
            chemist_data[chemist_id]["name"] = (
                entry.get("chemist_name_first_name", "")
                + " "
                + entry.get("chemist_name_last_name", "")
            ).strip()

    # Convert to list of dicts, filter out null chemistId
    grouped_chemist_data = [
        {"chemistId": k, **v} for k, v in chemist_data.items() if k is not None
    ]

    # Remove entries where all values are zero (optional, if you want to filter out empty chemists)
    grouped_chemist_data = [
        d
        for d in grouped_chemist_data
        if d.get("totalSales", 0) != 0
        or d.get("stockPurchased", 0) != 0
        or d.get("pendingStockAmount", 0) != 0
        or d.get("remainingStock", 0) != 0
    ]

    # Sort by totalSales
    grouped_chemist_data.sort(key=lambda x: x["totalSales"], reverse=True)

    # Output
    return {
        "success": True,
        "data": {
            "total_sales": response[0][0]["total_amount"],
            "total_purchase": response[1][0]["total_amount"],
            "remaining_stock": response[2][0]["_amount"],
            "pending_stock": response[3][0]["_amount"],
            "dead_stock": (response[4][0]["_amount"] if response[4] != [] else 0),
            "sales_trends": response[5],
            "sales_trends_month_wise": TopMonths,
            "category_wise": response[8],
            "stock_level": response[9],
            "chemist_wise_total_sales": grouped_chemist_data,
            "top_5_categories_all_time": response[12],
        },
    }
