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
    "Services"
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
                {"email": {"$regex": f"^{search}", "$options": "i"}},
                {
                    "ledger_name": {
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
                    "email": {
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
                {
                    "mailing_name": {
                        "$regex": f"^{search}",
                        "$options": "i",
                    }
                },
            ]

        if state not in ["", None]:
            filter_params["$or"] = [
                {"mailing_state": {"$regex": f"^{state}", "$options": "i"}},
            ]

        if parent not in ["", None]:
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
            # "gst_supply_type": "gst_supply_type",
        }

        sort_field_mapped = sort_fields_mapping.get(sort.sort_field, "name")
        sort_order_value = 1 if sort.sort_order == SortingOrder.ASC else -1
        sort_criteria = {sort_field_mapped: sort_order_value}

        pipeline = []
        match_stage = {"is_deleted": is_deleted}
        if current_user_id is not None:
            match_stage["user_id"] = current_user_id
        if company_id is not None:
            match_stage["company_id"] = company_id
        pipeline.extend(
            [
                {"$match": match_stage},
                {"$match": filter_params},
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


ledger_repo = ledgerRepo()
