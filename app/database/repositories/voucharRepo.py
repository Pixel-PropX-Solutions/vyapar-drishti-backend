from typing import Any, List
from fastapi import Depends
from pydantic import BaseModel
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
import math


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

        sort_stage = (
            {sort.sort_field: int(sort.sort_order)} if sort.sort_field else {"date": -1}
        )

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
        company_id: str,
        pagination: PageRequest,
        sort: Sort,
        category: str = '',
        current_user: TokenData = Depends(get_current_user),
        start_date: datetime = None,
        end_date: datetime = None,
    ):
        start_date = start_date[:10]
        end_date = end_date[:10]
        filter_params = {
            "user_id": current_user.user_id,
            "company_id": company_id,
        }

        if start_date not in ["", None] and end_date not in ["", None]:
            filter_params["date"] = {"$gte": start_date, "$lte": end_date}

        pipeline = [
            {"$match": filter_params},
            # Join with Inventory and calculate total_qty for distributing additional_charge
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"vouchar_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$vouchar_id", "$$vouchar_id"]}}},
                        {
                            "$group": {
                                "_id": None,
                                "items": {"$push": "$$ROOT"},
                                "total_qty": {"$sum": "$quantity"},
                            }
                        },
                    ],
                    "as": "inventory_info",
                }
            },
            {"$unwind": {"path": "$inventory_info"}},
            {"$unwind": {"path": "$inventory_info.items"}},
            # Flatten inventory + voucher fields
            {
                "$addFields": {
                    "item": "$inventory_info.items.item",
                    "item_id": "$inventory_info.items.item_id",
                    "unit": "$inventory_info.items.unit",
                    "quantity": "$inventory_info.items.quantity",
                    "rate": "$inventory_info.items.rate",
                    "amount": "$inventory_info.items.amount",
                    "is_purchase": {
                        "$cond": [{"$eq": ["$voucher_type", "Purchase"]}, 1, 0]
                    },
                    "is_sale": {"$cond": [{"$eq": ["$voucher_type", "Sales"]}, 1, 0]},
                    "date": "$date",
                    "total_qty": "$inventory_info.total_qty",
                    # per-unit additional charge
                    "per_unit_additional": {
                        "$cond": [
                            {"$gt": ["$inventory_info.total_qty", 0]},
                            {
                                "$divide": [
                                    "$additional_charge",
                                    "$inventory_info.total_qty",
                                ]
                            },
                            0,
                        ]
                    },
                }
            },
            # Adjusted total amount (item.total_amount + distributed additional charge)
            {
                "$addFields": {
                    "per_item_additional": {
                        "$multiply": ["$per_unit_additional", "$quantity"]
                    },
                    "adj_total_amount": {
                        "$add": [
                            "$inventory_info.items.total_amount",
                            {"$multiply": ["$per_unit_additional", "$quantity"]},
                        ]
                    },
                }
            },
            # 🔹 Join with StockItem to fetch master opening balances
            {
                "$lookup": {
                    "from": "StockItem",
                    "let": {"item_id": "$item_id"},
                    "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", "$$item_id"]}}}],
                    "as": "stock_item",
                }
            },
            {"$unwind": {"path": "$stock_item", "preserveNullAndEmptyArrays": True}},
            # Group per item
            {
                "$group": {
                    "_id": "$item_id",
                    "item_id": {"$first": "$item_id"},
                    "item": {"$first": "$item"},
                    "unit": {"$first": "$unit"},
                    "stock_opening_qty": {"$first": "$stock_item.opening_balance"},
                    "stock_opening_val": {"$first": "$stock_item.opening_value"},
                    "stock_opening_rate": {"$first": "$stock_item.opening_rate"},
                    # Opening balances (before start_date, from vouchers)
                    "opening_qty_vouchers": {
                        "$sum": {
                            "$cond": [
                                {"$lt": ["$date", start_date]},
                                {
                                    "$cond": [
                                        {"$eq": ["$is_purchase", 1]},
                                        "$quantity",
                                        {"$multiply": [-1, "$quantity"]},
                                    ]
                                },
                                0,
                            ]
                        }
                    },
                    "opening_val_vouchers": {
                        "$sum": {
                            "$cond": [
                                {"$lt": ["$date", start_date]},
                                {
                                    "$cond": [
                                        {"$eq": ["$is_purchase", 1]},
                                        "$adj_total_amount",
                                        {"$multiply": [-1, "$adj_total_amount"]},
                                    ]
                                },
                                0,
                            ]
                        }
                    },
                    # Inwards (Purchases in date range)
                    "inwards_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$date", start_date]},
                                        {"$lte": ["$date", end_date]},
                                        {"$eq": ["$is_purchase", 1]},
                                    ]
                                },
                                "$quantity",
                                0,
                            ]
                        }
                    },
                    "inwards_val": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$date", start_date]},
                                        {"$lte": ["$date", end_date]},
                                        {"$eq": ["$is_purchase", 1]},
                                    ]
                                },
                                "$adj_total_amount",
                                0,
                            ]
                        }
                    },
                    # Outwards (Sales in date range)
                    "outwards_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$date", start_date]},
                                        {"$lte": ["$date", end_date]},
                                        {"$eq": ["$is_sale", 1]},
                                    ]
                                },
                                "$quantity",
                                0,
                            ]
                        }
                    },
                    "outwards_val": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$date", start_date]},
                                        {"$lte": ["$date", end_date]},
                                        {"$eq": ["$is_sale", 1]},
                                    ]
                                },
                                "$adj_total_amount",
                                0,
                            ]
                        }
                    },
                }
            },
            # 🔹 Add StockItem opening + voucher opening together
            {
                "$addFields": {
                    "opening_qty": {
                        "$round": [
                            {
                                "$add": [
                                    "$stock_opening_qty",
                                    "$opening_qty_vouchers",
                                ]
                            },
                            2,
                        ]
                    },
                    "opening_val": {
                        "$round": [
                            {
                                "$add": [
                                    "$stock_opening_val",
                                    "$opening_val_vouchers",
                                ]
                            },
                            2,
                        ]
                    },
                }
            },
            # Recalculate opening_rate with new qty/val
            {
                "$addFields": {
                    "closing_qty": {
                        "$round": [
                            {
                                "$subtract": [
                                    {
                                        "$add": [
                                            "$opening_qty",
                                            "$inwards_qty",
                                        ]
                                    },
                                    "$outwards_qty",
                                ]
                            },
                            2,
                        ]
                    },
                    "opening_rate": {
                        "$cond": [
                            {"$eq": ["$opening_qty", 0]},
                            {"$ifNull": ["$stock_opening_rate", 0]},
                            {
                                "$round": [
                                    {"$divide": ["$opening_val", "$opening_qty"]},
                                    2,
                                ]
                            },
                        ]
                    },
                    "inwards_rate": {
                        "$cond": [
                            {"$eq": ["$inwards_qty", 0]},
                            0,
                            {
                                "$round": [
                                    {"$divide": ["$inwards_val", "$inwards_qty"]},
                                    2,
                                ]
                            },
                        ]
                    },
                    "outwards_rate": {
                        "$cond": [
                            {"$eq": ["$outwards_qty", 0]},
                            0,
                            {
                                "$round": [
                                    {"$divide": ["$outwards_val", "$outwards_qty"]},
                                    2,
                                ]
                            },
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    # Gross Profit = OutwardsVal – (OutwardsQty × AvgCostRate)
                    "avg_cost_rate": {
                        "$cond": [
                            {"$gt": [{"$add": ["$opening_qty", "$inwards_qty"]}, 0]},
                            {
                                "$round": [
                                    {
                                        "$divide": [
                                            {"$add": ["$opening_val", "$inwards_val"]},
                                            {"$add": ["$opening_qty", "$inwards_qty"]},
                                        ]
                                    },
                                    2,
                                ]
                            },
                            0,
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    "gross_profit": {
                        "$round": [
                            {
                                "$multiply": [
                                    "$outwards_qty",
                                    {"$subtract": ["$outwards_rate", "$avg_cost_rate"]},
                                ]
                            },
                            2,
                        ]
                    },
                    "profit_percent": {
                        "$cond": [
                            {"$gt": ["$outwards_val", 0]},
                            {
                                "$round": [
                                    {
                                        "$multiply": [
                                            {
                                                "$divide": [
                                                    {
                                                        "$multiply": [
                                                            "$outwards_qty",
                                                            {
                                                                "$subtract": [
                                                                    "$outwards_rate",
                                                                    "$avg_cost_rate",
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    "$outwards_val",
                                                ]
                                            },
                                            100,
                                        ]
                                    },
                                    2,
                                ]
                            },
                            0,
                        ]
                    },
                    "closing_val": {"$multiply": ["$closing_qty", "$avg_cost_rate"]},
                }
            },
            {
                "$project": {
                    "item_id": 1,
                    "item": 1,
                    "unit": 1,
                    "opening_qty": 1,
                    "opening_rate": 1,
                    "opening_val": 1,
                    "inwards_qty": 1,
                    "inwards_rate": 1,
                    "inwards_val": 1,
                    "outwards_qty": 1,
                    "outwards_rate": 1,
                    "outwards_val": 1,
                    "closing_qty": 1,
                    "closing_rate": "$avg_cost_rate",
                    "closing_val": 1,
                    "gross_profit": 1,
                    "profit_percent": 1,
                }
            },
            {"$sort": {"item": -1 if sort.sort_order == SortingOrder.ASC else 1}},
            {
                "$match": {
                    **(
                        {
                            "$or": [
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

        meta_pipeline = [
            {"$match": filter_params},
            # Join with Inventory and calculate total_qty for distributing additional_charge
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"vouchar_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$vouchar_id", "$$vouchar_id"]}}},
                        {
                            "$group": {
                                "_id": None,
                                "items": {"$push": "$$ROOT"},
                                "total_qty": {"$sum": "$quantity"},
                            }
                        },
                    ],
                    "as": "inventory_info",
                }
            },
            {"$unwind": {"path": "$inventory_info"}},
            {"$unwind": {"path": "$inventory_info.items"}},
            # Flatten inventory + voucher fields
            {
                "$addFields": {
                    "item": "$inventory_info.items.item",
                    "item_id": "$inventory_info.items.item_id",
                    "unit": "$inventory_info.items.unit",
                    "quantity": "$inventory_info.items.quantity",
                    "rate": "$inventory_info.items.rate",
                    "amount": "$inventory_info.items.amount",
                    "is_purchase": {
                        "$cond": [{"$eq": ["$voucher_type", "Purchase"]}, 1, 0]
                    },
                    "is_sale": {"$cond": [{"$eq": ["$voucher_type", "Sales"]}, 1, 0]},
                    "date": "$date",
                    "total_qty": "$inventory_info.total_qty",
                    # per-unit additional charge
                    "per_unit_additional": {
                        "$cond": [
                            {"$gt": ["$inventory_info.total_qty", 0]},
                            {
                                "$divide": [
                                    "$additional_charge",
                                    "$inventory_info.total_qty",
                                ]
                            },
                            0,
                        ]
                    },
                }
            },
            # Adjusted total amount (item.total_amount + distributed additional charge)
            {
                "$addFields": {
                    "per_item_additional": {
                        "$multiply": ["$per_unit_additional", "$quantity"]
                    },
                    "adj_total_amount": {
                        "$add": [
                            "$inventory_info.items.total_amount",
                            {"$multiply": ["$per_unit_additional", "$quantity"]},
                        ]
                    },
                }
            },
            # 🔹 Join with StockItem to fetch master opening balances
            {
                "$lookup": {
                    "from": "StockItem",
                    "let": {"item_id": "$item_id"},
                    "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", "$$item_id"]}}}],
                    "as": "stock_item",
                }
            },
            {"$unwind": {"path": "$stock_item", "preserveNullAndEmptyArrays": True}},
            # Group per item
            {
                "$group": {
                    "_id": "$item_id",
                    "item_id": {"$first": "$item_id"},
                    "item": {"$first": "$item"},
                    "unit": {"$first": "$unit"},
                    "stock_opening_qty": {"$first": "$stock_item.opening_balance"},
                    "stock_opening_val": {"$first": "$stock_item.opening_value"},
                    "stock_opening_rate": {"$first": "$stock_item.opening_rate"},
                    # Opening balances (before start_date, from vouchers)
                    "opening_qty_vouchers": {
                        "$sum": {
                            "$cond": [
                                {"$lt": ["$date", start_date]},
                                {
                                    "$cond": [
                                        {"$eq": ["$is_purchase", 1]},
                                        "$quantity",
                                        {"$multiply": [-1, "$quantity"]},
                                    ]
                                },
                                0,
                            ]
                        }
                    },
                    "opening_val_vouchers": {
                        "$sum": {
                            "$cond": [
                                {"$lt": ["$date", start_date]},
                                {
                                    "$cond": [
                                        {"$eq": ["$is_purchase", 1]},
                                        "$adj_total_amount",
                                        {"$multiply": [-1, "$adj_total_amount"]},
                                    ]
                                },
                                0,
                            ]
                        }
                    },
                    # Inwards (Purchases in date range)
                    "inwards_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$date", start_date]},
                                        {"$lte": ["$date", end_date]},
                                        {"$eq": ["$is_purchase", 1]},
                                    ]
                                },
                                "$quantity",
                                0,
                            ]
                        }
                    },
                    "inwards_val": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$date", start_date]},
                                        {"$lte": ["$date", end_date]},
                                        {"$eq": ["$is_purchase", 1]},
                                    ]
                                },
                                "$adj_total_amount",
                                0,
                            ]
                        }
                    },
                    # Outwards (Sales in date range)
                    "outwards_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$date", start_date]},
                                        {"$lte": ["$date", end_date]},
                                        {"$eq": ["$is_sale", 1]},
                                    ]
                                },
                                "$quantity",
                                0,
                            ]
                        }
                    },
                    "outwards_val": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$date", start_date]},
                                        {"$lte": ["$date", end_date]},
                                        {"$eq": ["$is_sale", 1]},
                                    ]
                                },
                                "$adj_total_amount",
                                0,
                            ]
                        }
                    },
                }
            },
            # 🔹 Add StockItem opening + voucher opening together
            {
                "$addFields": {
                    "opening_qty": {
                        "$round": [
                            {
                                "$add": [
                                    "$stock_opening_qty",
                                    "$opening_qty_vouchers",
                                ]
                            },
                            2,
                        ]
                    },
                    "opening_val": {
                        "$round": [
                            {
                                "$add": [
                                    "$stock_opening_val",
                                    "$opening_val_vouchers",
                                ]
                            },
                            2,
                        ]
                    },
                }
            },
            # Recalculate opening_rate with new qty/val
            {
                "$addFields": {
                    "closing_qty": {
                        "$round": [
                            {
                                "$add": [
                                    "$opening_qty",
                                    "$inwards_qty",
                                    {"$multiply": [-1, "$outwards_qty"]},
                                ]
                            },
                            2,
                        ]
                    },
                    "inwards_rate": {
                        "$cond": [
                            {"$eq": ["$inwards_qty", 0]},
                            0,
                            {
                                "$round": [
                                    {"$divide": ["$inwards_val", "$inwards_qty"]},
                                    2,
                                ]
                            },
                        ]
                    },
                    "outwards_rate": {
                        "$cond": [
                            {"$eq": ["$outwards_qty", 0]},
                            0,
                            {
                                "$round": [
                                    {"$divide": ["$outwards_val", "$outwards_qty"]},
                                    2,
                                ]
                            },
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    # Gross Profit = OutwardsVal – (OutwardsQty × AvgCostRate)
                    "avg_cost_rate": {
                        "$cond": [
                            {"$gt": [{"$add": ["$opening_qty", "$inwards_qty"]}, 0]},
                            {
                                "$round": [
                                    {
                                        "$divide": [
                                            {"$add": ["$opening_val", "$inwards_val"]},
                                            {"$add": ["$opening_qty", "$inwards_qty"]},
                                        ]
                                    },
                                    2,
                                ]
                            },
                            0,
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    "gross_profit": {
                        "$round": [
                            {
                                "$multiply": [
                                    "$outwards_qty",
                                    {"$subtract": ["$outwards_rate", "$avg_cost_rate"]},
                                ]
                            },
                            2,
                        ]
                    },
                    "closing_val": {"$multiply": ["$closing_qty", "$avg_cost_rate"]},
                }
            },
            {
                "$project": {
                    "item_id": 1,
                    "opening_qty": 1,
                    "opening_rate": 1,
                    "opening_val": 1,
                    "inwards_qty": 1,
                    "inwards_rate": 1,
                    "inwards_val": 1,
                    "outwards_qty": 1,
                    "outwards_rate": 1,
                    "outwards_val": 1,
                    "closing_qty": 1,
                    "closing_rate": "$avg_cost_rate",
                    "closing_val": 1,
                    "gross_profit": 1,
                }
            },
        ]

        res = [doc async for doc in self.collection.aggregate(pipeline)]
        totals_res = [doc async for doc in self.collection.aggregate(meta_pipeline)]
        # print("totals_res", totals_res)
        docs = res[0]["docs"]
        opening_val = sum((doc.get("opening_val") or 0) for doc in totals_res)
        inwards_val = sum((doc.get("inwards_val") or 0) for doc in totals_res)
        outwards_val = sum((doc.get("outwards_val") or 0) for doc in totals_res)
        closing_val = sum((doc.get("closing_val") or 0) for doc in totals_res)
        gross_profit = sum((doc.get("gross_profit") or 0) for doc in totals_res)
        profit_percent = gross_profit / outwards_val * 100 if outwards_val != 0 else 0

        count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0

        class Meta2(Page):
            total: int
            opening_val: float
            inwards_val: float
            outwards_val: float
            closing_val: float
            gross_profit: float
            profit_percent: float

        class PaginatedResponse2(BaseModel):
            docs: List[Any]
            meta: Meta2

        return PaginatedResponse2(
            docs=docs,
            meta=Meta2(
                page=pagination.paging.page,
                limit=pagination.paging.limit,
                total=count,
                opening_val=opening_val,
                inwards_val=inwards_val,
                outwards_val=outwards_val,
                closing_val=closing_val,
                gross_profit=gross_profit,
                profit_percent=profit_percent,
            ),
        )


vouchar_repo = VoucherRepo()
