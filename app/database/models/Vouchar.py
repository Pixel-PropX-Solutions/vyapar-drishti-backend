from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import Literal, Optional, List
from app.database.models.Inventory import InventoryItem, InventoryItemUpdate
from app.database.models.Accounting import Accounting, AccountingUpdate


class Voucher(BaseModel):
    company_id: str
    user_id: str
    date: str
    voucher_number: str = ""
    voucher_type: Literal[
        "Sales",
        "Purchase",
        "Payment",
        "Receipt",
        "Contra",
        "Journal",
        "Credit Note",
        "Debit Note",
    ] = "Sales"
    voucher_type_id: str = ""
    narration: str = ""
    party_name: str = ""
    party_name_id: str = ""

    # Conditional fields
    reference_date: Optional[str] = None
    reference_number: Optional[str] = ""
    place_of_supply: str = ""
    vehicle_number: Optional[str] = None
    mode_of_transport: Optional[str] = None
    payment_mode: Optional[str] = None
    due_date: Optional[str] = None

    # Accounting fields
    paid_amount: float  # Amount paid by the customer
    total: Optional[float] = 0.0  # Total amount before taxes and discounts
    discount: Optional[float] = 0.0  # Discount applied to the invoice
    total_amount: Optional[float] = 0.0  # Total amount after discounts but before taxes
    total_tax: Optional[float] = 0.0  # Total tax applied to the invoice
    additional_charge: Optional[float] = 0.0  # Any additional charges applied
    roundoff: Optional[float] = 0.0  # Round off amount
    grand_total: float  # Total amount including taxes, discounts, and additional charges

    is_deleted: bool = False


class VoucherDB(Voucher):
    vouchar_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class VoucherCreate(BaseModel):
    company_id: str
    date: str
    voucher_type: Literal[
        "Sales",
        "Purchase",
        "Payment",
        "Receipt",
        "Contra",
        "Journal",
        "Credit Note",
        "Debit Note",
    ] = "Sales"
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
    payment_mode: Optional[str] = None
    due_date: Optional[str] = None

    paid_amount: float  # Amount paid by the customer
    total: Optional[float] = 0.0  # Total amount before taxes and discounts
    discount: Optional[float] = 0.0  # Discount applied to the invoice
    total_amount: Optional[float] = 0.0  # Total amount after discounts but before taxes
    total_tax: Optional[float] = 0.0  # Total tax applied to the invoice
    additional_charge: Optional[float] = 0.0  # Any additional charges applied
    roundoff: Optional[float] = 0.0  # Round off amount
    grand_total: float  # Total amount including taxes, discounts, and additional charges

    accounting: List[Accounting]
    items: List[InventoryItem] = []


class VoucherUpdate(BaseModel):
    vouchar_id: str
    user_id: str
    company_id: str
    date: str
    voucher_type: Literal[
        "Sales",
        "Purchase",
        "Payment",
        "Receipt",
        "Contra",
        "Journal",
        "Credit Note",
        "Debit Note",
    ] = "Sales"
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
    payment_mode: Optional[str] = None
    due_date: Optional[str] = None

    paid_amount: float  # Amount paid by the customer
    total: Optional[float] = 0.0  # Total amount before taxes and discounts
    discount: Optional[float] = 0.0  # Discount applied to the invoice
    total_amount: Optional[float] = 0.0  # Total amount after discounts but before taxes
    total_tax: Optional[float] = 0.0  # Total tax applied to the invoice
    additional_charge: Optional[float] = 0.0  # Any additional charges applied
    roundoff: Optional[float] = 0.0  # Round off amount
    grand_total: float  # Total amount including taxes, discounts, and additional charges

    accounting: List[AccountingUpdate]
    items: Optional[List[InventoryItemUpdate]]
