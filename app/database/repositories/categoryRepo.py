from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.Category import Category, CategoryDB
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


class CategoryRepo(BaseMongoDbCrud[CategoryDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "Category",
            unique_attributes=["category_name", "user_id", "company_id"],
        )

    async def new(self, sub: Category):
        return await self.save(CategoryDB(**sub.model_dump()))

    async def viewAllCategories(
        self,
        search: str,
        company_id: str,
        pagination: PageRequest,
        sort: Sort,
        current_user: TokenData = Depends(get_current_user),
    ):
        filter_params = {
            "user_id": current_user.user_id,
            "company_id": company_id,
            "is_deleted": False,
        }
        # Filter by search term
        if search is not None and isinstance(search, str) and search.strip() != "":
            filter_params["$or"] = [
                {"category_name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]

        sort_fields_mapping = {
            "category_name": "category_name",
            "created_at": "created_at",
            "updated_at": "updated_at",
        }

        sort_field_mapped = sort_fields_mapping.get(sort.sort_field, "category_name")
        sort_order_value = 1 if sort.sort_order == SortingOrder.ASC else -1
        sort_stage = {sort_field_mapped: sort_order_value}

        pipeline = [
            {"$match": filter_params},
            {
                "$lookup": {
                    "from": "StockItem",
                    "let": {"category_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$category_id", "$$category_id"]}}}
                    ],
                    "as": "stock_items",
                }
            },
            {
                "$unwind": {
                    "path": "$stock_items",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            # {
            #     "$addFields": {
            #         "stock_items_count": {
            #             "$cond": {
            #                 "if": {"$isArray": "$stock_items"},
            #                 "then": {"$size": "$stock_items"},
            #                 "else": 0,
            #             }
            #         }
            #     }
            # },
            {
                "$group": {
                    "_id": "$_id",
                    "user_id": {"$first": "$user_id"},
                    "company_id": {"$first": "$company_id"},
                    "category_name": {"$first": "$category_name"},
                    "description": {"$first": "$description"},
                    "image": {"$first": "$image"},
                    # "stock_items_count": {"$first": "$stock_items_count"},
                    "stock_items": {"$push": "$stock_items"},
                    "is_deleted": {"$first": "$is_deleted"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "user_id": 1,
                    "company_id": 1,
                    "category_name": 1,
                    "description": 1,
                    "image": 1,
                    "stock_items_count": {
                        "$cond": {
                            "if": {"$isArray": "$stock_items"},
                            "then": {"$size": "$stock_items"},
                            "else": 0,
                        }
                    },
                    "stock_items": {
                        "$cond": {
                            "if": {"$isArray": "$stock_items"},
                            "then": "$stock_items",
                            "else": [],
                        }
                    },
                    "is_deleted": 1,
                    "created_at": 1,
                    "updated_at": 1,
                }
            },
            {"$sort": sort_stage},
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

        res = [doc async for doc in self.collection.aggregate(pipeline)]

        docs = res[0]["docs"]
        count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0

        return PaginatedResponse(
            docs=docs,
            meta=Meta(
                page=pagination.paging.page,
                limit=pagination.paging.limit,
                total=count,
                unique=[],  # Added to satisfy Meta's required field
            ),
        )


category_repo = CategoryRepo()
