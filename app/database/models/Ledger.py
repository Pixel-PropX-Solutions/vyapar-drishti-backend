from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from app.database.models.entity import PhoneNumber
from typing import Optional


class Ledger(BaseModel):
    name: str
    company_id: str
    user_id: str
    parent: str # Group under which the ledger falls (e.g., "Sales Accounts")
    _parent: Optional[str] = None  # This is the name or id of the parent Ledger for internal reference
    alias: Optional[str] = None
    is_revenue: Optional[bool] = False
    is_deemed_positive: Optional[bool] = False # Indicates and Controls Debit/Credit nature
    opening_balance: Optional[float] = 0.0 # Opening balance for the ledger, can be positive or negative, Amount if ledger is not zeroed
    image: Optional[str] = None
    is_deleted: Optional[bool] = False
    
    

    # Optional mailing details
    mailing_name: Optional[str] = None
    mailing_address: Optional[str] = None
    mailing_state: Optional[str] = None
    mailing_country: Optional[str] = None
    mailing_pincode: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[PhoneNumber] = None 

    # Optional tax details
    it_pan: Optional[str] = None
    gstn: Optional[str] = None
    gst_registration_type: Optional[str] = None
    gst_supply_type: Optional[str] = None
    gst_duty_head: Optional[str] = None
    tax_rate: Optional[float] = 0.0

    # # Optional bank details
    # bank_account_holder: Optional[str] = None
    # bank_account_number: Optional[str] = None
    # bank_ifsc: Optional[str] = None
    # bank_swift: Optional[str] = None
    # bank_name: Optional[str] = None
    # bank_branch: Optional[str] = None


class LedgerDB(Ledger):
    ledger_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class LedgerCreate(BaseModel):
    name: str
    company_id: str
    user_id: str
    parent: str # Group under which the ledger falls (e.g., "Sales Accounts")
    _parent: Optional[str] = None  # This is the name or id of the parent Ledger for internal reference
    alias: Optional[str] = None
    is_revenue: Optional[bool] = False
    is_deemed_positive: Optional[bool] = False 
    opening_balance: Optional[float] = 0.0 

    # Optional mailing details
    mailing_name: Optional[str] = None
    mailing_address: Optional[str] = None
    mailing_state: Optional[str] = None
    mailing_country: Optional[str] = None
    mailing_pincode: Optional[str] = None
    email: Optional[str] = None

    # # Optional tax details
    # it_pan: Optional[str] = None
    # gstn: Optional[str] = None
    # gst_registration_type: Optional[str] = None
    # gst_supply_type: Optional[str] = None
    # gst_duty_head: Optional[str] = None
    # tax_rate: Optional[float] = 0.0

    # # Optional bank details
    # bank_account_holder: Optional[str] = None
    # bank_account_number: Optional[str] = None
    # bank_ifsc: Optional[str] = None
    # bank_swift: Optional[str] = None
    # bank_name: Optional[str] = None
    # bank_branch: Optional[str] = None
