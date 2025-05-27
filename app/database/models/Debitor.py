from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from enum import Enum
from typing import Dict, List
from app.database.models.entity import Name, PhoneNumber
from app.schema.enums import BalanceType
from typing import Optional


class Debitor(BaseModel):
    name: Name
    user_id: str
    billing_address: str
    phone_number: Optional[PhoneNumber] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    gstin: Optional[str] = None
    opening_balance: Optional[float] = 0.0
    balance_type: Optional[BalanceType] = BalanceType.DEBIT

    # Additional fields for Debitor
    image: Optional[str] = None
    pan_number: Optional[str] = None
    debit_limit: Optional[float] = None
    tags: Optional[List[str]] = None


class DebitorDB(Debitor):
    debitor_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class DebitorCreate(BaseModel):
    name: Name
    user_id: str
