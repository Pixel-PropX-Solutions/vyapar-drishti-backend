from pydantic import BaseModel, Field
from typing import Optional, List
import datetime
from uuid import uuid4


class TAXDetails(BaseModel):
    tin: Optional[str] = None
    tax_registration: Optional[str] = None  # Regular / Composition / Unregistered
    place_of_supply: Optional[str] = None


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
    enable_inventory: bool = True
    
# class PrintDetails(BaseModel):
#     # Print Declarations
#     print_decl: list[str] = Field(
#         default_factory=lambda: [
#             "We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct",
#         ]
#     )
#     print_jurisdiction: Optional[str] = None
#     print_bank_name: Optional[str] = None
#     print_bank_account: Optional[str] = None
#     qr_code_url: Optional[str] = None


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
    bank_details: Optional[BankDetails] = Field(default_factory=BankDetails)
    # print_details: Optional[PrintDetails] = Field(default_factory=PrintDetails)

    is_deleted: bool = False


class CompanySettingsDB(CompanySettings):
    company_settings_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
