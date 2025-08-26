from app.Config import ENV_PROJECT
from app.database.models.Ledger import Ledger, LedgerDB
from .crud.base_mongo_crud import BaseMongoDbCrud
from app.database.repositories.crud.base import (
    PageRequest,
    Meta,
    PaginatedResponse,
    Sort,
    SortingOrder,
)
import re
from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.Vouchar import Voucher, VoucherDB
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
import re
from datetime import datetime

SUFFIXES = [
    "Traders",
    "Enterprises",
    "Corporation",
    "Group",
    "Pvt Ltd",
    "Co.",
    "Industries",
    "Solutions",
    "Exports",
    "Imports",
    "Distributors",
    "& Sons",
    "LLC",
    "Inc.",
    "LLP",
    "Agencies",
    "Services",
]


def normalize_name(name: str) -> str:
    """Basic normalization: remove extra spaces, keep only alphabets and digits."""
    return re.sub(r"\s+", " ", name.strip())


class ledgerRepo(BaseMongoDbCrud[LedgerDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "Ledger",
            unique_attributes=["ledger_name", "user_id", "company_id", "parent"],
        )

    async def new(self, sub: Ledger):
        return await self.save(LedgerDB(**sub.model_dump()))

    async def viewAllledgers(
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
        filter_params = {}

        if search not in ["", None]:
            filter_params["$or"] = [
                {"email": {"$regex": f"{search}", "$options": "i"}},
                {
                    "ledger_name": {
                        "$regex": f"{search}",
                        "$options": "i",
                    }
                },
                {
                    "parent": {
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
                {
                    "alias": {
                        "$regex": f"{search}",
                        "$options": "i",
                    }
                },
                {
                    "mailing_name": {
                        "$regex": f"{search}",
                        "$options": "i",
                    }
                },
            ]

        if state not in ["", None]:
            filter_params["$or"] = [
                {"mailing_state": {"$regex": f"{state}", "$options": "i"}},
            ]

        if parent == "Customers":
            filter_params["parent"] = {"$in": ["Debtors", "Creditors"]}
        elif parent == "Accounts":
            filter_params["parent"] = {"$in": ["Bank Accounts", "Cash-in-Hand"]}
        elif parent not in ["", None]:
            filter_params["$or"] = [
                {"parent": {"$regex": f"^{parent}", "$options": "i"}},
            ]

        sort_fields_mapping = {
            "name": "ledger_name",
            "parent": "parent",
            "city": "mailing_pincode",
            "state": "mailing_state",
            "opening_balance": "opening_balance",
            "created_at": "created_at",
            # "tax_supply_type": "tax_supply_type",
        }

        sort_field_mapped = sort_fields_mapping.get(sort.sort_field, "name")
        sort_order_value = 1 if sort.sort_order == SortingOrder.ASC else -1
        sort_criteria = {sort_field_mapped: sort_order_value}

        pipeline = []

        pipeline.extend(
            [
                {
                    "$match": {
                        "user_id": current_user_id,
                        "company_id": company_id,
                    }
                },
                {"$match": filter_params},
                {
                    "$lookup": {
                        "from": "Accounting",
                        "localField": "_id",
                        "foreignField": "ledger_id",
                        "as": "accounts",
                    }
                },
                {
                    "$addFields": {
                        "total_amount": {"$round": [{"$sum": "$accounts.amount"}, 2]}
                    },
                },
                {"$sort": sort_criteria},
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
            {
                "$match": {
                    "user_id": current_user_id,
                    "company_id": company_id,
                }
            },
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

    def generate_name_suggestions(
        self, name: str, existing_names: set = None, count: int = 10
    ) -> list:
        if existing_names is None:
            existing_names = set()

        name = normalize_name(name)
        suggestions = set()

        # Suffix-based suggestions
        for suffix in SUFFIXES:
            suggestion = f"{name} {suffix}"
            if suggestion not in existing_names:
                suggestions.add(suggestion)
            if len(suggestions) >= count:
                break

        # Add numbered versions
        i = 1
        while len(suggestions) < count:
            variant = f"{name} {str(i).zfill(2)}"
            if variant not in existing_names:
                suggestions.add(variant)
            i += 1

        return list(suggestions)[:count]

    async def get_ledger_invoices(
        self,
        search: str,
        type: str,
        company_id: str,
        ledger_id: str,
        pagination: PageRequest,
        sort: Sort,
        current_user: TokenData = Depends(get_current_user),
        start_date: str = None,
        end_date: str = None,
    ):
        start_date = start_date[:10]
        end_date = end_date[:10]
        filter_params = {
            "_id": ledger_id,
            "company_id": company_id,
            "user_id": current_user.user_id,
        }

        sort_options = {
            "voucher_number_asc": {"accounts.voucher_number": 1},
            "voucher_number_desc": {"accounts.voucher_number": -1},
            "date_asc": {"accounts.date": 1},
            "date_desc": {"accounts.date": -1},
        }

        sort_key = f"{sort.sort_field}_{'asc' if sort.sort_order == SortingOrder.ASC else 'desc'}"
        sort_stage = sort_options.get(sort_key, {"accounts.date": -1})

        pipeline = [
            {"$match": filter_params},
            {
                "$lookup": {
                    "from": "Accounting",
                    "localField": "_id",
                    "foreignField": "ledger_id",
                    "as": "accounts",
                }
            },
            {
                "$lookup": {
                    "from": "Voucher",
                    "localField": "accounts.vouchar_id",
                    "foreignField": "_id",
                    "as": "vouchars",
                }
            },
            {
                "$lookup": {
                    "from": "Accounting",
                    "localField": "vouchars._id",
                    "foreignField": "vouchar_id",
                    "as": "account_details",
                },
            },
            {
                "$addFields": {
                    "accounts": {
                        "$map": {
                            "input": "$accounts",
                            "as": "account",
                            "in": {
                                "amount": "$$account.amount",
                                "is_deemed_positive": {
                                    "$cond": [
                                        {"$lt": ["$$account.amount", 0]},
                                        True,
                                        False,
                                    ]
                                },
                                "vouchar_id": "$$account.vouchar_id",
                                "date": {
                                    "$arrayElemAt": [
                                        "$vouchars.date",
                                        {
                                            "$indexOfArray": [
                                                "$vouchars._id",
                                                "$$account.vouchar_id",
                                            ]
                                        },
                                    ]
                                },
                                "status": {
                                    "$arrayElemAt": [
                                        "$vouchars.status",
                                        {
                                            "$indexOfArray": [
                                                "$vouchars._id",
                                                "$$account.vouchar_id",
                                            ]
                                        },
                                    ]
                                },
                                "voucher_number": {
                                    "$arrayElemAt": [
                                        "$vouchars.voucher_number",
                                        {
                                            "$indexOfArray": [
                                                "$vouchars._id",
                                                "$$account.vouchar_id",
                                            ]
                                        },
                                    ]
                                },
                                "voucher_type": {
                                    "$arrayElemAt": [
                                        "$vouchars.voucher_type",
                                        {
                                            "$indexOfArray": [
                                                "$vouchars._id",
                                                "$$account.vouchar_id",
                                            ]
                                        },
                                    ]
                                },
                                "narration": {
                                    "$arrayElemAt": [
                                        "$vouchars.narration",
                                        {
                                            "$indexOfArray": [
                                                "$vouchars._id",
                                                "$$account.vouchar_id",
                                            ]
                                        },
                                    ]
                                },
                                "reference_date": {
                                    "$arrayElemAt": [
                                        "$vouchars.reference_date",
                                        {
                                            "$indexOfArray": [
                                                "$vouchars._id",
                                                "$$account.vouchar_id",
                                            ]
                                        },
                                    ]
                                },
                                "reference_number": {
                                    "$arrayElemAt": [
                                        "$vouchars.reference_number",
                                        {
                                            "$indexOfArray": [
                                                "$vouchars._id",
                                                "$$account.vouchar_id",
                                            ]
                                        },
                                    ]
                                },
                                "place_of_supply": {
                                    "$arrayElemAt": [
                                        "$vouchars.place_of_supply",
                                        {
                                            "$indexOfArray": [
                                                "$vouchars._id",
                                                "$$account.vouchar_id",
                                            ]
                                        },
                                    ]
                                },
                                "customer": {
                                    "$let": {
                                        "vars": {
                                            "other_account": {
                                                "$arrayElemAt": [
                                                    {
                                                        "$filter": {
                                                            "input": "$account_details",
                                                            "as": "ad",
                                                            "cond": {
                                                                "$and": [
                                                                    {
                                                                        "$eq": [
                                                                            "$$ad.vouchar_id",
                                                                            "$$account.vouchar_id",
                                                                        ]
                                                                    },
                                                                    {
                                                                        "$ne": [
                                                                            "$$ad.ledger_id",
                                                                            "$$account.ledger_id",
                                                                        ]
                                                                    },
                                                                ]
                                                            },
                                                        }
                                                    },
                                                    0,
                                                ]
                                            }
                                        },
                                        "in": {"$ifNull": ["$$other_account.ledger", ""]},
                                    }
                                },
                            },
                        }
                    }
                }
            },
            {
                "$addFields": {
                    "total_amount": {"$round": [{"$sum": "$accounts.amount"}, 2]}
                },
            },
            {
                "$unwind": "$accounts",
            },
            {
                "$project": {
                    "accounts": 1,
                },
            },
            {
                "$match": {
                    **(
                        {
                            "$or": [
                                {
                                    "accounts.voucher_number": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "accounts.customer": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                            ]
                        }
                        if search not in ["", None]
                        else {}
                    ),
                    **({"accounts.voucher_type": type} if type not in ["", None] else {}),
                    **(
                        {"accounts.date": {"$gte": start_date, "$lte": end_date}}
                        if start_date and end_date
                        else {}
                    ),
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

        # Transform docs to only include the 'accounts' dict for each entry
        docs = [doc["accounts"] for doc in docs]

        return PaginatedResponse(
            docs=docs,
            meta=Meta(
                page=pagination.paging.page,
                limit=pagination.paging.limit,
                total=count,
                unique=[],
            ),
        )


ledger_repo = ledgerRepo()
