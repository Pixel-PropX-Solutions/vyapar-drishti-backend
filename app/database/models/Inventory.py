from typing import Optional
from pydantic import BaseModel, Field
from uuid import uuid4
import datetime


class InventoryItem(BaseModel):
    vouchar_id: str  # Foreign key to trn_voucher._id
    item: str
    item_id: str
    quantity: int  # Quantity of the item in the voucher(Sales, purchase), neagative for sale or positive for purchase
    rate: float
    amount: float  # Total amount for the item in the voucher(Sales, purchase), negative for sale or positive for purchase

    # Additional fields for the item
    # These fields are optional and can be used for additional charges or discounts
    additional_amount: Optional[float] = 0.0
    discount_amount: Optional[float] = 0.0
    godown: Optional[str] = ""
    godown_id: Optional[str] = ""
    # tracking_number: Optional[str] = None
    order_number: Optional[str] = None
    order_due_date: Optional[str] = None


class InventoryItemDB(InventoryItem):
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class InventoryItemCreate(BaseModel):
    vouchar_id: str  # Foreign key to trn_voucher._id
    item: str
    item_id: str
    quantity: int  # Quantity of the item in the voucher(Sales, purchase), neagative for sale or positive for purchase
    rate: float
    amount: float  # Total amount for the item in the voucher(Sales, purchase), negative for sale or positive for purchase

    # Additional fields for the item
    # These fields are optional and can be used for additional charges or discounts
    additional_amount: Optional[float] = 0.0
    discount_amount: Optional[float] = 0.0
    godown: Optional[str] = ""
    godown_id: Optional[str] = ""
    # tracking_number: Optional[str] = None
    order_number: Optional[str] = None
    order_due_date: Optional[str] = None


class InventoryItemUpdate(BaseModel):
    entry_id: str
    vouchar_id: str
    item: str
    item_id: str
    quantity: int
    rate: float
    amount: float

    additional_amount: Optional[float] = 0.0
    discount_amount: Optional[float] = 0.0
    godown: Optional[str] = ""
    godown_id: Optional[str] = ""

    order_number: Optional[str] = None
    order_due_date: Optional[str] = None
