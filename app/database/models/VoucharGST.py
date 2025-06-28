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

    @root_validator(pre=True)
    def set_total_amount(cls, values):
        cgst = values.get("cgst", 0.0)
        sgst = values.get("sgst", 0.0)
        igst = values.get("igst", 0.0)
        taxable_value = values.get("taxable_value", 0.0)

        if cgst and sgst:
            amount = taxable_value + cgst + sgst
        elif igst:
            amount = taxable_value + igst
        else:
            amount = taxable_value

        values["total_amount"] = amount
        return values


# class GSTLedgerDetail(BaseModel):
#     ledger_name: str
#     gst_duty_head: Optional[str] = None  # CGST / SGST / IGST / CESS
#     gst_rate: Optional[float] = None
#     amount: float = 0.0


# class GSTSummaryEntry(BaseModel):
#     rate: str
#     taxable_value: float
#     cgst: float
#     sgst: float
#     igst: float
#     total: float

#     @root_validator(pre=True)
#     def calculate_totals(cls, values):
#         taxable_value = values.get("taxable_value", 0.0)
#         cgst = values.get("cgst", 0.0)
#         sgst = values.get("sgst", 0.0)
#         igst = values.get("igst", 0.0)

#         total = taxable_value + cgst + sgst + igst
#         values["total"] = total
#         return values


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


class VoucherGSTDB(VoucherGST):
    vouchar_gst_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
