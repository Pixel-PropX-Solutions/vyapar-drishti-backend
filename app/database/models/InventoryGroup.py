from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4
import datetime


class InventoryGroup(BaseModel):
    inventory_group_name: str
    user_id: str
    company_id: str
    image: Optional[str] = None  # Image URL or path
    description: Optional[str] = ""  # Description of the group
    is_deleted: bool = False  # Soft delete flag
    parent: Optional[str] = "Primary Group"
    _parent: Optional[str] = "Primary Group"
    # gst_nature_of_goods: Optional[str] = ""
    # gst_hsn_code: Optional[str] = ""
    # gst_taxability: Optional[str] = ""


class InventoryGroupDB(InventoryGroup):
    inventory_group_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class InventoryGroupCreate(BaseModel):
    inventory_group_name: str
    user_id: str
    company_id: str
    image: Optional[str] = None  # Image URL or path
    description: Optional[str] = ""  # Description of the group
    is_deleted: bool = False  # Soft delete flag
    parent: Optional[str] = ""
    _parent: Optional[str] = ""
    # gst_nature_of_goods: Optional[str] = ""
    # gst_hsn_code: Optional[str] = ""
    # gst_taxability: Optional[str] = ""
