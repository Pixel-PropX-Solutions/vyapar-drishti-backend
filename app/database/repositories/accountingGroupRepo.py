from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.AccountingGroup import AccountingGroup, AccountingGroupDB
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


class AccountingGroupRepo(BaseMongoDbCrud[AccountingGroupDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "AccountingGroup",
            unique_attributes=[
                "accounting_group_name",
                "user_id",
                "company_id",
                "parent",
            ],
        )

    async def new(self, sub: AccountingGroup):
        return await self.save(AccountingGroupDB(**sub.model_dump()))

    async def viewAllGroup(
        self,
        search: str,
        pagination: PageRequest,
        sort: Sort,
        parent: str = None,
        company_id: str = None,
        state: str = None,
        is_deleted: bool = False,
        current_user_id: str = None,
    ):
        filter_params = {
            "is_deleted": is_deleted,
        }
        if current_user_id is not None:
            filter_params["$or"] = [
                {"user_id": current_user_id},
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

        if search not in ["", None]:
            filter_params["$or"] = [
                {"email": {"$regex": f"^{search}", "$options": "i"}},
                {
                    "accounting_group_name": {
                        "$regex": f"^{search}",
                        "$options": "i",
                    }
                },
                {
                    "parent": {
                        "$regex": f"^{search}",
                        "$options": "i",
                    }
                },
                {
                    "description": {
                        "$regex": f"^{search}",
                        "$options": "i",
                    }
                },
                
            ]

       
        if parent not in ["", None]:
            filter_params["$or"] = [
                {"parent": {"$regex": f"^{state}", "$options": "i"}},
            ]

        sort_fields_mapping = {
            "accounting_group_name": "accounting_group_name",
            "parent": "parent",
            "created_at": "created_at",
        }

        sort_field_mapped = sort_fields_mapping.get(sort.sort_field, "accounting_group_name")
        sort_order_value = 1 if sort.sort_order == SortingOrder.ASC else -1
        sort_criteria = {sort_field_mapped: sort_order_value}

        pipeline = []

        pipeline.extend(
            [
                {"$match": filter_params},
                {"$sort": sort_criteria},
                {
                    "$project": {
                        "_id": 1,
                        'user_id': 1,
                        "company_id": 1,
                        'is_deleted': 1,
                        "accounting_group_name": 1,
                        "description": 1,
                        "image": 1,
                        "parent": 1,
                        "created_at": 1,
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

        pipeline2 = [
            {"$match": {"id": {"$in": [None, ""]}}},
            {
                "$facet": {
                    "count": [{"$count": "count"}],
                }
            },
        ]

        unique_states_pipeline = [
            {"$match": filter_params},
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
        res2 = [doc async for doc in self.collection.aggregate(pipeline2)]
        
        
        states_res = [
            doc async for doc in self.collection.aggregate(unique_states_pipeline)
        ]
                
        docs = res[0]["docs"]
        count = res2[0]["count"][0]["count"] if len(res2[0]["count"]) > 0 else 0
        unique_states = [entry["state"] for entry in states_res]

        return PaginatedResponse(
            docs=docs,
            meta=Meta(
                **pagination.paging.model_dump(), total=count, unique=unique_states
            ),
        )


accounting_group_repo = AccountingGroupRepo()
