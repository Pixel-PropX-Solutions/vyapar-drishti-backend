from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.StockItem import StockItem, StockItemDB
from app.database.repositories.categoryRepo import category_repo
from app.database.repositories.groupRepo import group_repo
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


class StockItemRepo(BaseMongoDbCrud[StockItemDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "StockItem",
            unique_attributes=["name", "user_id", "company_id"],
        )

    async def new(self, sub: StockItem):
        return await self.save(StockItemDB(**sub.model_dump()))

    async def viewAllProduct(
        self,
        search: str,
        category: str,
        company_id: str,
        group: str,
        pagination: PageRequest,
        sort: Sort,
        current_user: TokenData = Depends(get_current_user),
        is_deleted: bool = False,
    ):
        filter_params = {
            "user_id": current_user.user_id,
            "is_deleted": is_deleted,
            "company_id": company_id,
        }
        # Filter by search term
        if search not in ["", None]:
            try:
                safe_search = re.escape(search)
                filter_params["$or"] = [
                    {"name": {"$regex": safe_search, "$options": "i"}},
                    {"alias_name": {"$regex": safe_search, "$options": "i"}},
                    {"category": {"$regex": safe_search, "$options": "i"}},
                    {"group": {"$regex": safe_search, "$options": "i"}},
                    {"description": {"$regex": safe_search, "$options": "i"}},
                ]
            except re.error:
                # If regex is invalid, ignore search filter or handle as needed
                pass

        if category not in ["", None]:
            filter_params["category"] = category

        if group not in ["", None]:
            filter_params["group"] = group

        # Define sorting logic
        sort_options = {
            "name_asc": {"name": 1},
            "name_desc": {"name": -1},
            # "price_asc": {"selling_price": 1},
            # "price_desc": {"selling_price": -1},
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
                    "localField": "_category",
                    "foreignField": "_id",
                    "as": "category",
                }
            },
            # Use $unwind with preserveNullAndEmptyArrays to keep products without categories
            {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Group",
                    "localField": "_group",
                    "foreignField": "_id",
                    "as": "group",
                }
            },
            # Use $unwind with preserveNullAndEmptyArrays to keep products without categories
            {"$unwind": {"path": "$group", "preserveNullAndEmptyArrays": True}},
            {"$sort": sort_stage},
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
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": is_deleted,
                    "company_id": company_id,
                }
            },
            {"$group": {"_id": "$category"}},
            {"$project": {"_id": 0, "category": "$_id"}},
            {"$sort": {"category": 1}},
        ]

        unique_groups_pipeline = [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": is_deleted,
                    "company_id": company_id,
                }
            },
            {"$group": {"_id": "$category"}},
            {"$project": {"_id": 0, "category": "$_id"}},
            {"$sort": {"category": 1}},
        ]

        res = [doc async for doc in self.collection.aggregate(pipeline)]

        categories_res = [
            doc
            async for doc in category_repo.collection.aggregate(
                unique_categories_pipeline
            )
        ]

        group_res = [
            doc
            async for doc in group_repo.collection.aggregate(unique_categories_pipeline)
        ]
        docs = res[0]["docs"]
        count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0
        
        # Extract unique categories and groups
        unique_categories = [entry["category"] for entry in categories_res]
        
        unique_groups = [entry["group"] for entry in group_res]

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


stock_item_repo = StockItemRepo()
