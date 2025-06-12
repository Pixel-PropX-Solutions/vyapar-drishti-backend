from pydantic import BaseModel, Field, validator
from typing import Optional, List
from uuid import uuid4
from datetime import date
import re
from pydantic import BaseModel, Field
from typing import Optional
from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import Optional


class GSTRate(BaseModel):
    item: str
    _item: Optional[str] = Field(default_factory=lambda: str(uuid4()))
    applicable_from: Optional[date] = Field(default_factory=date.today)
    hsn_description: Optional[str] = None
    hsn_code: Optional[str] = None
    rate: Optional[str] = None  # Accepts "18", "9+9"
    is_rcm_applicable: Optional[bool] = False
    nature_of_transaction: Optional[str] = None  # Sale, Purchase, Export, etc.
    nature_of_goods: Optional[str] = None  # Goods or Services
    supply_type: Optional[str] = None  # Intra-state or Inter-state
    taxability: Optional[str] = "Taxable"  # Taxable / Exempt / Nil Rated

    # Auto-parsed fields (not input)
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None

    @validator("rate", always=True)
    def normalize_rate(cls, v, values):
        if v:
            match = re.fullmatch(r"(\d+(?:\.\d+)?)\+(\d+(?:\.\d+)?)", v)
            if match:
                values["cgst"] = float(match.group(1))
                values["sgst"] = float(match.group(2))
                values["igst"] = float(match.group(1)) + float(match.group(2))
            elif re.fullmatch(r"\d+(\.\d+)?", v):
                values["igst"] = float(v)
                values["cgst"] = float(v) / 2
                values["sgst"] = float(v) / 2
            else:
                raise ValueError("Invalid GST rate format. Use '9+9' or '18'.")
        return v


class GSTRateDB(GSTRate):
    gst_rate_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class GSTRateCreate(BaseModel):
    item: str
    applicable_from: Optional[str] = ''
    hsn_description: Optional[str] = None
    hsn_code: Optional[str] = None
    rate: Optional[str] = None  # Accepts "18", "9+9"
    is_rcm_applicable: Optional[bool] = False
    nature_of_transaction: Optional[str] = None  # Sale, Purchase, Export, etc.
    nature_of_goods: Optional[str] = None  # Goods or Services
    supply_type: Optional[str] = None  # Intra-state or Inter-state
    taxability: Optional[str] = "Taxable"  # Taxable / Exempt / Nil Rated

    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None
    