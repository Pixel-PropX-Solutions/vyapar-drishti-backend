from pydantic import BaseModel, Field, validator, root_validator
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
    user_id: str
    company_id: str
    item: str
    item_id: str
    hsn_description: Optional[str] = None
    hsn_code: Optional[str] = None
    rate: Optional[str] = None  # Accepts "18", "9+9"
    nature_of_goods: Optional[str] = None  # Goods or Services
    taxability: Optional[str] = "Taxable"  # Taxable / Exempt / Nil Rated

    # Auto-parsed fields (not input)
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None

    @root_validator(pre=True)
    def set_gst_components(cls, values):
        rate = values.get("rate")
        if rate:
            match = re.fullmatch(r"(\d+(?:\.\d+)?)\+(\d+(?:\.\d+)?)", rate)
            if match:
                values["cgst"] = float(match.group(1))
                values["sgst"] = float(match.group(2))
                values["igst"] = float(match.group(1)) + float(match.group(2))
            elif re.fullmatch(r"\d+(\.\d+)?", rate):
                values["igst"] = float(rate)
                values["cgst"] = float(rate) / 2
                values["sgst"] = float(rate) / 2
            else:
                raise ValueError("Invalid GST rate format. Use '9+9' or '18'.")
        return values


class GSTRateDB(GSTRate):
    gst_rate_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
