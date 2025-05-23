from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from enum import Enum
from typing import Optional, Union



# Base Product Schema
class product(BaseModel):
    #required fields
    product_name: str
    selling_price: float
    user_id: str
    is_deleted: bool = False
    
    #optional fields    
    unit: str | None
    hsn_code: str | None
    puchase_price: float | None
    barcode: str | None
    category: str | None
    image: str | None
    description: str | None
    opening_quantity: int | None
    opening_purchase_price: int | None
    opening_stock_value: int | None
    
    # Additonal Optional fields
    low_stock_alert: int | None
    show_active_stock: bool = True
    
    state: str | None
    storage_requirement: str | None
    expiry_date: datetime.datetime | None


# Database Schema
class ProductDB(product):
    product_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


# Schema for Creating a New Product
class ProductCreate(BaseModel):
    # required fields
    product_name: str
    selling_price: float
    user_id: str
    is_deleted: bool = False
    
    # optional fields    
    unit: Optional[str] = None
    hsn_code: Optional[str] = None
    purchase_price: Union[float, str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    image: Optional[str] = None
    description: Optional[str] = None
    opening_quantity: Union[int, str] = None
    opening_purchase_price: Union[float, str] = None
    opening_stock_value: Union[int, str] = None
    
     # Additonal Optional fields
    low_stock_alert: Union[int, str] = None
    show_active_stock: bool = True
    
    state: Union[str] = None
    storage_requirement: Optional[str] = None
    expiry_date: Union[datetime.datetime, str] = None
