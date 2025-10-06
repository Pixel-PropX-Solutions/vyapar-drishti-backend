from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4
import datetime


class AccountingGroup(BaseModel):
    accounting_group_name: str
    user_id: Optional[str] = None
    company_id: Optional[str] = None
    description: Optional[str] = ""  # Description of the group
    is_deleted: bool = False  # Soft delete flag
    parent: Optional[str] = "Primary Group"  # Default parent group name
    parent_id: Optional[str] = "Primary Group"  # Internal use, default parent group name


class AccountingGroupDB(AccountingGroup):
    accounting_group_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class AccountingGroupCreate(BaseModel):
    accounting_group_name: str
    user_id: str
    company_id: str
    is_deleted: Optional[bool] = False
    description: Optional[str] = ""
    parent: Optional[str] = ""
    parent_id: Optional[str] = ""
