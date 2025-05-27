from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import Optional


class Shipping(BaseModel):
    user_id: str
    company_id: str
    state: str
    address_1: str
    is_deleted: bool = False

    # Optional fields
    country: Optional[str] = None
    title: Optional[str] = None
    address_2: Optional[str] = None
    pinCode: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None


class ShippingDB(Shipping):
    shipping_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class ShippingCreate(BaseModel):
    user_id: str
    company_id: str
    state: str
    address_1: str
    is_deleted: bool = False
