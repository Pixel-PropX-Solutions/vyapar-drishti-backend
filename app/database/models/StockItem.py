from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from enum import Enum
from typing import Optional, Union


# Base Product Schema
class StockItem(BaseModel):

    # required fields
    stock_item_name: str
    user_id: str
    company_id: str
    unit: str
    unit_id: str
    is_deleted: bool = False

    # optional fields
    alias_name: Optional[str] = ""
    category: Optional[str] = ""
    category_id: Optional[str] = ""
    group: Optional[str] = ""
    group_id: Optional[str] = ""
    image: Optional[str] = ""
    description: Optional[str] = ""

    # optional fields
    opening_balance: Optional[float] = 0
    opening_rate: Optional[float] = 0
    opening_value: Optional[float] = 0
    gst_hsn_code: Optional[str] = ""
    gst_nature_of_goods: Optional[str] = ""
    gst_taxability: Optional[str] = ""

    # Additonal Optional fields
    low_stock_alert: Optional[int] = 0


# Database Schema
class StockItemDB(StockItem):
    stock_item_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


# Schema for Creating a New Product
class StockItemCreate(BaseModel):
    # required fields
    stock_item_name: str
    user_id: str
    company_id: str
    unit: str
    unit_id: str
    is_deleted: bool = False

    # optional fields
    alias_name: Optional[str] = ""
    category: Optional[str] = ""
    category_id: Optional[str] = ""
    group: Optional[str] = ""
    group_id: Optional[str] = ""
    image: Optional[str] = ""
    description: Optional[str] = ""

    # optional fields
    opening_balance: Optional[float] = 0
    opening_rate: Optional[float] = 0
    opening_value: Optional[float] = 0
    gst_nature_of_goods: Optional[str] = ""
    gst_hsn_code: Optional[str] = ""
    gst_taxability: Optional[str] = ""

    # Additonal Optional fields
    low_stock_alert: Optional[int] = 0

class StockItemVouchar(BaseModel):
    name: str
    hsn_code: str
    quantity: float
    rate: float
    amount: float
    
