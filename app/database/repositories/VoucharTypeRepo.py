import re
from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.VoucharType import VoucherType, VoucherTypeDB
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


class VoucherTypeRepo(BaseMongoDbCrud[VoucherTypeDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "VoucherType",
            unique_attributes=["vouchar_type_name", "user_id", "company_id", 'parent'],
        )

    async def new(self, sub: VoucherType):
        return await self.save(VoucherTypeDB(**sub.model_dump()))

    async def viewAllVoucharType(
        self,
        search: str,
        company_id: str,
        pagination: PageRequest,
        sort: Sort,
        current_user: TokenData = Depends(get_current_user),
    ):
        filter_params = {}

        if current_user.user_id is not None:
            filter_params["$or"] = [
                {"user_id": current_user.user_id},
                {"user_id": {"$in": [None, ""]}},
            ]
        else:
            filter_params["user_id"] = {"$in": [None, ""]}

        if company_id is not None:
            if "$or" in filter_params:
                filter_params["$or"] = [
                    {**cond, "company_id": company_id} for cond in filter_params["$or"]
                ] + [
                    {**cond, "company_id": {"$in": [None, ""]}}
                    for cond in filter_params["$or"]
                ]
            else:
                filter_params["$or"] = [
                    {"company_id": company_id},
                    {"company_id": {"$in": [None, ""]}},
                ]
        else:
            if "$or" in filter_params:
                filter_params["$or"] = [
                    {**cond, "company_id": {"$in": [None, ""]}}
                    for cond in filter_params["$or"]
                ]
            else:
                filter_params["company_id"] = {"$in": [None, ""]}

        # Filter by search term
        if search not in ["", None]:
            try:
                safe_search = re.escape(search)
                filter_params["$or"] = [
                    {"vouchar_type_name": {"$regex": safe_search, "$options": "i"}},
                    {"parent": {"$regex": safe_search, "$options": "i"}},
                ]
            except re.error:
                # If regex is invalid, ignore search filter or handle as needed
                pass

        sort_fields_mapping = {
            "name": "vouchar_type_name",
            "parent": "parent",
            "created_at": "created_at",
            # "tax_supply_type": "tax_supply_type",
        }

        sort_field_mapped = sort_fields_mapping.get(sort.sort_field, "name")
        sort_order_value = 1 if sort.sort_order == SortingOrder.ASC else -1
        sort_criteria = {sort_field_mapped: sort_order_value}
        
        pipeline = [
            {"$match": filter_params},
            {"$sort": sort_criteria},
            {
                "$project": {
                    "_id": 1,
                    "name": "$vouchar_type_name",
                    "user_id": 1,
                    "company_id": 1,
                    "parent": 1,
                    # "parent_id": 1,
                    "numbering_method": 1,
                    # "is_deemedpositive": 1,
                    # "affects_stock": 1,
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
                unique=[],
            ),
        )


vouchar_type_repo = VoucherTypeRepo()
