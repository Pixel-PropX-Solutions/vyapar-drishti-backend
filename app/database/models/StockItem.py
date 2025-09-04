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
    hsn_code: Optional[str] = ""
    nature_of_goods: Optional[str] = ""
    taxability: Optional[str] = ""
    tax_rate: Optional[float] = 0

    # Additonal Optional fields
    low_stock_alert: Optional[float] = 10.0


# Database Schema
class StockItemDB(StockItem):
    stock_item_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


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
    opening_balance: Optional[float] = 0.0
    opening_rate: Optional[float] = 0.0
    opening_value: Optional[float] = 0.0
    nature_of_goods: Optional[str] = ""
    hsn_code: Optional[str] = ""
    taxability: Optional[str] = ""
    tax_rate: Optional[float] = 0.0

    # Additonal Optional fields
    low_stock_alert: Optional[float] = 10.0


class StockItemVouchar(BaseModel):
    name: str
    hsn_code: str
    quantity: float
    rate: float
    amount: float
