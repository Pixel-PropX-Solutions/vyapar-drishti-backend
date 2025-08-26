from typing import Optional
from pydantic import BaseModel, Field
from uuid import uuid4
import datetime


class InventoryItem(BaseModel):
    vouchar_id: str
    item: str
    item_id: str
    
    hsn_code: Optional[str] = ''
    unit: Optional[str] = ''
    
    quantity: float
    rate: float
    amount: float
    discount_amount: Optional[float] = 0.0
    tax_rate: Optional[float] = 0.0
    tax_amount: Optional[float] = 0.0
    total_amount: Optional[float] = 0.0

    # Additional fields for the item
    godown: Optional[str] = ""
    godown_id: Optional[str] = ""


class InventoryItemDB(InventoryItem):
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class InventoryItemCreate(BaseModel):
    vouchar_id: str
    item: str
    item_id: str
    
    hsn_code: Optional[str] = None
    unit: Optional[str] = None
    
    quantity: float
    rate: float
    amount: float

    # Additional fields for the item
    discount_amount: Optional[float] = 0.0
    tax_rate: Optional[float] = 0.0
    tax_amount: Optional[float] = 0.0
    total_amount: Optional[float] = 0.0
    godown: Optional[str] = ""
    godown_id: Optional[str] = ""


class InventoryItemUpdate(BaseModel):
    entry_id: str
    vouchar_id: str
    item: str
    item_id: str
    
    hsn_code: Optional[str] = None
    unit: Optional[str] = None
    
    quantity: float
    rate: float
    amount: float
    discount_amount: Optional[float] = 0.0
    tax_rate: Optional[float] = 0.0
    tax_amount: Optional[float] = 0.0
    total_amount: Optional[float] = 0.0
    
    godown: Optional[str] = ""
    godown_id: Optional[str] = ""

class CreateInventoryItemWithTAX(BaseModel):
    vouchar_id: str
    item: str
    item_id: str
    
    hsn_code: Optional[str] = None
    unit: Optional[str] = None
    
    quantity: float
    rate: float
    amount: float
    discount_amount: Optional[float] = 0.0
    tax_rate: Optional[float] = 0.0
    tax_amount: Optional[float] = 0.0
    total_amount: Optional[float] = 0.0
    
    godown: Optional[str] = ""
    godown_id: Optional[str] = ""


class UpdateInventoryItemWithTAX(BaseModel):
    entry_id: str
    vouchar_id: str
    item: str
    item_id: str
    
    hsn_code: Optional[str] = None
    unit: Optional[str] = None
    
    quantity: float
    rate: float
    amount: float
    discount_amount: Optional[float] = 0.0
    tax_rate: Optional[float] = 0.0
    tax_amount: Optional[float] = 0.0
    total_amount: Optional[float] = 0.0
    godown: Optional[str] = ""
    godown_id: Optional[str] = ""
