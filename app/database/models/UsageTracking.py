from typing import Literal, Union, List, Optional
from pydantic import BaseModel, Field
import datetime
from app.database.models.entity import Name, PhoneNumber
from app.schema.enums import UserTypeEnum
from uuid import uuid4


class UsageTracking(BaseModel):
    user_id: str
    plan_id: str
    metric_name: str  # e.g. "vouchers_created", "companies_created"
    count: int = 0
    reset_interval: str = "monthly"  # daily, monthly, yearly
    last_reset: datetime.datetime = Field(default_factory=datetime.datetime.now)
    
class UsageTrackingDB(UsageTracking):
    usage_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
