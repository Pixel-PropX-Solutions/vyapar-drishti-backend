from typing import Any, List, Union
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
from datetime import datetime, timedelta
import math
import calendar


def convert_to_daily_data(docs):
    if not docs:
        return {}

    # Extract month/year from first record
    first_date = datetime.strptime(docs[0]["_id"], "%Y-%m-%d")
    month = first_date.month
    year = first_date.year

    # Prepare arrays for daily values
    sales_arr = []
    purchase_arr = []
    profit_arr = []

    total_sales = 0
    total_purchase = 0
    total_profit = 0

    for doc in docs:
        sales_val = doc["total_sales_val"]
        purchase_val = doc["total_purchase_val"]
        profit_val = doc["gross_profit"]

        sales_arr.append(sales_val)
        purchase_arr.append(purchase_val)
        profit_arr.append(profit_val)

        total_sales += sales_val
        total_purchase += purchase_val
        total_profit += profit_val

    # Build final structure
    result = {
        "month": month,
        "year": year,
        "sales": round(total_sales, 2),
        "purchase": round(total_purchase, 2),
        "profit": round(total_profit, 2),
        "data": [
            {"id": "sales", "label": "Total Sales", "data": sales_arr},
            {"id": "purchase", "label": "Total Purchase", "data": purchase_arr},
            {"id": "profit", "label": "Profit (₹)", "data": profit_arr},
        ],
    }

    return result


def transform_monthly_to_yearly(data, year):
    # Ensure 12 months slots
    months = [f"{year}-{str(m).zfill(2)}" for m in range(1, 13)]

    sales_data = []
    purchase_data = []
    profit_data = []

    # Create lookup for faster access
    lookup = {row["_id"]: row for row in data}

    for m in months:
        row = lookup.get(
            m, {"total_sales_val": 0, "total_purchase_val": 0, "gross_profit": 0}
        )
        sales_data.append(row["total_sales_val"])
        purchase_data.append(row["total_purchase_val"])
        profit_data.append(row["gross_profit"])

    result = {
        "sales": round(sum(sales_data), 2),
        "purchase": round(sum(purchase_data), 2),
        "profit": round(sum(profit_data), 2),
        "year": year,
        "data": [
            {"id": "sales", "label": "Total Sales", "data": sales_data},
            {"id": "purchase", "label": "Total Purchase", "data": purchase_data},
            {"id": "profit", "label": "Profit (₹)", "data": profit_data},
        ],
    }
    return result


