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
            ENV_PROJECT.MONGO_DATABASE, "Category", unique_attributes=["name", 'user_id', 'company_id']
        )

    async def new(self, sub: Category):
        return await self.save(CategoryDB(**sub.model_dump()))

    async def viewAllCategories(
        self,
        search: str,
        pagination: PageRequest,
        sort: Sort,
        current_user: TokenData = Depends(get_current_user),
        is_deleted: bool = False,
    ):
        filter_params = {"user_id": current_user.user_id, "is_deleted": is_deleted}
        # Filter by search term
        if search is not None and isinstance(search, str) and search.strip() != "":
            filter_params["$or"] = [
                {"category_name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
            ]

        # Define sorting logic
        sort_options = {
            "name_asc": {"category_name": 1},
            "name_desc": {"category_name": -1},
            "created_at_asc": {"created_at": 1},
            "created_at_desc": {"created_at": -1},
            "updated_at_asc": {"updated_at": 1},
            "updated_at_desc": {"updated_at": -1},
        }

        # Construct sorting key
        sort_key = f"{sort.sort_field}_{'asc' if sort.sort_order == SortingOrder.ASC else 'desc'}"

        sort_stage = sort_options.get(sort_key, {"created_at": 1})

        pipeline = [
            {"$match": filter_params},
            {"$sort": sort_stage},
            {
                "$project": {
                    "created_at": 1,
                    "updated_at": 1,
                    "category_name": 1,
                    "description": 1,
                    "image": 1,
                    "user_id": 1,
                    "is_deleted": 1,
                    "_id": 1,
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
