from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import Optional, List
from app.database.models.Inventory import InventoryItem, InventoryItemUpdate
from app.database.models.Accounting import Accounting, AccountingUpdate


class Voucher(BaseModel):
    company_id: str
    user_id: str
    date: str
    voucher_number: str = ""
    voucher_type: str = ""
    voucher_type_id: str = ""
    narration: str = ""
    party_name: str = (
        ""  # This is the name or id of the party( Ledger ) involved in the voucher
    )
    party_name_id: str = (
        ""  # This is the name or id of the party( Ledger ) involved in the voucher
    )

    # Conditional fields
    reference_date: Optional[str] = (
        None  # Required if using bill-wise accounting or tracking references(e.g. bills in sales/purchase).
    )
    reference_number: Optional[str] = (
        ""  # Required if using bill-wise accounting or tracking references (e.g. invoice date) in bill-wise entries.
    )
    place_of_supply: str = (
        ""  # Required if GST is enabled (used for determining IGST/CGST/SGST applicability).
    )
    vehicle_number: Optional[str] = None
    mode_of_transport: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None

    # Automatically set fields
    is_invoice: Optional[int] = 0
    is_accounting_voucher: Optional[int] = 0
    is_inventory_voucher: Optional[int] = 0
    is_order_voucher: Optional[int] = 0
    is_deleted: bool = False


class VoucherDB(Voucher):
    vouchar_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class VoucherCreate(BaseModel):
    company_id: str
    date: str
    voucher_type: str
    voucher_type_id: str
    voucher_number: str
    party_name: str
    party_name_id: str
    narration: Optional[str] = ""
    reference_number: Optional[str] = None
    reference_date: Optional[str] = None
    place_of_supply: Optional[str] = None
    vehicle_number: Optional[str] = None
    mode_of_transport: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None

    accounting: List[Accounting]
    items: List[InventoryItem] = []


class VoucherUpdate(BaseModel):
    vouchar_id: str
    user_id: str
    company_id: str
    date: str
    voucher_type: str
    voucher_type_id: str
    voucher_number: str
    party_name: str
    party_name_id: str
    narration: Optional[str]
    reference_number: Optional[str]
    reference_date: Optional[str]
    place_of_supply: Optional[str]
    
    vehicle_number: Optional[str] = None
    mode_of_transport: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None

    accounting: List[AccountingUpdate]
    items: Optional[List[InventoryItemUpdate]]
