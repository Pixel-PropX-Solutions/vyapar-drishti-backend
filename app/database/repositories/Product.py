from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.Product import product, ProductDB
from app.oauth2 import get_current_user
from app.schema.token import TokenData
from .crud.base_mongo_crud import BaseMongoDbCrud
from app.database.repositories.crud.base import (
    PageRequest,
    Meta,
    PaginatedResponse,
    SortingOrder,
    Sort,
    Page,
)
from pydantic import BaseModel
from typing import List
import re


class ProductRepo(BaseMongoDbCrud[ProductDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE, "Product", unique_attributes=["product_name"]
        )

    async def new(self, sub: product):
        return await self.save(ProductDB(**sub.model_dump()))

    async def viewAllProduct(
        self,
        search: str,
        category: str,
        pagination: PageRequest,
        sort: Sort,
        current_user: TokenData = Depends(get_current_user),
        is_deleted: bool = False,
    ):
        filter_params = {"user_id": current_user.user_id, "is_deleted": is_deleted}
        # Filter by search term
        if search not in ["", None]:
            try:
                safe_search = re.escape(search)
                filter_params["$or"] = [
                    {"product_name": {"$regex": safe_search, "$options": "i"}},
                    {"hsn_code": {"$regex": safe_search, "$options": "i"}},
                    {"barcode": {"$regex": safe_search, "$options": "i"}},
                    {"category": {"$regex": safe_search, "$options": "i"}},
                    {"description": {"$regex": safe_search, "$options": "i"}},
                ]
            except re.error:
                # If regex is invalid, ignore search filter or handle as needed
                pass
        if category not in ["", None]:
            filter_params["category"] = category

        # Define sorting logic
        sort_options = {
            "name_asc": {"product_name": 1},
            "name_desc": {"product_name": -1},
            "price_asc": {"selling_price": 1},
            "price_desc": {"selling_price": -1},
            "created_at_asc": {"created_at": 1},
            "created_at_desc": {"created_at": -1},
        }

        # Construct sorting key
        sort_key = f"{sort.sort_field}_{'asc' if sort.sort_order == SortingOrder.ASC else 'desc'}"

        sort_stage = sort_options.get(sort_key, {"created_at": 1})

        pipeline = [
            {"$match": filter_params},
            {
            "$lookup": {
                "from": "Category",
                "localField": "category",
                "foreignField": "_id",
                "as": "categoryDetails",
            }
            },
            # Use $unwind with preserveNullAndEmptyArrays to keep products without categories
            {"$unwind": {"path": "$categoryDetails", "preserveNullAndEmptyArrays": True}},
            {"$sort": sort_stage},
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
                "category": {
                "$ifNull": ["$categoryDetails.category_name", None]
                },
                "category_desc": {
                "$ifNull": ["$categoryDetails.description", None]
                },
            }
            },
            {
            "$facet": {
                "docs": [
                {"$skip": (pagination.paging.page - 1) * pagination.paging.limit},
                {"$limit": pagination.paging.limit},
                ],
                "count": [{"$count": "count"}],
            }
            },
        ]

        unique_categories_pipeline = [
            {"$group": {"_id": "$category"}},
            {"$project": {"_id": 0, "category": "$_id"}},
            {"$sort": {"category": 1}},
        ]

        res = [doc async for doc in self.collection.aggregate(pipeline)]
        categories_res = [
            doc async for doc in self.collection.aggregate(unique_categories_pipeline)
        ]
        docs = res[0]["docs"]
        count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0
        unique_categories = [entry["category"] for entry in categories_res]

        return PaginatedResponse(
            docs=docs,
            meta=Meta(
                page=pagination.paging.page,
                limit=pagination.paging.limit,
                total=count,
                unique=unique_categories,
            ),
        )

    async def group_products_by_stock_level(self, chemist_id: str):
        pipeline = [
            {
                "$set": {
                    "stock_level": {
                        "$switch": {
                            "branches": [
                                {"case": {"$lte": ["$quantity", 10]}, "then": "Low"},
                                {
                                    "case": {"$gte": ["$quantity", 200]},
                                    "then": "Overstock",
                                },
                            ],
                            "default": "Medium",
                        }
                    }
                }
            },
            {"$group": {"_id": "$stock_level", "count": {"$sum": 1}}},
        ]

        return await self.collection.aggregate(pipeline).to_list(None)


product_repo = ProductRepo()
