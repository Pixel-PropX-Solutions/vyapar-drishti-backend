from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import List
from app.database.models.entity import Name, BillingAddress, PhoneNumber, ShippingAddress
from app.schema.enums import BalanceType
from typing import Optional


class Creditor(BaseModel):
    name: Name
    user_id: str
    phone_number: Optional[PhoneNumber] = None
    email: Optional[str] = None
    gstin: Optional[str] = None
    company_name: Optional[str] = None
    billing_address: str
    shipping_address: Optional[str] = None
    opening_balance: Optional[float] = 0.0
    balance_type: Optional[BalanceType] = BalanceType.DEBIT

    # Additional fields for Creditor
    image: Optional[str] = None
    pan_number: Optional[str] = None
    credit_limit: Optional[float] = None
    tags: Optional[List[str]] = None
    due_date: Optional[float] = None


class CreditorDB(Creditor):
    creditor_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class CreditorCreate(BaseModel):
    name: Name
    user_id: str
