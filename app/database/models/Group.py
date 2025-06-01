# from pydantic import BaseModel, Field
# import datetime
# from uuid import uuid4
# from typing import Optional


# # Base Group Schema
# class Group(BaseModel):
#     # required fields
#     name: str
#     under: Optional[str] = "Primary"
#     company_id: str
#     user_id: str
#     is_deleted: bool
#     image: str | None
#     description: str | None


# # Database Schema
# class GroupDB(Group):
#     group_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
#     created_at: datetime.datetime = Field(
#         default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
#     )
#     updated_at: datetime.datetime = Field(
#         default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
#     )


# # Schema for Creating a New Group
# class GroupCreate(BaseModel):
#     # required fields
#     name: str
#     user_id: str
#     under: Optional[str] = "Primary"
#     image: Optional[str] = None
#     description: Optional[str] = None
#     is_deleted: Optional[bool] = False

from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4
import datetime


class Group(BaseModel):
    name: str
    user_id: str
    company_id: str
    description: Optional[str] = ""  # Description of the group
    image: Optional[str] = None  # URL or path to the group image
    is_deleted: bool = False  # Soft delete flag
    parent: Optional[str] = ""
    _parent: Optional[str] = ""
    primary_group: Optional[str] = ""  # Top-level system group like 'Capital Account'
    is_revenue: Optional[bool] = False  # True for income/expense groups
    is_deemedpositive: Optional[bool] = False  # Debit/Credit nature
    is_reserved: Optional[bool] = False  # True for system-reserved groups
    affects_gross_profit: Optional[bool] = False  # If affects P&L
    sort_position: Optional[int] = 0


class GroupDB(Group):
    group_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class GroupCreate(BaseModel):
    name: str
    user_id: str
    company_id: str
    is_deleted: Optional[bool] = False
    image: Optional[str] = ""
    description: Optional[str] = ""
    parent: Optional[str] = ""
    _parent: Optional[str] = ""
    primary_group: Optional[str] = ""
    is_revenue: Optional[bool] = False
    is_deemedpositive: Optional[bool] = False
    is_reserved: Optional[bool] = False
    affects_gross_profit: Optional[bool] = False
    sort_position: Optional[int] = 0
