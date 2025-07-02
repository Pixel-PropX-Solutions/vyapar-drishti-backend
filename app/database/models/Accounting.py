from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import Optional


class Accounting(BaseModel):
    vouchar_id: str  # Foreign key to trn_voucher._id
    ledger: str = Field(..., description="Name of the ledger account used")
    ledger_id: str = Field(..., description="Internal reference or GUID for the ledger")
    amount: float = Field(..., description="Amount debited or credited")


# Database Schema
class AccountingDB(Accounting):
    accounting_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class AccountingCreate(BaseModel):
    vouchar_id: str
    ledger: str = Field(..., description="Name of the ledger account used")
    ledger_id: str = Field(..., description="Internal reference or GUID for the ledger")
    amount: float = Field(..., description="Amount debited or credited")


class AccountingUpdate(BaseModel):
    entry_id: str
    vouchar_id: str
    ledger: str = Field(..., description="Name of the ledger account used")
    ledger_id: str = Field(..., description="Internal reference or GUID for the ledger")
    amount: float = Field(..., description="Amount debited or credited")