def month_range(sd: datetime, ed: datetime):
    months = []
    current = datetime(sd.year, sd.month, 1)  # start of first month
    end = datetime(ed.year, ed.month, 1)  # start of last month

    while current <= end:
        months.append(current.strftime("%Y-%m"))
        # go to next month safely
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)
    return months


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
                    {"party_name": {"$regex": safe_search, "$options": "i"}},
                    {"ledger_name": {"$regex": safe_search, "$options": "i"}},
                    {"narration": {"$regex": safe_search, "$options": "i"}},
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

        # Always sort by the main field, then voucher_number as secondary
        if sort.sort_field:
            sort_stage = {
                sort.sort_field if sort.sort_field != "type" else "voucher_type": int(
                    sort.sort_order
                ),
                "voucher_number": int(sort.sort_order),
            }
        else:
            sort_stage = {"date": -1, "voucher_number": -1}

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
                    "amount": '$grand_total',
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
        category: str = "",
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
                                "$cond": [
                                    {"$gt": ["$additional_charge", 0]},
                                    {
                                        "$divide": [
                                            "$additional_charge",
                                            "$inventory_info.total_qty",
                                        ]
                                    },
                                    0,
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
                    "stock_opening_qty": {
                        "$first": {"$ifNull": ["$stock_item.opening_balance", 0]}
                    },
                    "stock_opening_val": {
                        "$first": {"$ifNull": ["$stock_item.opening_value", 0]}
                    },
                    "stock_opening_rate": {
                        "$first": {"$ifNull": ["$stock_item.opening_rate", 0]}
                    },
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
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_qty",
                                            "$opening_qty_vouchers",
                                        ]
                                    },
                                    0,
                                ]
                            },
                            2,
                        ]
                    },
                    "opening_val": {
                        "$round": [
                            {
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_val",
                                            "$opening_val_vouchers",
                                        ]
                                    },
                                    0,
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
                                "$ifNull": [
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
                                    0,
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
                                    {
                                        "$ifNull": [
                                            {"$divide": ["$opening_val", "$opening_qty"]},
                                            0,
                                        ]
                                    },
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
                                "$cond": [
                                    {"$gt": ["$additional_charge", 0]},
                                    {
                                        "$divide": [
                                            "$additional_charge",
                                            "$inventory_info.total_qty",
                                        ]
                                    },
                                    0,
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
                    "stock_opening_qty": {
                        "$first": {"$ifNull": ["$stock_item.opening_balance", 0]}
                    },
                    "stock_opening_val": {
                        "$first": {"$ifNull": ["$stock_item.opening_value", 0]}
                    },
                    "stock_opening_rate": {
                        "$first": {"$ifNull": ["$stock_item.opening_rate", 0]}
                    },
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
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_qty",
                                            "$opening_qty_vouchers",
                                        ]
                                    },
                                    0,
                                ]
                            },
                            2,
                        ]
                    },
                    "opening_val": {
                        "$round": [
                            {
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_val",
                                            "$opening_val_vouchers",
                                        ]
                                    },
                                    0,
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
                                "$ifNull": [
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
                                    0,
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
                                    {
                                        "$ifNull": [
                                            {"$divide": ["$inwards_val", "$inwards_qty"]},
                                            0,
                                        ]
                                    },
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

    async def get_analytics_data(
        self,
        year: int,
        company_id: str,
        current_user: TokenData = Depends(get_current_user),
    ):

        # Calculate start and end dates for the year
        sd = datetime(year=year, month=4, day=1)
        ed = datetime(year=year + 1, month=3, day=31, hour=23, minute=59, second=59)

        # Ensure same format as DB ("YYYY-MM-DD")
        start_date = sd.strftime("%Y-%m-%d")
        end_date = ed.strftime("%Y-%m-%d")

        match_stage = {
            "user_id": current_user.user_id,
            "company_id": company_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }

        # Compute total sales/purchase for the year
        pipeline = [
            {"$match": match_stage},
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
                                "$cond": [
                                    {"$gt": ["$additional_charge", 0]},
                                    {
                                        "$divide": [
                                            "$additional_charge",
                                            "$inventory_info.total_qty",
                                        ]
                                    },
                                    0,
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
                    "stock_opening_qty": {
                        "$first": {"$ifNull": ["$stock_item.opening_balance", 0]}
                    },
                    "stock_opening_val": {
                        "$first": {"$ifNull": ["$stock_item.opening_value", 0]}
                    },
                    "stock_opening_rate": {
                        "$first": {"$ifNull": ["$stock_item.opening_rate", 0]}
                    },
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
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_qty",
                                            "$opening_qty_vouchers",
                                        ]
                                    },
                                    0,
                                ]
                            },
                            2,
                        ]
                    },
                    "opening_val": {
                        "$round": [
                            {
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_val",
                                            "$opening_val_vouchers",
                                        ]
                                    },
                                    0,
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
                                "$ifNull": [
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
                                    0,
                                ]
                            },
                            2,
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
                    "opening_val": 1,
                    "inwards_val": 1,
                    "outwards_val": 1,
                    "closing_rate": "$avg_cost_rate",
                    "closing_val": 1,
                    "gross_profit": 1,
                }
            },
        ]

        totals_res = [doc async for doc in self.collection.aggregate(pipeline)]
        opening_val = sum((doc.get("opening_val") or 0) for doc in totals_res)
        inwards_val = sum((doc.get("inwards_val") or 0) for doc in totals_res)
        outwards_val = sum((doc.get("outwards_val") or 0) for doc in totals_res)
        closing_val = sum((doc.get("closing_val") or 0) for doc in totals_res)
        gross_profit = sum((doc.get("gross_profit") or 0) for doc in totals_res)
        profit_percent = gross_profit / outwards_val * 100 if outwards_val != 0 else 0

        return {
            "opening": round(opening_val, 2),
            "purchase": round(inwards_val, 2),
            "sales": round(outwards_val, 2),
            "current": round(closing_val, 2),
            "profit": round(gross_profit, 2),
            "profit_percent": round(profit_percent, 2),
        }

    async def get_monthly_data(
        self,
        year: int,
        company_id: str,
        current_user: TokenData = Depends(get_current_user),
    ):

        # Calculate start and end dates for the year
        sd = datetime(year=year, month=4, day=1)
        ed = datetime(year=year + 1, month=3, day=31, hour=23, minute=59, second=59)

        # Ensure same format as DB ("YYYY-MM-DD")
        start_date = sd.strftime("%Y-%m-%d")
        end_date = ed.strftime("%Y-%m-%d")

        match_stage = {
            "user_id": current_user.user_id,
            "company_id": company_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }

        # Compute total sales/purchase for the year
        pipeline_total = [
            {"$match": match_stage},
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
            # Flatten fields from inventory items
            {
                "$addFields": {
                    "item_id": "$inventory_info.items.item_id",
                    "item": "$inventory_info.items.item",
                    "quantity": "$inventory_info.items.quantity",
                    "amount": "$inventory_info.items.amount",
                    "month_only": {"$substr": ["$date", 0, 7]},
                    "is_purchase": {
                        "$cond": [{"$eq": ["$voucher_type", "Purchase"]}, 1, 0]
                    },
                    "is_sale": {"$cond": [{"$eq": ["$voucher_type", "Sales"]}, 1, 0]},
                    "total_qty": "$inventory_info.total_qty",
                    # per-unit additional charge
                    "per_unit_additional": {
                        "$cond": [
                            {"$gt": ["$inventory_info.total_qty", 0]},
                            {
                                "$cond": [
                                    {"$gt": ["$additional_charge", 0]},
                                    {
                                        "$divide": [
                                            "$additional_charge",
                                            "$inventory_info.total_qty",
                                        ]
                                    },
                                    0,
                                ]
                            },
                            0,
                        ]
                    },
                }
            },
            # Adjusted total amount including additional charges
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
            # Bring in StockItem for opening balances
            {
                "$lookup": {
                    "from": "StockItem",
                    "let": {"item_id": "$item_id"},
                    "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", "$$item_id"]}}}],
                    "as": "stock_item",
                }
            },
            {"$unwind": {"path": "$stock_item", "preserveNullAndEmptyArrays": True}},
            # Group by item + date
            {
                "$group": {
                    "_id": {"item_id": "$item_id", "date": "$month_only"},
                    "item": {"$first": "$item"},
                    "date": {"$first": "$month_only"},
                    "stock_opening_qty": {
                        "$first": {"$ifNull": ["$stock_item.opening_balance", 0]}
                    },
                    "stock_opening_val": {
                        "$first": {"$ifNull": ["$stock_item.opening_value", 0]}
                    },
                    # Opening balances adjusted by vouchers < start_date
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
                    "purchase_qty": {
                        "$sum": {"$cond": [{"$eq": ["$is_purchase", 1]}, "$quantity", 0]}
                    },
                    "purchase_val": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$is_purchase", 1]},
                                "$adj_total_amount",
                                0,
                            ]
                        }
                    },
                    "sales_qty": {
                        "$sum": {"$cond": [{"$eq": ["$is_sale", 1]}, "$quantity", 0]}
                    },
                    "sales_val": {
                        "$sum": {
                            "$cond": [{"$eq": ["$is_sale", 1]}, "$adj_total_amount", 0]
                        }
                    },
                }
            },
            # Add final opening balances
            {
                "$addFields": {
                    "opening_qty": {
                        "$round": [
                            {
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_qty",
                                            "$opening_qty_vouchers",
                                        ]
                                    },
                                    0,
                                ]
                            },
                            2,
                        ]
                    },
                    "opening_val": {
                        "$round": [
                            {
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_val",
                                            "$opening_val_vouchers",
                                        ]
                                    },
                                    0,
                                ]
                            },
                            2,
                        ]
                    },
                }
            },
            # Compute average cost including opening stock + purchases
            {
                "$addFields": {
                    "total_qty_for_cost": {"$add": ["$opening_qty", "$purchase_qty"]},
                    "total_val_for_cost": {"$add": ["$opening_val", "$purchase_val"]},
                }
            },
            {
                "$addFields": {
                    "avg_cost_rate": {
                        "$cond": [
                            {"$gt": ["$total_qty_for_cost", 0]},
                            {
                                "$round": [
                                    {
                                        "$divide": [
                                            "$total_val_for_cost",
                                            "$total_qty_for_cost",
                                        ]
                                    },
                                    2,
                                ]
                            },
                            0,
                        ]
                    }
                }
            },
            # Gross profit = sales value – (sales qty × avg cost rate)
            {
                "$addFields": {
                    "gross_profit": {
                        "$round": [
                            {
                                "$subtract": [
                                    "$sales_val",
                                    {"$multiply": ["$sales_qty", "$avg_cost_rate"]},
                                ]
                            },
                            2,
                        ]
                    }
                }
            },
            # Group by date for daily totals
            {
                "$group": {
                    "_id": "$date",
                    "total_purchase_qty": {"$sum": "$purchase_qty"},
                    "total_purchase_val": {"$sum": "$purchase_val"},
                    "total_sales_qty": {"$sum": "$sales_qty"},
                    "total_sales_val": {"$sum": "$sales_val"},
                    "gross_profit": {"$sum": "$gross_profit"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        total_result = await self.collection.aggregate(pipeline_total).to_list(None)
        months_range = month_range(sd, ed)
        data_by_month = {doc["_id"]: doc for doc in total_result}
        final_result = []

        for d in months_range:
            if d in data_by_month:
                final_result.append(data_by_month[d])
            else:
                final_result.append(
                    {
                        "_id": d,
                        "total_purchase_qty": 0,
                        "total_purchase_val": 0,
                        "total_sales_qty": 0,
                        "total_sales_val": 0,
                        "gross_profit": 0,
                    }
                )

        formatted = transform_monthly_to_yearly(final_result, 2025)
        print("formatted Result ", formatted)

        return formatted

    async def get_daily_data(
        self,
        year: int,
        month: Union[int, None],
        company_id: str,
        current_user: TokenData = Depends(get_current_user),
    ):

        # Calculate start and end dates for the year
        sd = datetime(
            year=year, month=month if month is not None else datetime.now().month, day=1
        )
        last_day = calendar.monthrange(
            int(year), int(month if month is not None else datetime.now().month)
        )[1]
        ed = datetime(
            year=int(year),
            month=int(month if month is not None else datetime.now().month),
            day=last_day,
            hour=23,
            minute=59,
            second=59,
        )

        # Ensure same format as DB ("YYYY-MM-DD")
        start_date = sd.strftime("%Y-%m-%d")
        end_date = ed.strftime("%Y-%m-%d")

        match_stage = {
            "user_id": current_user.user_id,
            "company_id": company_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }

        # Compute total sales/purchase for the year
        pipeline_total = [
            {"$match": match_stage},
            # Join inventory
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
            # Flatten fields from inventory items
            {
                "$addFields": {
                    "item_id": "$inventory_info.items.item_id",
                    "item": "$inventory_info.items.item",
                    "quantity": "$inventory_info.items.quantity",
                    "amount": "$inventory_info.items.amount",
                    "date_only": {"$substr": ["$date", 0, 10]},
                    "is_purchase": {
                        "$cond": [{"$eq": ["$voucher_type", "Purchase"]}, 1, 0]
                    },
                    "is_sale": {"$cond": [{"$eq": ["$voucher_type", "Sales"]}, 1, 0]},
                    "total_qty": "$inventory_info.total_qty",
                    # per-unit additional charge
                    "per_unit_additional": {
                        "$cond": [
                            {"$gt": ["$inventory_info.total_qty", 0]},
                            {
                                "$cond": [
                                    {"$gt": ["$additional_charge", 0]},
                                    {
                                        "$divide": [
                                            "$additional_charge",
                                            "$inventory_info.total_qty",
                                        ]
                                    },
                                    0,
                                ]
                            },
                            0,
                        ]
                    },
                }
            },
            # Adjusted total amount including additional charges
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
            # Bring in StockItem for opening balances
            {
                "$lookup": {
                    "from": "StockItem",
                    "let": {"item_id": "$item_id"},
                    "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", "$$item_id"]}}}],
                    "as": "stock_item",
                }
            },
            {"$unwind": {"path": "$stock_item", "preserveNullAndEmptyArrays": True}},
            # Group by item + date
            {
                "$group": {
                    "_id": {"item_id": "$item_id", "date": "$date_only"},
                    "item": {"$first": "$item"},
                    "date": {"$first": "$date_only"},
                    "stock_opening_qty": {
                        "$first": {"$ifNull": ["$stock_item.opening_balance", 0]}
                    },
                    "stock_opening_val": {
                        "$first": {"$ifNull": ["$stock_item.opening_value", 0]}
                    },
                    # Opening balances adjusted by vouchers < start_date
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
                    "purchase_qty": {
                        "$sum": {"$cond": [{"$eq": ["$is_purchase", 1]}, "$quantity", 0]}
                    },
                    "purchase_val": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$is_purchase", 1]},
                                "$adj_total_amount",
                                0,
                            ]
                        }
                    },
                    "sales_qty": {
                        "$sum": {"$cond": [{"$eq": ["$is_sale", 1]}, "$quantity", 0]}
                    },
                    "sales_val": {
                        "$sum": {
                            "$cond": [{"$eq": ["$is_sale", 1]}, "$adj_total_amount", 0]
                        }
                    },
                }
            },
            # Add final opening balances
            {
                "$addFields": {
                    "opening_qty": {
                        "$round": [
                            {
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_qty",
                                            "$opening_qty_vouchers",
                                        ]
                                    },
                                    0,
                                ]
                            },
                            2,
                        ]
                    },
                    "opening_val": {
                        "$round": [
                            {
                                "$ifNull": [
                                    {
                                        "$add": [
                                            "$stock_opening_val",
                                            "$opening_val_vouchers",
                                        ]
                                    },
                                    0,
                                ]
                            },
                            2,
                        ]
                    },
                }
            },
            # Compute average cost including opening stock + purchases
            {
                "$addFields": {
                    "total_qty_for_cost": {"$add": ["$opening_qty", "$purchase_qty"]},
                    "total_val_for_cost": {"$add": ["$opening_val", "$purchase_val"]},
                }
            },
            {
                "$addFields": {
                    "avg_cost_rate": {
                        "$cond": [
                            {"$gt": ["$total_qty_for_cost", 0]},
                            {
                                "$round": [
                                    {
                                        "$divide": [
                                            "$total_val_for_cost",
                                            "$total_qty_for_cost",
                                        ]
                                    },
                                    2,
                                ]
                            },
                            0,
                        ]
                    }
                }
            },
            # Gross profit = sales value – (sales qty × avg cost rate)
            {
                "$addFields": {
                    "gross_profit": {
                        "$round": [
                            {
                                "$subtract": [
                                    "$sales_val",
                                    {"$multiply": ["$sales_qty", "$avg_cost_rate"]},
                                ]
                            },
                            2,
                        ]
                    }
                }
            },
            # Group by date for daily totals
            {
                "$group": {
                    "_id": "$date",
                    "total_purchase_qty": {"$sum": "$purchase_qty"},
                    "total_purchase_val": {"$sum": "$purchase_val"},
                    "total_sales_qty": {"$sum": "$sales_qty"},
                    "total_sales_val": {"$sum": "$sales_val"},
                    "gross_profit": {"$sum": "$gross_profit"},
                }
            },
            {"$sort": {"_id": 1}},
        ]

        total_result = await self.collection.aggregate(pipeline_total).to_list(None)

        date_range = [
            (sd + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range((ed - sd).days + 1)
        ]

        # Map aggregation results by date
        data_by_date = {doc["_id"]: doc for doc in total_result}

        # Fill missing dates with zeros
        final_result = []
        for d in date_range:
            if d in data_by_date:
                final_result.append(data_by_date[d])
            else:
                final_result.append(
                    {
                        "_id": d,
                        "total_purchase_qty": 0,
                        "total_purchase_val": 0,
                        "total_sales_qty": 0,
                        "total_sales_val": 0,
                        "gross_profit": 0,
                    }
                )
        daily_data = convert_to_daily_data(final_result)
        print("daily_data in voucher repo", daily_data)
        return daily_data


vouchar_repo = VoucherRepo()
