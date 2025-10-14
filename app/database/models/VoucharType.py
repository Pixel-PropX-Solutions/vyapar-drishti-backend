from pydantic import BaseModel, Field
from typing import Literal, Optional
from uuid import uuid4
import datetime


class VoucherType(BaseModel):
    vouchar_type_name: str
    user_id: Optional[str] = None
    company_id: Optional[str] = None
    parent: Optional[str] = ""
    parent_id: Optional[str] = ""
    numbering_method: Literal["Automatic", "Manual"] = "Automatic"
    is_deemedpositive: Optional[bool] = False  # Credit/Debit direction
    affects_stock: Optional[bool] = False  # If stock is involved
    is_deleted: Optional[bool] = False  # Soft delete flag


class VoucherTypeDB(VoucherType):
    vouchar_type_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class VoucherTypeCreate(BaseModel):
    vouchar_type_name: str
    user_id: Optional[str] = None
    company_id: Optional[str] = None
    parent: Optional[str] = ""
    parent_id: Optional[str] = ""
    numbering_method: Literal["Automatic", "Manual"] = "Automatic"
    is_deemedpositive: Optional[bool] = False  # Credit/Debit direction
    affects_stock: Optional[bool] = False  # If stock is involved
    is_deleted: Optional[bool] = False  # Soft delete flag
