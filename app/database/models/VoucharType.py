from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4
import datetime

class VoucherType(BaseModel):
    vouchar_type_name: str
    user_id: str
    company_id: str
    parent: Optional[str] = ''
    _parent: Optional[str] = ''
    numbering_method: Optional[str] = ''  # e.g., "Automatic", "Manual"
    is_deemedpositive: Optional[bool] = False  # Credit/Debit direction
    affects_stock: Optional[bool] = False      # If stock is involved
    is_deleted: Optional[bool] = False  # Soft delete flag

class VoucherTypeDB(VoucherType):
    vouchar_type_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

class VoucherTypeCreate(BaseModel):
    vouchar_type_name: str
    user_id: str
    company_id: str
    parent: Optional[str] = ''
    _parent: Optional[str] = ''
    numbering_method: Optional[str] = ''  # e.g., "Automatic", "Manual"
    is_deemedpositive: Optional[bool] = False  # Credit/Debit direction
    affects_stock: Optional[bool] = False      # If stock is involved
    is_deleted: Optional[bool] = False  # Soft delete flag