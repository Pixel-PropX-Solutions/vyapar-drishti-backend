from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List
import datetime
from uuid import uuid4


class GSTItemDetail(BaseModel):
    item: str
    item_id: str
    hsn_code: Optional[str] = None
    gst_rate: Optional[str] = None  # e.g., "18%" or "9+9"
    taxable_value: float = 0.0
    cgst: Optional[float] = 0.0
    sgst: Optional[float] = 0.0
    igst: Optional[float] = 0.0
    total_amount: float = 0.0


class VoucherGST(BaseModel):
    voucher_id: str
    company_id: str
    user_id: str
    is_gst_applicable: bool = False
    place_of_supply: Optional[str] = None
    party_gstin: Optional[str] = None
    item_gst_details: Optional[List[GSTItemDetail]] = []
    # tax_ledgers: Optional[List[GSTLedgerDetail]] = []
    # gst_summary: Optional[List[GSTSummaryEntry]] = []
    is_deleted: bool = False


class VoucherGSTDB(VoucherGST):
    vouchar_gst_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
