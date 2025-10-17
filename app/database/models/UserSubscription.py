from typing import Literal, Union, List, Optional
from pydantic import BaseModel, Field
import datetime
from app.database.models.entity import Name, PhoneNumber
from app.schema.enums import UserTypeEnum
from uuid import uuid4


class UserSubscription(BaseModel):
    user_id: str
    plan_id: str  
    start_date: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    end_date: Optional[datetime.datetime] = None  # None = lifetime or free tier
    trial_end_date: Optional[datetime.datetime] = None
    is_active: bool = True
    auto_renew: bool = True
    payment_status: Literal[
        "Paid",
        "Pending",
        "Failed",
        "Cancelled",
        "Refunded",
        "Free Tier",
        "Trial",
    ] = "Free Tier"
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    stripe_session_id: Optional[str] = None

    def is_trial_active(self) -> bool:
        return (
            self.trial_end_date is not None
            and datetime.datetime.now() <= self.trial_end_date
        )


class UserSubscriptionDB(UserSubscription):
    user_subscription_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
