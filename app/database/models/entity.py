from pydantic import BaseModel
from typing import Optional


class Name(BaseModel):
    first: str
    last: Optional[str] = None


class PhoneNumber(BaseModel):
    code: str = "+91"
    number: str  

class ProductDetails(BaseModel):
    _id: str
    name: str
    quantity: int
    unit_price: float
    total_price: float
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    discount: Optional[float] = None
    discount_amount: Optional[float] = None
    
class BankDetails(BaseModel):
    account_number: str
    confirm_account_number: str
    ifsc_code: str
    bank_name: str
    branch_name: str
    upi_id: Optional[str] = None
    upi_number: Optional[str] = None
    # opening_balance: Optional[float] = 0.0
    account_holder_name: Optional[str] = None
