from typing import Literal, Union, List, Optional
from pydantic import BaseModel, Field, field_validator
import datetime
from app.database.models.entity import Name, PhoneNumber
from app.schema.enums import PlanNameEnum, UserTypeEnum
from uuid import uuid4


class Features(BaseModel):
    enable_tax: bool = False
    enable_inventory: bool = True
    enable_hsn_summary: bool = False
    enable_reports: bool = False
    enable_multi_godown: bool = False
    enable_custom_units: bool = False
    enable_notification: bool = False
    enable_reminder: bool = False
    enable_low_stock: bool = False
    enable_tracking: bool = False
    enable_printing: bool = False
    enable_sharing: bool = False
    enable_custom_logo: bool = False
    enable_custom_header_footer: bool = False
    enable_auto_save: bool = False
    enable_custom_fields: bool = False
    enable_bulk_upload: bool = False
    enable_daily_summary: bool = False
    enable_insights: bool = False
    enable_online_payment: bool = False
    enable_barcode: bool = False
    enable_user_activity_log: bool = False
    enable_bulk_download: bool = False
    e_way_bill: bool = False
    enable_price_list: bool = False
    enable_batch_expiry: bool = False
    enable_customer_grouping: bool = False
    enable_item_grouping: bool = False
    enable_sales_order: bool = False
    enable_bank_reconciliation: bool = False
    enable_cess: bool = False
    enable_e_invoice: bool = False
    enable_gst_filing: bool = False
    enable_online_store: bool = False
    enable_digital_sign: bool = False


class SubscriptionPlan(BaseModel):
    name: PlanNameEnum = PlanNameEnum.basic
    version: int = 1
    description: Optional[str] = None
    price_per_month: float = 0.0
    price_per_year: float = 0.0

    # Feature limits
    max_companies: int = 1
    max_sub_users: int = 1
    max_vouchers_per_month: int = 100
    notification_limit_per_month: int = 0
    notification_type: List[Literal["email", "sms"]] = []
    notification_action: List[Literal["sales", "purchase", "payment", "receipt"]] = []
    features: Features = Field(default_factory=Features)
    is_active: bool = True

    stripe_product_id: Optional[str] = None
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_yearly: Optional[str] = None

    @field_validator(
        "price_per_month",
        "price_per_year",
        "max_companies",
        "max_sub_users",
        "max_vouchers_per_month",
        "notification_limit_per_month",
    )
    def non_negative(cls, v, field):
        if v < 0:
            raise ValueError(f"{field.name} cannot be negative")
        return v

    @property
    def yearly_discount_percentage(self) -> float:
        if self.price_per_month == 0:
            return 0
        expected_yearly = self.price_per_month * 12
        if expected_yearly == 0:
            return 0
        discount = ((expected_yearly - self.price_per_year) / expected_yearly) * 100
        return round(discount, 2)


class SubscriptionPlanDB(SubscriptionPlan):
    plan_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
