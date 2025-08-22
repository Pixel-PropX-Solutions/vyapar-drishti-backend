from pydantic import BaseModel, Field
from typing import Optional, List
import datetime
from uuid import uuid4


class TAXDetails(BaseModel):
    tin: Optional[str] = None
    tax_registration: Optional[str] = None  # Regular / Composition / Unregistered
    place_of_supply: Optional[str] = None


# class TDSDetails(BaseModel):
#     tan: Optional[str] = None
#     tds_enabled: bool = False
#     deductor_type: Optional[str] = None  # e.g., Company, Individual
#     default_nature_of_payment: Optional[str] = None
#     tds_threshold_limit: Optional[float] = None


class BankDetails(BaseModel):
    account_holder: Optional[str] = None
    account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    qr_code_url: Optional[str] = None


class FeatureFlags(BaseModel):
    enable_tax: bool = False
    item_wise_tax: bool = False
    # enable_tds: bool = False
    # enable_vat: bool = False
    # enable_payroll: bool = False
    enable_inventory: bool = True
    # enable_multi_currency: bool = False


# class AuditLogEntry(BaseModel):
#     modified_by: str  # user_id or email
#     modified_at: datetime
#     action: str  # e.g., "Updated TAX Settings", "Changed Book Start Date"


class CompanySettings(BaseModel):
    # Core company info
    user_id: str
    company_id: str
    company_name: str
    books_start_date: str
    country: str = "India"
    state: str
    currency: str = "INR"
    motto: Optional[str] = "LIFE'S A JOURNEY, KEEP SMILING"

    # Feature toggles
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    # Tax configuration
    tax_details: Optional[TAXDetails] = Field(default_factory=TAXDetails)
    # tds_details: Optional[TDSDetails] = Field(default_factory=TDSDetails)
    bank_details: Optional[BankDetails] = Field(default_factory=BankDetails)

    # Audit/versioning
    # version: int = 1
    # last_modified_by: Optional[str] = None  # user_id or email
    # audit_log: List[AuditLogEntry] = Field(default_factory=list)

    # System flags
    is_deleted: bool = False


class CompanySettingsDB(CompanySettings):
    company_settings_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
