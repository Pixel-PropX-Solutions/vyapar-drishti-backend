from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.user import User, UserDB
from app.oauth2 import get_current_user
from app.schema.token import TokenData
from .crud.base_mongo_crud import BaseMongoDbCrud
from app.database.repositories.crud.base import (
    PageRequest,
    Meta,
    PaginatedResponse,
    Sort,
    SortingOrder,
)


class userRepo(BaseMongoDbCrud[UserDB]):
    def __init__(self):
        super().__init__(ENV_PROJECT.MONGO_DATABASE, "User", unique_attributes=["email"])

    async def new(self, sub: User):
        return await self.save(UserDB(**sub.model_dump()))

    async def viewAllUsers(
        self,
        search: str,
        pagination: PageRequest,
        sort: Sort,
        start_date: str = "",
        end_date: str = "",
    ):
        filter_params = {}

        if start_date not in ["", None] and end_date not in ["", None]:
            startDate = start_date[0:10]
            endDate = end_date[0:10]
            filter_params["created_at"] = {"$gte": startDate, "$lte": endDate}

        if sort.sort_field:
            sort_stage = {
                sort.sort_field: int(sort.sort_order),
            }

        pipeline = [
            {"$match": filter_params},
            {
                "$lookup": {
                    "from": "UserSettings",
                    "localField": "_id",
                    "foreignField": "user_id",
                    "as": "user_settings",
                }
            },
            {"$unwind": {"path": "$user_settings", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Company",
                    "let": {"user_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$user_id", "$$user_id"]}}},
                        {
                            "$lookup": {
                                "from": "CompanySettings",
                                "let": {"company_id": "$_id"},
                                "pipeline": [
                                    {
                                        "$match": {
                                            "$expr": {
                                                "$eq": ["$company_id", "$$company_id"]
                                            },
                                        }
                                    },
                                    {
                                        "$project": {
                                            "_id": 1,
                                            "company_name": 1,
                                            "country": 1,
                                            "bank_details": 1,
                                        }
                                    },
                                ],
                                "as": "company_info",
                            }
                        },
                        {
                            "$unwind": {
                                "path": "$company_info",
                                "preserveNullAndEmptyArrays": True,
                            }
                        },
                        {
                            "$lookup": {
                                "from": "Voucher",
                                "let": {"company_id": "$_id"},
                                "pipeline": [
                                    {
                                        "$match": {
                                            "$expr": {
                                                "$eq": ["$company_id", "$$company_id"]
                                            },
                                        }
                                    },
                                    {"$sort": {"created_at": -1}},
                                ],
                                "as": "invoices",
                            }
                        },
                        {
                            "$project": {
                                "_id": 1,
                                "company_name": "$company_info.company_name",
                                "country": "$company_info.country",
                                "bank_details": "$company_info.bank_details",
                                "email": 1,
                                "phone": 1,
                                "state": 1,
                                "pinCode": 1,
                                "created_at": 1,
                                "last_invoice_date": {
                                    "$arrayElemAt": ["$invoices.date", 0]
                                },
                                "last_invoice_created_at": {
                                    "$arrayElemAt": ["$invoices.created_at", 0]
                                },
                                "total_invoices": {"$size": "$invoices"},
                            }
                        },
                    ],
                    "as": "companies",
                }
            },
            {
                "$addFields": {
                    "latest_invoice_date": {
                        "$max": {
                            "$map": {
                                "input": "$companies.last_invoice_date",
                                "as": "d",
                                "in": {
                                    "$dateFromString": {
                                        "dateString": "$$d",
                                        "format": "%Y-%m-%d",
                                    }
                                },
                            }
                        }
                    },
                    "latest_invoice_created_at": {
                        "$max": "$companies.last_invoice_created_at"
                    },
                    "total_invoices_created": {
                        "$sum": "$companies.total_invoices"
                    },
                }
            },
            {
                "$project": {
                    "password": 0,
                    "is_deleted": 0,
                    "updated_at": 0,
                    "user_settings.role": 0,
                    "user_settings.permissions": 0,
                    "user_settings.ui_preferences": 0,
                    "user_settings.is_deleted": 0,
                    "user_settings.created_at": 0,
                    "user_settings.updated_at": 0,
                }
            },
            {"$sort": sort_stage},
            {
                "$match": {
                    **(
                        {
                            "$or": [
                                {
                                    "name.first": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "name.last": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "email": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                            ]
                        }
                        if search not in ["", None]
                        else {}
                    )
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


user_repo = userRepo()
