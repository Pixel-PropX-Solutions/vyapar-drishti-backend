from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.InventoryGroup import InventoryGroup, InventoryGroupDB
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


class InventoryGroupRepo(BaseMongoDbCrud[InventoryGroupDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "InventoryGroup",
            unique_attributes=["inventory_group_name", "user_id", "company_id", 'parent'],
        )

    async def new(self, sub: InventoryGroup):
        return await self.save(InventoryGroupDB(**sub.model_dump()))

    async def viewAllGroup(
        self,
        search: str,
        pagination: PageRequest,
        sort: Sort,
        company_id: str = None,
        current_user_id: str = None,
    ):
        filter_params = {}

        if search not in ["", None]:
            filter_params["$or"] = [
                {"email": {"$regex": f"^{search}", "$options": "i"}},
                {
                    "inventory_group_name": {
                        "$regex": f"^{search}",
                        "$options": "i",
                    }
                },
                {
                    "alias": {
                        "$regex": f"^{search}",
                        "$options": "i",
                    }
                },
                
            ]

        
        sort_fields_mapping = {
            "name": "inventory_group_name",
            "created_at": "created_at",
            # "tax_supply_type": "tax_supply_type",
        }

        sort_field_mapped = sort_fields_mapping.get(sort.sort_field, "name")
        sort_order_value = 1 if sort.sort_order == SortingOrder.ASC else -1
        sort_criteria = {sort_field_mapped: sort_order_value}

        pipeline = []
        match_stage = {"is_deleted": False}
        if current_user_id is not None:
            match_stage["user_id"] = current_user_id
        if company_id is not None:
            match_stage["company_id"] = company_id
        pipeline.extend(
            [
                {"$match": match_stage},
                {"$match": filter_params},
                {"$sort": sort_criteria},
                {
                    "$project": {
                        "_id": 1,
                        "inventory_group_name": 1,
                        "user_id": 1,
                        "company_id": 1,
                        "image": 1,
                        "description": 1,
                        "is_deleted": 1,
                        "nature_of_goods": 1,
                        "hsn_code": 1,
                        "taxability": 1,
                        'created_at': 1,
                        'updated_at': 1,
                    }
                },
            ]
        )

        pipeline.append(
            {
                "$facet": {
                    "docs": [
                        {
                            "$skip": (pagination.paging.page - 1)
                            * (pagination.paging.limit)
                        },
                        {"$limit": pagination.paging.limit},
                    ],
                    "count": [{"$count": "count"}],
                }
            }
        )

        unique_states_pipeline = [
            {"$match": match_stage},
            {
                "$project": {
                    "states": {
                        "$cond": {
                            "if": {"$ne": ["$mailing_state", None]},
                            "then": "$mailing_state",
                            "else": "$mailing_country",
                        }
                    },
                },
            },
            {"$unwind": "$states"},
            {"$group": {"_id": "$states"}},
            {"$sort": {"_id": 1}},
            {"$project": {"state": "$_id", "_id": 0}},
        ]

        res = [doc async for doc in self.collection.aggregate(pipeline)]
        states_res = [
            doc async for doc in self.collection.aggregate(unique_states_pipeline)
        ]
        docs = res[0]["docs"]
        count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0
        unique_states = [entry["state"] for entry in states_res]

        return PaginatedResponse(
            docs=docs,
            meta=Meta(
                **pagination.paging.model_dump(), total=count, unique=unique_states
            ),
        )



inventory_group_repo = InventoryGroupRepo()
