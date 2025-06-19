from pydantic import BaseModel, Field
from typing import Optional, List
import datetime
from uuid import uuid4


class GSTDetails(BaseModel):
    gstin: Optional[str] = None
    gst_registration_type: Optional[str] = None  # Regular / Composition / Unregistered
    place_of_supply: Optional[str] = None


# class TDSDetails(BaseModel):
#     tan: Optional[str] = None
#     tds_enabled: bool = False
#     deductor_type: Optional[str] = None  # e.g., Company, Individual
#     default_nature_of_payment: Optional[str] = None
#     tds_threshold_limit: Optional[float] = None


class FeatureFlags(BaseModel):
    enable_gst: bool = False
    # enable_tds: bool = False
    # enable_vat: bool = False
    # enable_payroll: bool = False
    enable_inventory: bool = True
    # enable_multi_currency: bool = False


class FinancialYearFormat(BaseModel):
    start_month: int = 4   # April
    start_day: int = 1     # 1st
    name_format: str = "YYYY"  # e.g., "2024-25"

    # def format_year_name(self, date: datetime) -> str:
    #     year = date.year if date.month >= self.start_month else date.year - 1
    #     return f"{year}-{str((year + 1) % 100).zfill(2)}"


# class AuditLogEntry(BaseModel):
#     modified_by: str  # user_id or email
#     modified_at: datetime
#     action: str  # e.g., "Updated GST Settings", "Changed Book Start Date"


class CompanySettings(BaseModel):
    # Core company info
    user_id: str
    company_id: str
    company_name: str
    books_start_date: str
    country: str = "India"
    state: str
    currency: str = "INR"

    # Financial Year Format
    financial_year_format: FinancialYearFormat = Field(default_factory=FinancialYearFormat)

    # Feature toggles
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    # Tax configuration
    gst_details: Optional[GSTDetails] = Field(default_factory=GSTDetails)
    # tds_details: Optional[TDSDetails] = Field(default_factory=TDSDetails)

    # Audit/versioning
    # version: int = 1
    # last_modified_by: Optional[str] = None  # user_id or email
    # audit_log: List[AuditLogEntry] = Field(default_factory=list)

    # System flags
    is_deleted: bool = False
    
    
class CompanySettingsDB(CompanySettings):
    company_settings_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
