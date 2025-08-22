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
# import pprint


class VoucherRepo(BaseMongoDbCrud[VoucherDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "Voucher",
            unique_attributes=[
                "user_id",
                "company_id",
                "party_name",
                "voucher_type",
                "voucher_number",
            ],
        )

    async def new(self, sub: Voucher):
        return await self.save(VoucherDB(**sub.model_dump()))

    async def viewAllVouchar(
        self,
        search: str,
        type: str,
        company_id: str,
        pagination: PageRequest,
        sort: Sort,
        current_user: TokenData = Depends(get_current_user),
        # is_deleted: bool = False,
        start_date: str = "",
        end_date: str = "",
    ):
        filter_params = {
            "user_id": current_user.user_id,
            "company_id": company_id,
        }

        if search not in ["", None]:
            try:
                safe_search = re.escape(search)
                filter_params["$or"] = [
                    {"voucher_number": {"$regex": safe_search, "$options": "i"}},
                    {"voucher_type": {"$regex": safe_search, "$options": "i"}},
                    {"group": {"$regex": safe_search, "$options": "i"}},
                    {"description": {"$regex": safe_search, "$options": "i"}},
                    {"party_name": {"$regex": safe_search, "$options": "i"}},
                ]
            except re.error:
                pass

        if type in ["Invoices", "Transactions"]:
            if type == "Invoices":
                filter_params["voucher_type"] = {"$in": ["Sales", "Purchase"]}
            else:
                filter_params["voucher_type"] = {"$in": ["Payment", "Receipt"]}
        elif type not in ["", None]:
            filter_params["voucher_type"] = type

        if start_date not in ["", None] and end_date not in ["", None]:
            startDate = start_date[0:10]
            endDate = end_date[0:10]
            filter_params["date"] = {"$gte": startDate, "$lte": endDate}

        sort_stage = {sort.sort_field: int(sort.sort_order)} if sort.sort_field else {"date": -1}

        pipeline = [
            {"$match": filter_params},
            {
                "$lookup": {
                    "from": "Ledger",
                    "localField": "party_name_id",
                    "foreignField": "_id",
                    "as": "party",
                }
            },
            {"$unwind": {"path": "$party", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Accounting",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "accounting",
                }
            },
            {
                "$addFields": {
                    "debit": {
                        "$sum": {
                            "$map": {
                                "input": "$accounting",
                                "as": "entry",
                                "in": {
                                    "$cond": [
                                        {"$gt": ["$$entry.amount", 0]},
                                        "$$entry.amount",
                                        0,
                                    ]
                                },
                            }
                        }
                    },
                    "credit": {
                        "$sum": {
                            "$map": {
                                "input": "$accounting",
                                "as": "entry",
                                "in": {
                                    "$cond": [
                                        {"$lt": ["$$entry.amount", 0]},
                                        {"$abs": "$$entry.amount"},
                                        0,
                                    ]
                                },
                            }
                        }
                    },
                }
            },
            {
                "$addFields": {
                    "ledger_entries": {
                        "$map": {
                            "input": {
                                "$filter": {
                                    "input": "$accounting",
                                    "as": "entry",
                                    "cond": {
                                        "$eq": ["$$entry.ledger_id", "$party_name_id"]
                                    },
                                }
                            },
                            "as": "entry",
                            "in": {
                                "ledgername": "$$entry.ledger",
                                "amount": "$$entry.amount",
                                "is_deemed_positive": {
                                    "$cond": [{"$lt": ["$$entry.amount", 0]}, True, False]
                                },
                                "amount_absolute": {"$abs": "$$entry.amount"},
                            },
                        }
                    }
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "date": 1,
                    "voucher_number": 1,
                    "voucher_type": 1,
                    "voucher_type_id": 1,
                    "party_name": 1,
                    "party_name_id": 1,
                    "narration": 1,
                    "paid_amount": 1,
                    "amount": {"$arrayElemAt": ["$ledger_entries.amount", 0]},
                    "balance_type": 1,
                    "ledger_name": {"$arrayElemAt": ["$ledger_entries.ledgername", 0]},
                    "is_deemed_positive": {
                        "$arrayElemAt": ["$ledger_entries.is_deemed_positive", 0]
                    },
                    "created_at": 1,
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
        # pprint.pprint(docs, indent=2, width=120)

        return PaginatedResponse(
            docs=docs,
            meta=Meta(
                page=pagination.paging.page,
                limit=pagination.paging.limit,
                total=count,
                unique=[],
            ),
        )

    async def viewTimeline(
        self,
        search: str,
        type: str,
        party_name: str,
        company_id: str,
        pagination: PageRequest,
        sort: Sort,
        current_user: TokenData = Depends(get_current_user),
        # is_deleted: bool = False,
        start_date: datetime = None,
        end_date: datetime = None,
    ):
        filter_params = {
            "user_id": current_user.user_id,
            "company_id": company_id,
        }

        if type not in ["", None]:
            filter_params["voucher_type"] = type

        if start_date not in ["", None] and end_date not in ["", None]:
            filter_params["date"] = {"$gte": start_date, "$lte": end_date}

        sort_options = {
            "voucher_number_asc": {"voucher_number": 1},
            "voucher_number_desc": {"voucher_number": -1},
            "created_at_asc": {"created_at": 1},
            "created_at_desc": {"created_at": -1},
            "date_asc": {"date": 1},
            "date_desc": {"date": -1},
        }

        sort_key = f"{sort.sort_field}_{'asc' if sort.sort_order == SortingOrder.ASC else 'desc'}"
        sort_stage = sort_options.get(sort_key, {"date": -1, "created_at": -1})

        pipeline = [
            {"$match": filter_params},
            {
                "$lookup": {
                    "from": "Inventory",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "inventory",
                }
            },
            {"$unwind": "$inventory"},
            {
                "$addFields": {
                    "inventory.company_id": "$company_id",
                    "inventory.user_id": "$user_id",
                    "inventory.date": "$date",
                    "inventory.voucher_number": "$voucher_number",
                    "inventory.voucher_type": "$voucher_type",
                    "inventory.narration": "$narration",
                    "inventory.party_name": "$party_name",
                    "inventory.place_of_supply": "$place_of_supply",
                    "inventory.created_at": "$created_at",
                    "inventory.updated_at": "$updated_at",
                }
            },
            {"$replaceRoot": {"newRoot": "$inventory"}},
            {"$sort": sort_stage},
            {
                "$match": {
                    **(
                        {
                            "$or": [
                                {
                                    "voucher_number": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "party_name": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "item": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                            ]
                        }
                        if search not in ["", None]
                        else {}
                    ),
                    **(
                        {"party_name": party_name} if party_name not in ["", None] else {}
                    ),
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

        party_name_pipeline = [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "company_id": company_id,
                }
            },
            {
                "$lookup": {
                    "from": "Inventory",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "inventory",
                }
            },
            {"$unwind": "$inventory"},
            {
                "$addFields": {
                    "inventory.company_id": "$company_id",
                    "inventory.user_id": "$user_id",
                    "inventory.date": "$date",
                    "inventory.voucher_number": "$voucher_number",
                    "inventory.voucher_type": "$voucher_type",
                    "inventory.narration": "$narration",
                    "inventory.party_name": "$party_name",
                    "inventory.place_of_supply": "$place_of_supply",
                    "inventory.created_at": "$created_at",
                    "inventory.updated_at": "$updated_at",
                }
            },
            {"$replaceRoot": {"newRoot": "$inventory"}},
            {"$group": {"_id": "$party_name"}},
            {"$project": {"_id": 0, "party_name": "$_id"}},
            {"$sort": {"party_name": 1}},
        ]

        res = [doc async for doc in self.collection.aggregate(pipeline)]
        party_res = [doc async for doc in self.collection.aggregate(party_name_pipeline)]
        docs = res[0]["docs"]
        unique_parties = [entry["party_name"] for entry in party_res]

        count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0

        return PaginatedResponse(
            docs=docs,
            meta=Meta(
                page=pagination.paging.page,
                limit=pagination.paging.limit,
                total=count,
                unique=unique_parties,
            ),
        )


vouchar_repo = VoucherRepo()


# from fastapi import Depends
# from app.Config import ENV_PROJECT
# from app.database.models.Vouchar import Voucher, VoucherDB
# from app.oauth2 import get_current_user
# from app.schema.token import TokenData
# from .crud.base_mongo_crud import BaseMongoDbCrud
# from app.database.repositories.crud.base import (
#     PageRequest,
#     Meta,
#     PaginatedResponse,
#     SortingOrder,
#     Sort,
#     Page,
# )
# import re
# from datetime import datetime


# class VoucherRepo(BaseMongoDbCrud[VoucherDB]):
#     def __init__(self):
#         super().__init__(
#             ENV_PROJECT.MONGO_DATABASE,
#             "Voucher",
#             unique_attributes=[
#                 "voucher_number",
#                 "user_id",
#                 "voucher_type",
#                 "company_id",
#                 "party_name",
#             ],
#         )

#     async def new(self, sub: Voucher):
#         return await self.save(VoucherDB(**sub.model_dump()))

#     async def viewAllVouchar(
#         self,
#         search: str,
#         type: str,
#         company_id: str,
#         # group: str,
#         pagination: PageRequest,
#         sort: Sort,
#         current_user: TokenData = Depends(get_current_user),
#         is_deleted: bool = False,
#         start_date: datetime = None,
#         end_date: datetime = None,
#         skip: int = 0,
#     ):
#         filter_params = {
#             "user_id": current_user.user_id,
#             # "is_deleted": is_deleted,
#             "company_id": company_id,
#         }
#         # Filter by search term
#         if search not in ["", None]:
#             try:
#                 safe_search = re.escape(search)
#                 filter_params["$or"] = [
#                     {"name": {"$regex": safe_search, "$options": "i"}},
#                     {"alias_name": {"$regex": safe_search, "$options": "i"}},
#                     {"voucher_type": {"$regex": safe_search, "$options": "i"}},
#                     {"group": {"$regex": safe_search, "$options": "i"}},
#                     {"description": {"$regex": safe_search, "$options": "i"}},
#                 ]
#             except re.error:
#                 # If regex is invalid, ignore search filter or handle as needed
#                 pass

#         if type not in ["", None]:
#             filter_params["voucher_type"] = type

#         if start_date and end_date:
#             filter_params["created_at"] = {"$gte": start_date, "$lte": end_date}

#         # if group not in ["", None]:
#         #     filter_params["group"] = group

#         # Define sorting logic
#         sort_options = {
#             "name_asc": {"name": 1},
#             "name_desc": {"name": -1},
#             # "price_asc": {"selling_price": 1},
#             # "price_desc": {"selling_price": -1},
#             "created_at_asc": {"created_at": 1},
#             "created_at_desc": {"created_at": -1},
#         }

#         # Construct sorting key
#         sort_key = f"{sort.sort_field}_{'asc' if sort.sort_order == SortingOrder.ASC else 'desc'}"

#         sort_stage = sort_options.get(sort_key, {"created_at": 1})

#         pipeline = [
#             {"$match": filter_params},
#             {
#                 "$lookup": {
#                     "from": "Ledger",
#                     "localField": "party_name",
#                     "foreignField": "name",
#                     "as": "party",
#                 }
#             },
#             {"$unwind": {"path": "$party", "preserveNullAndEmptyArrays": True}},
#             {
#                 "$lookup": {
#                     "from": "Inventory",
#                     "localField": "_id",
#                     "foreignField": "vouchar_id",
#                     "as": "inventory",
#                 }
#             },
#             {"$unwind": {"path": "$inventory", "preserveNullAndEmptyArrays": True}},
#             {
#                 "$lookup": {
#                     "from": "Accounting",
#                     "localField": "_id",
#                     "foreignField": "vouchar_id",
#                     "as": "accounting",
#                 }
#             },
#             {
#                 "$group": {
#                     "_id": "$_id",
#                     "voucher_number": {"$first": "$voucher_number"},
#                     "date": {"$first": "$date"},
#                     "voucher_type": {"$first": "$voucher_type"},
#                     "accounting": {"$push": "$accounting"},
#                     "inventory": {"$first": "$inventory"},
#                     "party": {"$first": "$party"},
#                 }
#             },
#             {
#                 "$addFields": {
#                     "amount": {
#                         "$add": [{"$ifNull": ["$debit", 0]}, {"$ifNull": ["$credit", 0]}]
#                     },
#                     "balance_type": {
#                         "$cond": [
#                             {"$gt": ["$debit", "$credit"]},
#                             "Dr",
#                             {"$cond": [{"$gt": ["$credit", "$debit"]}, "Cr", "Balanced"]},
#                         ]
#                     },
#                 }
#             },
#             {
#                 "$project": {
#                     "_id": 1,
#                     "date": 1,
#                     "voucher_number": 1,
#                     "voucher_type": 1,
#                     "ledger_name": 1,
#                     "debit": 1,
#                     "credit": 1,
#                     "amount": 1,
#                     "balance_type": 1,
#                     "narration": 1,
#                 }
#             },
#             {
#                 "$facet": {
#                     "docs": [
#                         {"$skip": (pagination.paging.page - 1) * pagination.paging.limit},
#                         {"$limit": pagination.paging.limit},
#                     ],
#                     "count": [{"$count": "count"}],
#                 }
#             },
#         ]

#         unique_categories_pipeline = [
#             {
#                 "$match": {
#                     "user_id": current_user.user_id,
#                     "is_deleted": is_deleted,
#                     "company_id": company_id,
#                 }
#             },
#             {"$group": {"_id": "$category"}},
#             {"$project": {"_id": 0, "category": "$_id"}},
#             {"$sort": {"category": 1}},
#         ]

#         unique_groups_pipeline = [
#             {
#                 "$match": {
#                     "user_id": current_user.user_id,
#                     "is_deleted": is_deleted,
#                     "company_id": company_id,
#                 }
#             },
#             {"$group": {"_id": "$group"}},
#             {"$project": {"_id": 0, "group": "$_id"}},
#             {"$sort": {"group": 1}},
#         ]

#         res = [doc async for doc in self.collection.aggregate(pipeline)]

#         # categories_res = [
#         #     doc
#         #     async for doc in category_repo.collection.aggregate(
#         #         unique_categories_pipeline
#         #     )
#         # ]

#         # group_res = [
#         #     doc
#         #     async for doc in group_repo.collection.aggregate(unique_groups_pipeline)
#         # ]
#         docs = res[0]["docs"]
#         count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0

#         # Extract unique categories and groups
#         # unique_categories = [entry["category"] for entry in categories_res]

#         # unique_groups = [entry["group"] for entry in group_res]

#         return PaginatedResponse(
#             docs=docs,
#             meta=Meta(
#                 page=pagination.paging.page,
#                 limit=pagination.paging.limit,
#                 total=count,
#                 unique=[],
#             ),
#         )


# vouchar_repo = VoucherRepo()
