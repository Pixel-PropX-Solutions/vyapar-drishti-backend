import asyncio
from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.StockItem import StockItem, StockItemDB
from app.database.repositories.categoryRepo import category_repo
from app.database.repositories.inventoryGroupRepo import inventory_group_repo
from app.oauth2 import get_current_user
from app.schema.token import TokenData
from .crud.base_mongo_crud import BaseMongoDbCrud
from app.database.repositories.crud.base import (
    PageRequest,
    PaginatedResponse,
    SortingOrder,
    Sort,
    Page,
)
from pydantic import BaseModel
from typing import List, Any
import re
from datetime import datetime, timedelta


async def fetch_all(cursor):
    return [doc async for doc in cursor]


class StockItemRepo(BaseMongoDbCrud[StockItemDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "StockItem",
            unique_attributes=["stock_item_name", "user_id", "company_id", "unit"],
        )

    async def new(self, sub: StockItem):
        return await self.save(StockItemDB(**sub.model_dump()))

    async def viewAllProduct(
        self,
        search: str,
        category: str,
        company_id: str,
        group: str,
        pagination: PageRequest,
        sort: Sort,
        stock_status: str = "",
        current_user: TokenData = Depends(get_current_user),
        # is_deleted: bool = False,
    ):
        # Stats filter: only user_id, is_deleted, company_id

        stats_filter_params = {
            "user_id": current_user.user_id,
            "is_deleted": False,
            "company_id": company_id,
        }

        stats_pipeline = [
            {"$match": stats_filter_params},
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"stock_item_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$item_id", "$$stock_item_id"]}}}
                    ],
                    "as": "inventory_entries",
                }
            },
            {
                "$unwind": {
                    "path": "$inventory_entries",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$lookup": {
                    "from": "Voucher",
                    "let": {"inventory_voucher_id": "$inventory_entries.vouchar_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$_id", "$$inventory_voucher_id"]}}}
                    ],
                    "as": "voucher",
                }
            },
            {"$unwind": {"path": "$voucher", "preserveNullAndEmptyArrays": True}},
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "stock_item_name": {"$first": "$stock_item_name"},
                    "unit": {"$first": "$unit"},
                    "category": {"$first": "$category"},
                    "alias_name": {"$first": "$alias_name"},
                    "image": {"$first": "$image"},
                    "description": {"$first": "$description"},
                    "hsn_code": {"$first": "$hsn_code"},
                    "low_stock_alert": {"$first": "$low_stock_alert"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                    "group": {"$first": "$group"},
                    "opening_balance": {"$first": "$opening_balance"},
                    "purchase_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.quantity",
                                0,
                            ]
                        }
                    },
                    "purchase_value": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                {
                                    "$abs": {
                                        "$multiply": [
                                            "$inventory_entries.quantity",
                                            "$inventory_entries.rate",
                                        ]
                                    },
                                },
                                0,
                            ]
                        }
                    },
                    "sales_qty": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.quantity"},
                                0,
                            ]
                        }
                    },
                    "sales_value": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {
                                    "$abs": {
                                        "$multiply": [
                                            "$inventory_entries.quantity",
                                            "$inventory_entries.rate",
                                        ]
                                    },
                                },
                                0,
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "low_stock_alert": 1,
                    "purchase_qty": 1,
                    "sales_qty": 1,
                    "purchase_value": 1,
                    "sales_value": 1,
                    "opening_balance": 1,
                    "current_stock": {
                        "$subtract": [
                            {
                                "$add": [
                                    {"$ifNull": ["$purchase_qty", 0]},
                                    {"$ifNull": ["$opening_balance", 0]},
                                ]
                            },
                            {"$ifNull": ["$sales_qty", 0]},
                        ]
                    },
                    "negative_stock": {
                        "$cond": [
                            {
                                "$lt": [
                                    {
                                        "$subtract": [
                                            {
                                                "$add": [
                                                    {"$ifNull": ["$purchase_qty", 0]},
                                                    {"$ifNull": ["$opening_balance", 0]},
                                                ]
                                            },
                                            {"$ifNull": ["$sales_qty", 0]},
                                        ]
                                    },
                                    0,
                                ]
                            },
                            1,
                            0,
                        ]
                    },
                    "zero_stock": {
                        "$cond": [
                            {
                                "$eq": [
                                    {
                                        "$subtract": [
                                            {
                                                "$add": [
                                                    {"$ifNull": ["$purchase_qty", 0]},
                                                    {"$ifNull": ["$opening_balance", 0]},
                                                ]
                                            },
                                            {"$ifNull": ["$sales_qty", 0]},
                                        ]
                                    },
                                    0,
                                ]
                            },
                            1,
                            0,
                        ]
                    },
                    "low_stock": {
                        "$cond": [
                            {
                                "$and": [
                                    {
                                        "$gt": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            0,
                                        ]
                                    },
                                    {
                                        "$lt": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            "$low_stock_alert",
                                        ]
                                    },
                                ]
                            },
                            1,
                            0,
                        ]
                    },
                    "positive_stock": {
                        "$cond": [
                            {
                                "$gte": [
                                    {
                                        "$subtract": [
                                            {
                                                "$add": [
                                                    {"$ifNull": ["$purchase_qty", 0]},
                                                    {"$ifNull": ["$opening_balance", 0]},
                                                ]
                                            },
                                            {"$ifNull": ["$sales_qty", 0]},
                                        ]
                                    },
                                    "$low_stock_alert",
                                ]
                            },
                            1,
                            0,
                        ]
                    },
                }
            },
        ]

        # Now build filter_params for docs pipeline
        filter_params = {
            "user_id": current_user.user_id,
            "is_deleted": False,
            "company_id": company_id,
        }

        if category not in ["", None]:
            filter_params["category"] = category

        if group not in ["", None]:
            filter_params["group"] = group

        sort_options = {
            "stock_item_name_asc": {"stock_item_name": 1},
            "stock_item_name_desc": {"stock_item_name": -1},
            "current_stock_asc": {"current_stock": 1},
            "current_stock_desc": {"current_stock": -1},
            "last_restock_date_asc": {"last_restock_date": 1},
            "last_restock_date_desc": {"last_restock_date": -1},
            "unit_asc": {"unit": 1},
            "unit_desc": {"unit": -1},
        }

        sort_key = f"{sort.sort_field}_{'asc' if sort.sort_order == SortingOrder.ASC else 'desc'}"
        sort_stage = sort_options.get(sort_key, {"created_at": 1})

        stock_status_dict = {}
        if stock_status == "zero":
            stock_status_dict["$in"] = ["zero", "negative"]
        elif stock_status not in ["", None]:
            stock_status_dict = stock_status

        pipeline = [
            {"$match": filter_params},
            {
                "$lookup": {
                    "from": "Category",
                    "localField": "category_id",
                    "foreignField": "_id",
                    "as": "category",
                }
            },
            {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Group",
                    "localField": "group_id",
                    "foreignField": "_id",
                    "as": "group",
                }
            },
            {"$unwind": {"path": "$group", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"stock_item_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$item_id", "$$stock_item_id"]}}}
                    ],
                    "as": "inventory_entries",
                }
            },
            {
                "$unwind": {
                    "path": "$inventory_entries",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$lookup": {
                    "from": "Voucher",
                    "let": {"inventory_voucher_id": "$inventory_entries.vouchar_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$_id", "$$inventory_voucher_id"]}}}
                    ],
                    "as": "voucher",
                }
            },
            {
                "$unwind": {
                    "path": "$voucher",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "stock_item_name": {"$first": "$stock_item_name"},
                    "unit": {"$first": "$unit"},
                    "category": {"$first": "$category"},
                    "alias_name": {"$first": "$alias_name"},
                    "image": {"$first": "$image"},
                    "description": {"$first": "$description"},
                    "hsn_code": {"$first": "$hsn_code"},
                    "low_stock_alert": {"$first": "$low_stock_alert"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                    "group": {"$first": "$group"},
                    "opening_balance": {"$first": "$opening_balance"},
                    "opening_value": {"$first": "$opening_value"},
                    "purchase_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.quantity",
                                0,
                            ]
                        }
                    },
                    "purchase_value": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.amount",
                                0,
                            ]
                        }
                    },
                    "sales_qty": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.quantity"},
                                0,
                            ]
                        }
                    },
                    "last_restock_date": {
                        "$max": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$voucher.date",
                                None,
                            ]
                        }
                    },
                    "sales_value": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.amount"},
                                0,
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "stock_item_name": 1,
                    "company_id": 1,
                    "user_id": 1,
                    "unit": 1,
                    "alias_name": 1,
                    "category": {"$ifNull": ["$category.category_name", None]},
                    "group": {"$ifNull": ["$group.inventory_group_name", None]},
                    "image": 1,
                    "description": 1,
                    "hsn_code": 1,
                    "low_stock_alert": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "current_stock": {
                        "$subtract": [
                            {
                                "$add": [
                                    {"$ifNull": ["$purchase_qty", 0]},
                                    {"$ifNull": ["$opening_balance", 0]},
                                ]
                            },
                            {"$ifNull": ["$sales_qty", 0]},
                        ]
                    },
                    "avg_purchase_rate": {
                        "$cond": [
                            {"$gt": ["$purchase_qty", 0]},
                            {"$divide": ["$purchase_value", "$purchase_qty"]},
                            0,
                        ]
                    },
                    "avg_sale_rate": {
                        "$cond": [
                            {"$gt": ["$sales_qty", 0]},
                            {"$divide": ["$sales_value", "$sales_qty"]},
                            0,
                        ]
                    },
                    "purchase_qty": "$purchase_qty",
                    "purchase_value": {
                        "$add": [
                            {"$ifNull": ["$purchase_value", 0]},
                            {"$ifNull": ["$opening_value", 0]},
                        ]
                    },
                    "sales_qty": "$sales_qty",
                    "sales_value": "$sales_value",
                    "last_restock_date": "$last_restock_date",
                    "stock_status": {
                        "$switch": {
                            "branches": [
                                {
                                    "case": {
                                        "$lt": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            0,
                                        ]
                                    },
                                    "then": "negative",
                                },
                                {
                                    "case": {
                                        "$eq": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            0,
                                        ]
                                    },
                                    "then": "zero",
                                },
                                {
                                    "case": {
                                        "$and": [
                                            {
                                                "$gt": [
                                                    {
                                                        "$subtract": [
                                                            {
                                                                "$add": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$purchase_qty",
                                                                            0,
                                                                        ]
                                                                    },
                                                                    {
                                                                        "$ifNull": [
                                                                            "$opening_balance",
                                                                            0,
                                                                        ]
                                                                    },
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$sales_qty",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    0,
                                                ]
                                            },
                                            {
                                                "$lt": [
                                                    {
                                                        "$subtract": [
                                                            {
                                                                "$add": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$purchase_qty",
                                                                            0,
                                                                        ]
                                                                    },
                                                                    {
                                                                        "$ifNull": [
                                                                            "$opening_balance",
                                                                            0,
                                                                        ]
                                                                    },
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$sales_qty",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    "$low_stock_alert",
                                                ]
                                            },
                                        ]
                                    },
                                    "then": "low",
                                },
                                {
                                    "case": {
                                        "$gte": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            "$low_stock_alert",
                                        ]
                                    },
                                    "then": "positive",
                                },
                            ],
                            "default": None,
                        }
                    },
                }
            },
            {
                "$match": {
                    **(
                        {
                            "$or": [
                                {
                                    "stock_item_name": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "description": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "category": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "group": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "alias_name": {
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
                        {"stock_status": stock_status_dict}
                        if stock_status not in ["", None]
                        else {}
                    ),
                }
            },
            {"$sort": sort_stage},
        ]

        pipeline.append(
            {
                "$facet": {
                    "docs": [
                        {"$skip": (pagination.paging.page - 1) * pagination.paging.limit},
                        {"$limit": pagination.paging.limit},
                    ],
                    "count": [{"$count": "count"}],
                }
            }
        )

        unique_categories_pipeline = [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                    "company_id": company_id,
                }
            },
            {"$group": {"_id": "$category_name"}},
            {"$project": {"_id": 0, "category": "$_id"}},
            {"$sort": {"category": 1}},
        ]

        unique_groups_pipeline = [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                    "company_id": company_id,
                }
            },
            {"$group": {"_id": "$inventory_group_name"}},
            {"$project": {"_id": 0, "group": "$_id"}},
            {"$sort": {"group": 1}},
        ]

        # Run stats pipeline first (no search/category/group filters)
        response = await asyncio.gather(
            fetch_all(self.collection.aggregate(stats_pipeline)),
            fetch_all(self.collection.aggregate(pipeline)),
            fetch_all(category_repo.collection.aggregate(unique_categories_pipeline)),
            fetch_all(inventory_group_repo.collection.aggregate(unique_groups_pipeline)),
        )
        stats_res = response[0]
        res = response[1]
        categories_res = response[2]
        groups_res = response[3]

        docs = res[0]["docs"]
        count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0
        unique_categories = [entry["category"] for entry in categories_res]
        unique_groups = [entry["group"] for entry in groups_res]

        # Aggregate stats for all products of user in company
        purchase_value = sum((doc.get("purchase_value") or 0) for doc in stats_res)
        sales_value = sum((doc.get("sales_value") or 0) for doc in stats_res)
        positive_stock = sum((doc.get("positive_stock") or 0) for doc in stats_res)
        negative_stock = sum((doc.get("negative_stock") or 0) for doc in stats_res)
        zero_stock = sum((doc.get("zero_stock") or 0) for doc in stats_res)
        low_stock = sum((doc.get("low_stock") or 0) for doc in stats_res)

        class Meta1(Page):
            total: int
            unique_categories: List[Any]
            unique_groups: List[Any]
            purchase_value: float = None
            sale_value: float = None
            positive_stock: float = None
            negative_stock: float = None
            low_stock: float = None

        class PaginatedResponse1(BaseModel):
            docs: List[Any]
            meta: Meta1

        return PaginatedResponse1(
            docs=docs,
            meta=Meta1(
                page=pagination.paging.page,
                limit=pagination.paging.limit,
                total=count,
                sale_value=sales_value,
                purchase_value=purchase_value,
                positive_stock=positive_stock,
                negative_stock=negative_stock + zero_stock,
                low_stock=low_stock,
                unique_categories=unique_categories,
                unique_groups=unique_groups,
            ),
        )

    async def viewInventoryItems(
        self,
        search: str,
        category: str,
        group: str,
        company_id: str,
        pagination: PageRequest,
        sort: Sort,
        stock_status: str = "",
        current_user: TokenData = Depends(get_current_user),
    ):
        # Now build filter_params for docs pipeline
        filter_params = {
            "user_id": current_user.user_id,
            "is_deleted": False,
            "company_id": company_id,
        }

        if category not in ["", None]:
            filter_params["category"] = category

        if group not in ["", None]:
            filter_params["group"] = group

        sort_options = {
            "stock_item_name_asc": {"stock_item_name": 1},
            "stock_item_name_desc": {"stock_item_name": -1},
            "current_stock_asc": {"current_stock": 1},
            "current_stock_desc": {"current_stock": -1},
            "last_restock_date_asc": {"last_restock_date": 1},
            "last_restock_date_desc": {"last_restock_date": -1},
        }
        sort_key = f"{sort.sort_field}_{'asc' if sort.sort_order == SortingOrder.ASC else 'desc'}"
        sort_stage = sort_options.get(sort_key, {"created_at": 1})

        stock_status_dict = {}
        if stock_status == "zero":
            stock_status_dict["$in"] = ["zero", "negative"]
        elif stock_status not in ["", None]:
            stock_status_dict = stock_status

        pipeline = [
            {"$match": filter_params},
            {
                "$lookup": {
                    "from": "Category",
                    "localField": "category_id",
                    "foreignField": "_id",
                    "as": "category",
                }
            },
            {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Group",
                    "localField": "group_id",
                    "foreignField": "_id",
                    "as": "group",
                }
            },
            {"$unwind": {"path": "$group", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"stock_item_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$item_id", "$$stock_item_id"]}}}
                    ],
                    "as": "inventory_entries",
                }
            },
            {
                "$unwind": {
                    "path": "$inventory_entries", "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$lookup": {
                    "from": "Voucher",
                    "let": {"inventory_voucher_id": "$inventory_entries.vouchar_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$_id", "$$inventory_voucher_id"]}}}
                    ],
                    "as": "voucher",
                }
            },
            {
                "$unwind": {
                    "path": "$voucher", "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "stock_item_name": {"$first": "$stock_item_name"},
                    "unit": {"$first": "$unit"},
                    "category": {"$first": "$category"},
                    "alias_name": {"$first": "$alias_name"},
                    "image": {"$first": "$image"},
                    "description": {"$first": "$description"},
                    "hsn_code": {"$first": "$hsn_code"},
                    "low_stock_alert": {"$first": "$low_stock_alert"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                    "group": {"$first": "$group"},
                    "opening_balance": {"$first": "$opening_balance"},
                    "opening_value": {"$first": "$opening_value"},
                    "purchase_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.quantity",
                                0,
                            ]
                        }
                    },
                    "purchase_value": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.amount",
                                0,
                            ]
                        }
                    },
                    "sales_qty": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.quantity"},
                                0,
                            ]
                        }
                    },
                    "last_restock_date": {
                        "$max": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$voucher.date",
                                None,
                            ]
                        }
                    },
                    "sales_value": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.amount"},
                                0,
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "stock_item_name": 1,
                    "company_id": 1,
                    "user_id": 1,
                    "unit": 1,
                    "alias_name": 1,
                    "category": {"$ifNull": ["$category.category_name", None]},
                    "group": {"$ifNull": ["$group.inventory_group_name", None]},
                    "image": 1,
                    "description": 1,
                    "hsn_code": 1,
                    "low_stock_alert": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "current_stock": {
                        "$subtract": [
                            {
                                "$add": [
                                    {"$ifNull": ["$purchase_qty", 0]},
                                    {"$ifNull": ["$opening_balance", 0]},
                                ]
                            },
                            {"$ifNull": ["$sales_qty", 0]},
                        ]
                    },
                    "avg_purchase_rate": {
                        "$cond": [
                            {"$gt": ["$purchase_qty", 0]},
                            {"$divide": ["$purchase_value", "$purchase_qty"]},
                            0,
                        ]
                    },
                    "avg_sale_rate": {
                        "$cond": [
                            {"$gt": ["$sales_qty", 0]},
                            {"$divide": ["$sales_value", "$sales_qty"]},
                            0,
                        ]
                    },
                    "purchase_qty": "$purchase_qty",
                    "purchase_value": "$purchase_value",
                    "sales_qty": "$sales_qty",
                    "sales_value": "$sales_value",
                    "last_restock_date": "$last_restock_date",
                    "stock_status": {
                        "$switch": {
                            "branches": [
                                {
                                    "case": {
                                        "$lt": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            0,
                                        ]
                                    },
                                    "then": "negative",
                                },
                                {
                                    "case": {
                                        "$eq": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            0,
                                        ]
                                    },
                                    "then": "zero",
                                },
                                {
                                    "case": {
                                        "$and": [
                                            {
                                                "$gt": [
                                                    {
                                                        "$subtract": [
                                                            {
                                                                "$add": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$purchase_qty",
                                                                            0,
                                                                        ]
                                                                    },
                                                                    {
                                                                        "$ifNull": [
                                                                            "$opening_balance",
                                                                            0,
                                                                        ]
                                                                    },
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$sales_qty",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    0,
                                                ]
                                            },
                                            {
                                                "$lt": [
                                                    {
                                                        "$subtract": [
                                                            {
                                                                "$add": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$purchase_qty",
                                                                            0,
                                                                        ]
                                                                    },
                                                                    {
                                                                        "$ifNull": [
                                                                            "$opening_balance",
                                                                            0,
                                                                        ]
                                                                    },
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$sales_qty",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    "$low_stock_alert",
                                                ]
                                            },
                                        ]
                                    },
                                    "then": "low",
                                },
                                {
                                    "case": {
                                        "$gte": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            "$low_stock_alert",
                                        ]
                                    },
                                    "then": "positive",
                                },
                            ],
                            "default": None,
                        }
                    },
                }
            },
            {
                "$match": {
                    **(
                        {
                            "$or": [
                                {
                                    "stock_item_name": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "description": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "category": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "group": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "alias_name": {
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
                        {"stock_status": stock_status_dict}
                        if stock_status not in ["", None]
                        else {}
                    ),
                }
            },
            {"$sort": sort_stage},
        ]

        pipeline.append(
            {
                "$facet": {
                    "docs": [
                        {"$skip": (pagination.paging.page - 1) * pagination.paging.limit},
                        {"$limit": pagination.paging.limit},
                    ],
                    "count": [{"$count": "count"}],
                }
            }
        )

        unique_categories_pipeline = [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                    "company_id": company_id,
                }
            },
            {"$group": {"_id": "$category_name"}},
            {"$project": {"_id": 0, "category": "$_id"}},
            {"$sort": {"category": 1}},
        ]

        unique_groups_pipeline = [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                    "company_id": company_id,
                }
            },
            {"$group": {"_id": "$inventory_group_name"}},
            {"$project": {"_id": 0, "group": "$_id"}},
            {"$sort": {"group": 1}},
        ]

        response = await asyncio.gather(
            fetch_all(self.collection.aggregate(pipeline)),
            fetch_all(category_repo.collection.aggregate(unique_categories_pipeline)),
            fetch_all(inventory_group_repo.collection.aggregate(unique_groups_pipeline)),
        )

        res = response[0]
        categories_res = response[1]
        groups_res = response[2]

        docs = res[0]["docs"]
        count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0
        unique_categories = [entry["category"] for entry in categories_res]
        unique_groups = [entry["group"] for entry in groups_res]

        class Meta1(Page):
            total: int
            unique_categories: List[Any]
            unique_groups: List[Any]

        class PaginatedResponse1(BaseModel):
            docs: List[Any]
            meta: Meta1

        return PaginatedResponse1(
            docs=docs,
            meta=Meta1(
                page=pagination.paging.page,
                limit=pagination.paging.limit,
                total=count,
                unique_categories=unique_categories,
                unique_groups=unique_groups,
            ),
        )

    async def viewInventoryStats(
        self,
        company_id: str,
        current_user: TokenData = Depends(get_current_user),
    ):
        # Stats filter: only user_id, is_deleted, company_id
        stats_filter_params = {
            "user_id": current_user.user_id,
            "company_id": company_id,
        }

        stats_pipeline = [
            {"$match": stats_filter_params},
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"stock_item_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$item_id", "$$stock_item_id"]}}}
                    ],
                    "as": "inventory_entries",
                }
            },
            {
                "$unwind": {
                    "path": "$inventory_entries",  "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$lookup": {
                    "from": "Voucher",
                    "let": {"inventory_voucher_id": "$inventory_entries.vouchar_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$_id", "$$inventory_voucher_id"]}}}
                    ],
                    "as": "voucher",
                }
            },
            {
                "$unwind": {
                    "path": "$voucher",  "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "stock_item_name": {"$first": "$stock_item_name"},
                    "unit": {"$first": "$unit"},
                    "category": {"$first": "$category"},
                    "alias_name": {"$first": "$alias_name"},
                    "image": {"$first": "$image"},
                    "description": {"$first": "$description"},
                    "hsn_code": {"$first": "$hsn_code"},
                    "low_stock_alert": {"$first": "$low_stock_alert"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                    "group": {"$first": "$group"},
                    "opening_balance": {"$first": "$opening_balance"},
                    "purchase_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.quantity",
                                0,
                            ]
                        }
                    },
                    "purchase_value": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                {
                                    "$abs": {
                                        "$multiply": [
                                            "$inventory_entries.quantity",
                                            "$inventory_entries.rate",
                                        ]
                                    },
                                },
                                0,
                            ]
                        }
                    },
                    "sales_qty": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.quantity"},
                                0,
                            ]
                        }
                    },
                    "sales_value": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {
                                    "$abs": {
                                        "$multiply": [
                                            "$inventory_entries.quantity",
                                            "$inventory_entries.rate",
                                        ]
                                    },
                                },
                                0,
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "low_stock_alert": 1,
                    "purchase_qty": 1,
                    "sales_qty": 1,
                    "purchase_value": 1,
                    "sales_value": 1,
                    "opening_balance": 1,
                    "current_stock": {
                        "$subtract": [
                            {
                                "$add": [
                                    {"$ifNull": ["$purchase_qty", 0]},
                                    {"$ifNull": ["$opening_balance", 0]},
                                ]
                            },
                            {"$ifNull": ["$sales_qty", 0]},
                        ]
                    },
                    "negative_stock": {
                        "$cond": [
                            {
                                "$lt": [
                                    {
                                        "$subtract": [
                                            {
                                                "$add": [
                                                    {"$ifNull": ["$purchase_qty", 0]},
                                                    {"$ifNull": ["$opening_balance", 0]},
                                                ]
                                            },
                                            {"$ifNull": ["$sales_qty", 0]},
                                        ]
                                    },
                                    0,
                                ]
                            },
                            1,
                            0,
                        ]
                    },
                    "zero_stock": {
                        "$cond": [
                            {
                                "$eq": [
                                    {
                                        "$subtract": [
                                            {
                                                "$add": [
                                                    {"$ifNull": ["$purchase_qty", 0]},
                                                    {"$ifNull": ["$opening_balance", 0]},
                                                ]
                                            },
                                            {"$ifNull": ["$sales_qty", 0]},
                                        ]
                                    },
                                    0,
                                ]
                            },
                            1,
                            0,
                        ]
                    },
                    "low_stock": {
                        "$cond": [
                            {
                                "$and": [
                                    {
                                        "$gt": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            0,
                                        ]
                                    },
                                    {
                                        "$lt": [
                                            {
                                                "$subtract": [
                                                    {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$purchase_qty",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$opening_balance",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$sales_qty", 0]},
                                                ]
                                            },
                                            "$low_stock_alert",
                                        ]
                                    },
                                ]
                            },
                            1,
                            0,
                        ]
                    },
                    "positive_stock": {
                        "$cond": [
                            {
                                "$gte": [
                                    {
                                        "$subtract": [
                                            {
                                                "$add": [
                                                    {"$ifNull": ["$purchase_qty", 0]},
                                                    {"$ifNull": ["$opening_balance", 0]},
                                                ]
                                            },
                                            {"$ifNull": ["$sales_qty", 0]},
                                        ]
                                    },
                                    "$low_stock_alert",
                                ]
                            },
                            1,
                            0,
                        ]
                    },
                }
            },
        ]

        # Run stats pipeline first (no search/category/group filters)
        stats_res = [doc async for doc in self.collection.aggregate(stats_pipeline)]

        # Aggregate stats for all products of user in company
        purchase_value = sum((doc.get("purchase_value") or 0) for doc in stats_res)
        sales_value = sum((doc.get("sales_value") or 0) for doc in stats_res)
        positive_stock = sum((doc.get("positive_stock") or 0) for doc in stats_res)
        negative_stock = sum((doc.get("negative_stock") or 0) for doc in stats_res)
        zero_stock = sum((doc.get("zero_stock") or 0) for doc in stats_res)
        low_stock = sum((doc.get("low_stock") or 0) for doc in stats_res)

        return {
            "sale_value": sales_value,
            "purchase_value": purchase_value,
            "positive_stock": positive_stock,
            "negative_stock": negative_stock,
            "zero_stock": zero_stock,
            "low_stock": low_stock,
        }

    async def view_all_stock_items(
        self,
        search: str,
        category: str,
        company_id: str,
        group: str,
        pagination: PageRequest,
        sort: Sort,
        current_user: TokenData = Depends(get_current_user),
        # is_deleted: bool = False,
    ):
        filter_params = {
            "user_id": current_user.user_id,
            "is_deleted": False,
            "company_id": company_id,
        }
        # Filter by search term
        if search not in ["", None]:
            try:
                safe_search = re.escape(search)
                filter_params["$or"] = [
                    {"stock_item_name": {"$regex": safe_search, "$options": "i"}},
                    {"alias_name": {"$regex": safe_search, "$options": "i"}},
                    {"category": {"$regex": safe_search, "$options": "i"}},
                    {"group": {"$regex": safe_search, "$options": "i"}},
                    {"description": {"$regex": safe_search, "$options": "i"}},
                ]
            except re.error:
                # If regex is invalid, ignore search filter or handle as needed
                pass

        if category not in ["", None]:
            filter_params["category"] = category

        if group not in ["", None]:
            filter_params["group"] = group

        # Define sorting logic
        sort_options = {
            "stock_item_name_asc": {"stock_item_name": 1},
            "stock_item_name_desc": {"stock_item_name": -1},
            "current_stock_asc": {"current_stock": 1},
            "current_stock_desc": {"current_stock": -1},
            "last_restock_date_asc": {"last_restock_date": 1},
            "last_restock_date_desc": {"last_restock_date": -1},
            "unit_asc": {"unit": 1},
            "unit_desc": {"unit": -1},
        }

        # Construct sorting key
        sort_key = f"{sort.sort_field}_{'asc' if sort.sort_order == SortingOrder.ASC else 'desc'}"

        sort_stage = sort_options.get(sort_key, {"created_at": 1})

        pipeline = [
            {"$match": filter_params},
            {
                "$lookup": {
                    "from": "Category",
                    "let": {"category_id": "$category_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$_id", "$$category_id"]}}}
                    ],
                    "as": "category",
                }
            },
            {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Group",
                    "let": {"group_id": "$group_id"},
                    "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", "$$group_id"]}}}],
                    "as": "group",
                }
            },
            {"$unwind": {"path": "$group", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"stock_item_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$item_id", "$$stock_item_id"]}}}
                    ],
                    "as": "inventory_entries",
                }
            },
            {
                "$unwind": {
                    "path": "$inventory_entries",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$lookup": {
                    "from": "Voucher",
                    "let": {"inventory_voucher_id": "$inventory_entries.vouchar_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$_id", "$$inventory_voucher_id"]}}}
                    ],
                    "as": "voucher",
                }
            },
            {"$unwind": {"path": "$voucher", "preserveNullAndEmptyArrays": True}},
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "stock_item_name": {"$first": "$stock_item_name"},
                    "unit": {"$first": "$unit"},
                    "category": {"$first": "$category"},
                    "alias_name": {"$first": "$alias_name"},
                    "image": {"$first": "$image"},
                    "description": {"$first": "$description"},
                    "hsn_code": {"$first": "$hsn_code"},
                    "opening_balance": {"$first": "$opening_balance"},
                    "opening_rate": {"$first": "$opening_rate"},
                    "opening_value": {"$first": "$opening_value"},
                    "low_stock_alert": {"$first": "$low_stock_alert"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                    "group": {"$first": "$group"},
                    "purchase_qty": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.quantity",
                                0,
                            ]
                        }
                    },
                    "purchase_value": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {"$toLower": "$voucher.voucher_type"},
                                        "purchase",
                                    ]
                                },
                                "$inventory_entries.amount",
                                0,
                            ]
                        }
                    },
                    "sales_qty": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.quantity"},
                                0,
                            ]
                        }
                    },
                    "sales_value": {
                        "$sum": {
                            "$cond": [
                                {"$eq": [{"$toLower": "$voucher.voucher_type"}, "sales"]},
                                {"$abs": "$inventory_entries.amount"},
                                0,
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "stock_item_name": 1,
                    "company_id": 1,
                    "user_id": 1,
                    "unit": 1,
                    "alias_name": 1,
                    "category": {"$ifNull": ["$category.category_name", None]},
                    "group": {"$ifNull": ["$group.inventory_group_name", None]},
                    "image": 1,
                    "description": 1,
                    "hsn_code": 1,
                    "opening_balance": {"$round": ["$opening_balance", 2]},
                    "opening_rate": {"$round": ["$opening_rate", 2]},
                    "opening_value": {"$round": ["$opening_value", 2]},
                    "low_stock_alert": {"$round": ["$low_stock_alert", 2]},
                    "created_at": 1,
                    "updated_at": 1,
                    "current_stock": {
                        "$round": [
                            {
                                "$subtract": [
                                    {
                                        "$add": [
                                            {"$ifNull": ["$purchase_qty", 0]},
                                            {"$ifNull": ["$opening_balance", 0]},
                                        ]
                                    },
                                    {"$ifNull": ["$sales_qty", 0]},
                                ]
                            },
                            2,
                        ]
                    },
                    "purchase_qty": {"$round": ["$purchase_qty", 2]},
                    "purchase_value": {"$round": ["$purchase_value", 2]},
                    "avg_purchase_rate": {
                        "$round": [
                            {
                                "$cond": [
                                    {
                                        "$gt": [
                                            {
                                                "$add": [
                                                    {"$ifNull": ["$purchase_qty", 0]},
                                                    {"$ifNull": ["$opening_balance", 0]},
                                                ]
                                            },
                                            0,
                                        ]
                                    },
                                    {
                                        "$divide": [
                                            {
                                                "$add": [
                                                    {"$ifNull": ["$purchase_value", 0]},
                                                    {"$ifNull": ["$opening_value", 0]},
                                                ]
                                            },
                                            {
                                                "$add": [
                                                    {"$ifNull": ["$purchase_qty", 0]},
                                                    {"$ifNull": ["$opening_balance", 0]},
                                                ]
                                            },
                                        ]
                                    },
                                    0,
                                ]
                            },
                            2,
                        ]
                    },
                    "sales_qty": {"$round": ["$sales_qty", 2]},
                    "sales_value": {"$round": ["$sales_value", 2]},
                    "avg_sales_rate": {
                        "$round": [
                            {
                                "$cond": [
                                    {"$gt": ["$sales_qty", 0]},
                                    {"$divide": ["$sales_value", "$sales_qty"]},
                                    0,
                                ]
                            },
                            2,
                        ]
                    },
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

        unique_categories_pipeline = [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                    "company_id": company_id,
                }
            },
            {"$group": {"_id": "$category_name"}},
            {"$project": {"_id": 0, "category": "$_id"}},
            {"$sort": {"category": 1}},
        ]

        unique_groups_pipeline = [
            {
                "$match": {
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                    "company_id": company_id,
                }
            },
            {"$group": {"_id": "$inventory_group_name"}},
            {"$project": {"_id": 0, "group": "$_id"}},
            {"$sort": {"group": 1}},
        ]

        response = await asyncio.gather(
            fetch_all(self.collection.aggregate(pipeline)),
            fetch_all(category_repo.collection.aggregate(unique_categories_pipeline)),
            fetch_all(inventory_group_repo.collection.aggregate(unique_groups_pipeline)),
        )
        res = response[0]
        categories_res = response[1]
        group_res = response[2]

        docs = res[0]["docs"]
        count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0

        # Extract unique categories and groups
        unique_categories = [entry["category"] for entry in categories_res]

        unique_groups = [entry["group"] for entry in group_res]

        class Meta2(Page):
            total: int
            unique_groups: List[Any]
            unique_categories: List[Any]

        class PaginatedResponse2(BaseModel):
            docs: List[Any]
            meta: Meta2

        return PaginatedResponse2(
            docs=docs,
            meta=Meta2(
                page=pagination.paging.page,
                limit=pagination.paging.limit,
                total=count,
                unique_categories=unique_categories,
                unique_groups=unique_groups,
            ),
        )

    async def viewProductTimeline(
        self,
        product_id: str,
        company_id: str,
        current_user: TokenData = Depends(get_current_user),
    ):
        pipeline = [
            {"$match": {"_id": product_id}},
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"item_id": product_id},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$item_id", "$$item_id"]}}},
                        {
                            "$lookup": {
                                "from": "Voucher",
                                "let": {"voucher_id": "$vouchar_id"},
                                "pipeline": [
                                    {
                                        "$match": {
                                            "$expr": {"$eq": ["$_id", "$$voucher_id"]}
                                        }
                                    }
                                ],
                                "as": "voucher",
                            }
                        },
                        {
                            "$unwind": {
                                "path": "$voucher",
                                "preserveNullAndEmptyArrays": True,
                            }
                        },
                        {
                            "$addFields": {
                                "date": "$voucher.date",
                                "voucher_number": "$voucher.voucher_number",
                                "voucher_type": "$voucher.voucher_type",
                                "party_name": "$voucher.party_name",
                                "party_name_id": "$voucher.party_name_id",
                                "place_of_supply": "$voucher.place_of_supply",
                                "vehicle_number": "$voucher.vehicle_number",
                                "mode_of_transport": "$voucher.mode_of_transport",
                                "payment_mode": "$voucher.payment_mode",
                                "due_date": "$voucher.due_date",
                            }
                        },
                        {"$project": {"voucher": 0}},
                    ],
                    "as": "timeline",
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "stock_item_name": 1,
                    "user_id": 1,
                    "company_id": 1,
                    "unit": 1,
                    "unit_id": 1,
                    "timeline": 1,
                }
            },
        ]

        res = [doc async for doc in self.collection.aggregate(pipeline)]

        if not res:
            return {"message": "The product has no timeline data."}
        return res

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

        pipeline = [
            # Start from StockItem (ensures all items included)
            {
                "$match": filter_params,
            },
            # Lookup for the Stock Item in Inventory and then to the related voucher
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"item_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$item_id", "$$item_id"]}}},
                        {
                            "$lookup": {
                                "from": "Voucher",
                                "let": {"vouchar_id": "$vouchar_id"},
                                "pipeline": [
                                    {
                                        "$match": {
                                            "$expr": {"$eq": ["$_id", "$$vouchar_id"]}
                                        }
                                    },
                                    {
                                        "$project": {
                                            "_id": 1,
                                            "date": 1,
                                            "voucher_number": 1,
                                            "voucher_type": 1,
                                            "additional_charge": 1,
                                        }
                                    },
                                ],
                                "as": "voucher_info",
                            }
                        },
                        {
                            "$unwind": {
                                "path": "$voucher_info",
                                "preserveNullAndEmptyArrays": True,
                            }
                        },
                        {
                            "$project": {
                                "_id": 1,
                                "item_id": 1,
                                "vouchar_id": 1,
                                "quantity": 1,
                                "total_amount": 1,
                                "voucher_info": 1,
                            }
                        },
                    ],
                    "as": "all_txns",
                }
            },
            {
                "$addFields": {
                    # filter rows before start_date
                    "txns_before_start": {
                        "$filter": {
                            "input": "$all_txns",
                            "as": "t",
                            "cond": {
                                # convert voucher_info.date strings (YYYY-MM-DD) to dates for comparison
                                "$lt": ["$$t.voucher_info.date", start_date]
                            },
                        }
                    },
                    # filter rows within [start_date, end_date]
                    "txns_in_range": {
                        "$filter": {
                            "input": "$all_txns",
                            "as": "t",
                            "cond": {
                                "$and": [
                                    {"$gte": ["$$t.voucher_info.date", start_date]},
                                    {"$lte": ["$$t.voucher_info.date", end_date]},
                                ]
                            },
                        }
                    },
                }
            },
            # Calculating the purchase and sale quantity and value for the filtered transactions
            {
                "$addFields": {
                    "before_summary": {
                        "$reduce": {
                            "input": "$txns_before_start",
                            "initialValue": {
                                "purchase_qty": 0,
                                "purchase_value": 0,
                                "sales_qty": 0,
                                "sales_value": 0,
                            },
                            "in": {
                                "$mergeObjects": [
                                    "$$value",
                                    {
                                        "purchase_qty": {
                                            "$add": [
                                                "$$value.purchase_qty",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Purchase",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.quantity",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "purchase_value": {
                                            "$add": [
                                                "$$value.purchase_value",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Purchase",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.total_amount",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "sales_qty": {
                                            "$add": [
                                                "$$value.sales_qty",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Sales",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.quantity",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "sales_value": {
                                            "$add": [
                                                "$$value.sales_value",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Sales",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.total_amount",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                    },
                                ]
                            },
                        }
                    },
                    # reduce txns_in_range to sums
                    "range_summary": {
                        "$reduce": {
                            "input": "$txns_in_range",
                            "initialValue": {
                                "purchase_qty": 0,
                                "purchase_value": 0,
                                "sales_qty": 0,
                                "sales_value": 0,
                            },
                            "in": {
                                "$mergeObjects": [
                                    "$$value",
                                    {
                                        "purchase_qty": {
                                            "$add": [
                                                "$$value.purchase_qty",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Purchase",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.quantity",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "purchase_value": {
                                            "$add": [
                                                "$$value.purchase_value",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Purchase",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.total_amount",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "sales_qty": {
                                            "$add": [
                                                "$$value.sales_qty",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Sales",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.quantity",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "sales_value": {
                                            "$add": [
                                                "$$value.sales_value",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Sales",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.total_amount",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                    },
                                ]
                            },
                        }
                    },
                }
            },
            # Add the fields opening qty, rate, value from the stock item
            {
                "$addFields": {
                    # original stored opening values (from StockItem document)
                    "orig_opening_balance": {"$ifNull": ["$opening_balance", 0]},
                    "orig_opening_rate": {"$ifNull": ["$opening_rate", 0]},
                    "orig_opening_value": {
                        "$ifNull": [
                            "$opening_value",
                            {
                                "$multiply": [
                                    {"$ifNull": ["$opening_balance", 0]},
                                    {"$ifNull": ["$opening_rate", 0]},
                                ]
                            },
                        ]
                    },
                    # opening adjustments from txns before start
                    "before_purchase_qty": {
                        "$ifNull": ["$before_summary.purchase_qty", 0]
                    },
                    "before_purchase_value": {
                        "$ifNull": ["$before_summary.purchase_value", 0]
                    },
                    "before_sales_qty": {"$ifNull": ["$before_summary.sales_qty", 0]},
                    "before_sales_value": {"$ifNull": ["$before_summary.sales_value", 0]},
                    # period (start..end) sums
                    "period_purchase_qty": {
                        "$ifNull": ["$range_summary.purchase_qty", 0]
                    },
                    "period_purchase_value": {
                        "$ifNull": ["$range_summary.purchase_value", 0]
                    },
                    "period_sales_qty": {"$ifNull": ["$range_summary.sales_qty", 0]},
                    "period_sales_value": {"$ifNull": ["$range_summary.sales_value", 0]},
                }
            },
            # Calculating the purchase and sale rate for the filtered transactions
            {
                "$addFields": {
                    # opening adjustments from txns before start
                    "before_purchase_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$before_purchase_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$before_purchase_value", 0]},
                                    {"$ifNull": ["$before_purchase_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    "before_sales_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$before_sales_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$before_sales_value", 0]},
                                    {"$ifNull": ["$before_sales_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    # period (start..end) sums
                    "period_purchase_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$period_purchase_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$period_purchase_value", 0]},
                                    {"$ifNull": ["$period_purchase_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    "period_sales_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$period_sales_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$period_sales_value", 0]},
                                    {"$ifNull": ["$period_sales_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    "avg_purchase_rate": { 
                        "$cond": [
                            {"$gt": [{"$ifNull": [{"$sum": ["$orig_opening_balance", "$before_purchase_qty"]}, 0]}, 0]},
                            {
                                "$divide": [
                                    {"$sum": ["$orig_opening_value", "$before_purchase_value" ]},
                                    {"$sum": ["$orig_opening_balance", "$before_purchase_qty"]},
                                ]
                            },
                            0
                        ]
                    }
                }
            },
            {
                "$addFields": {
                    # Opening quantity = stored opening_balance + purchases before start - sales before start
                    "opening_qty": {
                        "$add": [
                            {"$ifNull": ["$orig_opening_balance", 0]},
                            {"$ifNull": ["$before_purchase_qty", 0]},
                            {"$multiply": [-1, {"$ifNull": ["$before_sales_qty", 0]}]},
                        ]
                    },
                    # Opening value prefer orig_opening_value, but if missing compute from orig_opening_rate * orig_opening_balance
                    "opening_value": {
                        "$add": [
                            {"$ifNull": ["$orig_opening_value", 0]},
                            {"$ifNull": ["$before_purchase_value", 0]},
                            {
                                "$multiply": [
                                    -1,
                                    {"$ifNull": ["$before_sales_qty", 0]},
                                    "$avg_purchase_rate",
                                ]
                            },
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    # combined_total_qty (used for avg cost calculation)
                    "combined_qty_for_avg": {
                        "$add": [
                            {"$ifNull": ["$orig_opening_balance", 0]},
                            {"$ifNull": ["$before_purchase_qty", 0]},
                            {"$ifNull": ["$period_purchase_qty", 0]},
                        ]
                    },
                    # combined_total_value for avg cost
                    "combined_value_for_avg": {
                        "$add": [
                            {"$ifNull": ["$orig_opening_value", 0]},
                            {"$ifNull": ["$before_purchase_value", 0]},
                            {"$ifNull": ["$period_purchase_value", 0]},
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    # purchase rate during period
                    "inwards_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$period_purchase_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$period_purchase_value", 0]},
                                    {"$ifNull": ["$period_purchase_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    # outwards rate during period
                    "outwards_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$period_sales_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$period_sales_value", 0]},
                                    {"$ifNull": ["$period_sales_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    # average cost (weighted) used for COGS: if combined_qty_for_avg > 0 else fallback to opening_rate (or 0)
                    "avg_cost_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$combined_qty_for_avg", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$combined_value_for_avg", 0]},
                                    {"$ifNull": ["$combined_qty_for_avg", 0]},
                                ]
                            },
                            1,
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    # COGS for sales in period = period_sales_qty * avg_cost_rate
                    "cogs": {
                        "$multiply": [
                            {"$ifNull": ["$period_sales_qty", 0]},
                            {"$ifNull": ["$avg_cost_rate", 0]},
                        ]
                    },
                },
            },
            {
                "$addFields": {
                    # gross profit = sales_value - cogs
                    "gross_profit": {
                        "$subtract": [
                            {"$ifNull": ["$period_sales_value", 0]},
                            {"$ifNull": ["$cogs", 0]},
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    # profit percent
                    "profit_percent": {
                        "$multiply": [
                            {
                                "$cond": [
                                    {"$gt": [{"$ifNull": ["$period_sales_value", 0]}, 0]},
                                    {
                                        "$divide": [
                                            {"$ifNull": ["$gross_profit", 0]},
                                            {"$ifNull": ["$period_sales_value", 0]},
                                        ]
                                    },
                                    0,
                                ]
                            },
                            100,
                        ]
                    },
                    # closing quantity
                    "closing_qty": {
                        "$subtract": [
                            {
                                "$add": [
                                    {"$ifNull": ["$opening_qty", 0]},
                                    {"$ifNull": ["$period_purchase_qty", 0]},
                                ]
                            },
                            {"$ifNull": ["$period_sales_qty", 0]},
                        ]
                    },
                    # closing_rate
                    "closing_rate": {"$ifNull": ["$avg_cost_rate", 0]},
                    # closing value = opening_value + purchase_value - cogs (value of sold items based on avg_cost)
                    "closing_val": {
                        "$multiply": [
                            {
                                "$subtract": [
                                    {
                                        "$add": [
                                            {"$ifNull": ["$opening_qty", 0]},
                                            {"$ifNull": ["$period_purchase_qty", 0]},
                                        ]
                                    },
                                    {"$ifNull": ["$period_sales_qty", 0]},
                                ]
                            },
                            {"$ifNull": ["$avg_cost_rate", 0]},
                        ]
                    },
                },
            },
            # 8) final project only required fields (rename to desired keys)
            {
                "$project": {
                    "item_id": "$_id",
                    "item": "$stock_item_name",
                    "unit": 1,
                    "category": 1,
                    # "unit_id": 1,
                    # opening
                    "opening_qty": {"$round": ["$opening_qty", 2]},
                    "opening_rate": {"$round": ["$avg_purchase_rate", 2]},
                    "opening_val": {"$round": ["$opening_value", 2]},
                    # period (purchase & sales)
                    "inwards_qty": {"$round": ["$period_purchase_qty", 2]},
                    "inwards_val": {"$round": ["$period_purchase_value", 2]},
                    "inwards_rate": {"$round": ["$inwards_rate", 2]},
                    "outwards_qty": {"$round": ["$period_sales_qty", 2]},
                    "outwards_val": {"$round": ["$period_sales_value", 2]},
                    "outwards_rate": {"$round": ["$outwards_rate", 2]},
                    # derived
                    # "avg_cost_rate": 1,
                    # "cogs": 1,
                    "gross_profit": {"$round": ["$gross_profit", 2]},
                    "profit_percent": {"$round": ["$profit_percent", 2]},
                    "closing_qty": {"$round": ["$closing_qty", 2]},
                    "closing_rate": {"$round": ["$closing_rate", 2]},
                    "closing_val": {"$round": ["$closing_val", 2]},
                }
            },
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
                                {
                                    "unit": {
                                        "$regex": f"{search}",
                                        "$options": "i",
                                    }
                                },
                                {
                                    "category": {
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
            {"$match": {"category": category} if category not in ["", None] else {}},
            {
                "$sort": {"item": -1 if sort.sort_order == SortingOrder.ASC else 1},
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
            # Start from StockItem (ensures all items included)
            {
                "$match": filter_params,
            },
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"item_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$item_id", "$$item_id"]}}},
                        {
                            "$lookup": {
                                "from": "Voucher",
                                "let": {"vouchar_id": "$vouchar_id"},
                                "pipeline": [
                                    {
                                        "$match": {
                                            "$expr": {"$eq": ["$_id", "$$vouchar_id"]}
                                        }
                                    },
                                    {
                                        "$project": {
                                            "_id": 1,
                                            "date": 1,
                                            "voucher_number": 1,
                                            "voucher_type": 1,
                                            "additional_charge": 1,
                                        }
                                    },
                                ],
                                "as": "voucher_info",
                            }
                        },
                        {
                            "$unwind": {
                                "path": "$voucher_info",
                                "preserveNullAndEmptyArrays": True,
                            }
                        },
                        {
                            "$project": {
                                "_id": 1,
                                "item_id": 1,
                                "vouchar_id": 1,
                                "quantity": 1,
                                "total_amount": 1,
                                "voucher_info": 1,
                            }
                        },
                    ],
                    "as": "all_txns",
                }
            },
            {
                "$addFields": {
                    # filter rows before start_date
                    "txns_before_start": {
                        "$filter": {
                            "input": "$all_txns",
                            "as": "t",
                            "cond": {
                                # convert voucher_info.date strings (YYYY-MM-DD) to dates for comparison
                                "$lt": ["$$t.voucher_info.date", start_date]
                            },
                        }
                    },
                    # filter rows within [start_date, end_date]
                    "txns_in_range": {
                        "$filter": {
                            "input": "$all_txns",
                            "as": "t",
                            "cond": {
                                "$and": [
                                    {"$gte": ["$$t.voucher_info.date", start_date]},
                                    {"$lte": ["$$t.voucher_info.date", end_date]},
                                ]
                            },
                        }
                    },
                }
            },
            {
                "$addFields": {
                    "before_summary": {
                        "$reduce": {
                            "input": "$txns_before_start",
                            "initialValue": {
                                "purchase_qty": 0,
                                "purchase_value": 0,
                                "sales_qty": 0,
                                "sales_value": 0,
                            },
                            "in": {
                                "$mergeObjects": [
                                    "$$value",
                                    {
                                        "purchase_qty": {
                                            "$add": [
                                                "$$value.purchase_qty",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Purchase",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.quantity",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "purchase_value": {
                                            "$add": [
                                                "$$value.purchase_value",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Purchase",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.total_amount",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "sales_qty": {
                                            "$add": [
                                                "$$value.sales_qty",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Sales",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.quantity",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "sales_value": {
                                            "$add": [
                                                "$$value.sales_value",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Sales",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.total_amount",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                    },
                                ]
                            },
                        }
                    },
                    # reduce txns_in_range to sums
                    "range_summary": {
                        "$reduce": {
                            "input": "$txns_in_range",
                            "initialValue": {
                                "purchase_qty": 0,
                                "purchase_value": 0,
                                "sales_qty": 0,
                                "sales_value": 0,
                            },
                            "in": {
                                "$mergeObjects": [
                                    "$$value",
                                    {
                                        "purchase_qty": {
                                            "$add": [
                                                "$$value.purchase_qty",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Purchase",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.quantity",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "purchase_value": {
                                            "$add": [
                                                "$$value.purchase_value",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Purchase",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.total_amount",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "sales_qty": {
                                            "$add": [
                                                "$$value.sales_qty",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Sales",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.quantity",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                        "sales_value": {
                                            "$add": [
                                                "$$value.sales_value",
                                                {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                "$$this.voucher_info.voucher_type",
                                                                "Sales",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$$this.total_amount",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                    },
                                ]
                            },
                        }
                    },
                }
            },
            # 5) compute final fields: opening, purchases, sales
            {
                "$addFields": {
                    # original stored opening values (from StockItem document)
                    "orig_opening_balance": {"$ifNull": ["$opening_balance", 0]},
                    "orig_opening_rate": {"$ifNull": ["$opening_rate", 0]},
                    "orig_opening_value": {
                        "$ifNull": [
                            "$opening_value",
                            {
                                "$multiply": [
                                    {"$ifNull": ["$opening_balance", 0]},
                                    {"$ifNull": ["$opening_rate", 0]},
                                ]
                            },
                        ]
                    },
                    # opening adjustments from txns before start
                    "before_purchase_qty": {
                        "$ifNull": ["$before_summary.purchase_qty", 0]
                    },
                    "before_purchase_value": {
                        "$ifNull": ["$before_summary.purchase_value", 0]
                    },
                    "before_sales_qty": {"$ifNull": ["$before_summary.sales_qty", 0]},
                    "before_sales_value": {"$ifNull": ["$before_summary.sales_value", 0]},
                    # period (start..end) sums
                    "period_purchase_qty": {
                        "$ifNull": ["$range_summary.purchase_qty", 0]
                    },
                    "period_purchase_value": {
                        "$ifNull": ["$range_summary.purchase_value", 0]
                    },
                    "period_sales_qty": {"$ifNull": ["$range_summary.sales_qty", 0]},
                    "period_sales_value": {"$ifNull": ["$range_summary.sales_value", 0]},
                }
            },
            {
                "$addFields": {
                    # opening adjustments from txns before start
                    "before_purchase_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$before_purchase_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$before_purchase_value", 0]},
                                    {"$ifNull": ["$before_purchase_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    "before_sales_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$before_sales_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$before_sales_value", 0]},
                                    {"$ifNull": ["$before_sales_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    # period (start..end) sums
                    "period_purchase_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$period_purchase_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$period_purchase_value", 0]},
                                    {"$ifNull": ["$period_purchase_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    "period_sales_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$period_sales_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$period_sales_value", 0]},
                                    {"$ifNull": ["$period_sales_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    "avg_purchase_rate": { 
                        "$cond": [
                            {"$gt": [{"$ifNull": [{"$sum": ["$orig_opening_balance", "$before_purchase_qty"]}, 0]}, 0]},
                            {
                                "$divide": [
                                    {"$sum": ["$orig_opening_value", "$before_purchase_value" ]},
                                    {"$sum": ["$orig_opening_balance", "$before_purchase_qty"]},
                                ]
                            },
                            0
                        ]
                    }
                }
            },
            # 6) compute opening_qty/value, average cost, cogs, profit, closing
            {
                "$addFields": {
                    # Opening quantity = stored opening_balance + purchases before start - sales before start
                    "opening_qty": {
                        "$add": [
                            {"$ifNull": ["$orig_opening_balance", 0]},
                            {"$ifNull": ["$before_purchase_qty", 0]},
                            {"$multiply": [-1, {"$ifNull": ["$before_sales_qty", 0]}]},
                        ]
                    },
                    # Opening value prefer orig_opening_value, but if missing compute from orig_opening_rate * orig_opening_balance
                    "opening_value": {
                        "$add": [
                            {"$ifNull": ["$orig_opening_value", 0]},
                            {"$ifNull": ["$before_purchase_value", 0]},
                            {
                                "$multiply": [
                                    -1,
                                    {"$ifNull": ["$before_sales_qty", 0]},
                                    "$avg_purchase_rate",
                                ]
                            },
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    # combined_total_qty (used for avg cost calculation)
                    "combined_qty_for_avg": {
                        "$add": [
                            {"$ifNull": ["$opening_qty", 0]},
                            {"$ifNull": ["$before_purchase_qty", 0]},
                            {"$ifNull": ["$period_purchase_qty", 0]},
                        ]
                    },
                    # combined_total_value for avg cost
                    "combined_value_for_avg": {
                        "$add": [
                            {"$ifNull": ["$opening_value", 0]},
                            {"$ifNull": ["$before_purchase_value", 0]},
                            {"$ifNull": ["$period_purchase_value", 0]},
                        ]
                    },
                }
            },
            # 7) calculate rates, cogs, gross profit, closing values
            {
                "$addFields": {
                    # purchase rate during period
                    "inwards_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$period_purchase_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$period_purchase_value", 0]},
                                    {"$ifNull": ["$period_purchase_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    # outwards rate during period
                    "outwards_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$period_sales_qty", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$period_sales_value", 0]},
                                    {"$ifNull": ["$period_sales_qty", 0]},
                                ]
                            },
                            0,
                        ]
                    },
                    # average cost (weighted) used for COGS: if combined_qty_for_avg > 0 else fallback to opening_rate (or 0)
                    "avg_cost_rate": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$combined_qty_for_avg", 0]}, 0]},
                            {
                                "$divide": [
                                    {"$ifNull": ["$combined_value_for_avg", 0]},
                                    {"$ifNull": ["$combined_qty_for_avg", 0]},
                                ]
                            },
                            {
                                "$cond": [
                                    {"$gt": [{"$ifNull": ["$opening_qty", 0]}, 0]},
                                    {
                                        "$divide": [
                                            {"$ifNull": ["$opening_value", 0]},
                                            {"$ifNull": ["$opening_qty", 0]},
                                        ]
                                    },
                                    0,
                                ]
                            },
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    # COGS for sales in period = period_sales_qty * avg_cost_rate
                    "cogs": {
                        "$multiply": [
                            {"$ifNull": ["$period_sales_qty", 0]},
                            {"$ifNull": ["$avg_cost_rate", 0]},
                        ]
                    },
                },
            },
            {
                "$addFields": {
                    # gross profit = sales_value - cogs
                    "gross_profit": {
                        "$subtract": [
                            {"$ifNull": ["$period_sales_value", 0]},
                            {"$ifNull": ["$cogs", 0]},
                        ]
                    },
                }
            },
            {
                "$addFields": {
                    # profit percent
                    "profit_percent": {
                        "$multiply": [
                            {
                                "$cond": [
                                    {"$gt": [{"$ifNull": ["$period_sales_value", 0]}, 0]},
                                    {
                                        "$divide": [
                                            {"$ifNull": ["$gross_profit", 0]},
                                            {"$ifNull": ["$period_sales_value", 0]},
                                        ]
                                    },
                                    0,
                                ]
                            },
                            100,
                        ]
                    },
                    # closing quantity
                    "closing_qty": {
                        "$subtract": [
                            {
                                "$add": [
                                    {"$ifNull": ["$opening_qty", 0]},
                                    {"$ifNull": ["$period_purchase_qty", 0]},
                                ]
                            },
                            {"$ifNull": ["$period_sales_qty", 0]},
                        ]
                    },
                    # closing_rate
                    "closing_rate": {"$ifNull": ["$avg_cost_rate", 0]},
                    # closing value = opening_value + purchase_value - cogs (value of sold items based on avg_cost)
                    "closing_val": {
                        "$multiply": [
                            {
                                "$subtract": [
                                    {
                                        "$add": [
                                            {"$ifNull": ["$opening_qty", 0]},
                                            {"$ifNull": ["$period_purchase_qty", 0]},
                                        ]
                                    },
                                    {"$ifNull": ["$period_sales_qty", 0]},
                                ]
                            },
                            {"$ifNull": ["$avg_cost_rate", 0]},
                        ]
                    },
                },
            },
            # 8) final project only required fields (rename to desired keys)
            {
                "$project": {
                    "item_id": "$_id",
                    "item": "$stock_item_name",
                    "unit": 1,
                    # "unit_id": 1,
                    # opening
                    "opening_qty": {"$round": ["$opening_qty", 2]},
                    "opening_rate": {"$round": ["$avg_purchase_rate", 2]},
                    "opening_val": {"$round": ["$opening_value", 2]},
                    # period (purchase & sales)
                     "inwards_qty": {"$round": ["$period_purchase_qty", 2]},
                    "inwards_val": {"$round": ["$period_purchase_value", 2]},
                    "inwards_rate": {"$round": ["$inwards_rate", 2]},
                    "outwards_qty": {"$round": ["$period_sales_qty", 2]},
                    "outwards_val": {"$round": ["$period_sales_value", 2]},
                    "outwards_rate": {"$round": ["$outwards_rate", 2]},
                    # derived
                    # "avg_cost_rate": 1,
                    # "cogs": 1,
                    "gross_profit": {"$round": ["$gross_profit", 2]},
                    "profit_percent": {"$round": ["$profit_percent", 2]},
                    "closing_qty": {"$round": ["$closing_qty", 2]},
                    "closing_rate": {"$round": ["$closing_rate", 2]},
                    "closing_val": {"$round": ["$closing_val", 2]},
                }
            },
        ]

        response = await asyncio.gather(
            fetch_all(self.collection.aggregate(pipeline)),
            fetch_all(self.collection.aggregate(meta_pipeline)),
        )
        res = response[0]
        totals_res = response[1]
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
                opening_val=round(opening_val, 2),
                inwards_val=round(inwards_val, 2),
                outwards_val=round(outwards_val, 2),
                closing_val=round(closing_val, 2),
                gross_profit=round(gross_profit, 2),
                profit_percent=round(profit_percent, 2),
            ),
        )


stock_item_repo = StockItemRepo()
