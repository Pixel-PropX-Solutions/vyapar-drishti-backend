from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import Optional, List
from app.database.models.Inventory import InventoryItem


class VoucherBase(BaseModel):
    company_id: str
    user_id: str
    alterid: int = 0
    date: datetime.date
    voucher_type: str = ""
    _voucher_type: str = ""
    voucher_number: str = ""
    reference_number: str = ""
    narration: str = ""
    party_name: str = ""  # This is the name or id of the party( Ledger ) involved in the voucher
    _party_name: str = "" # This is the name or id of the party( Ledger ) involved in the voucher
    place_of_supply: str = ""
    items: List[InventoryItem] = []
    
    # Optional fields
    reference_date: Optional[datetime.date] = None
    is_invoice: Optional[int] = 0
    is_accounting_voucher: Optional[int] = 0
    is_inventory_voucher: Optional[int] = 0
    is_order_voucher: Optional[int] = 0


class VoucherBaseDB(VoucherBase):
    vouchar_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class VoucherBaseCreate(BaseModel):
    company_id: str
    user_id: str
    alterid: int = 0
    date: datetime.date
    voucher_type: str = ""
    _voucher_type: str = ""
    voucher_number: str = ""
    reference_number: str = ""
    narration: str = ""
    party_name: str = ""
    _party_name: str = ""
    place_of_supply: str = ""
    items: List[InventoryItem] = []

    
    # Optional fields
    reference_date: Optional[datetime.date] = None
    is_invoice: Optional[int] = 0
    is_accounting_voucher: Optional[int] = 0
    is_inventory_voucher: Optional[int] = 0
    is_order_voucher: Optional[int] = 0


class VoucherUpdate(BaseModel):
    narration: Optional[str]
    place_of_supply: Optional[str]
    items: Optional[List[InventoryItem]]
