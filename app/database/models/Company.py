from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from app.database.models.entity import PhoneNumber
from typing import Optional


class Company(BaseModel):
    company_name: str

    # Primary Mailing Details
    user_id: str
    mailing_name: Optional[str] = None
    address_1: Optional[str] = None
    address_2: Optional[str] = None
    pinCode: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    # Contact Details
    phone: Optional[PhoneNumber] = None
    email: Optional[str] = None

    # Financial Year
    financial_year_start: str
    books_begin_from: str

    # Optional fields
    image: Optional[str] = None
    tin: Optional[str] = ""
    website: Optional[str] = None
    is_deleted: bool = False


class CompanyDB(Company):
    company_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class CompanyCreate(BaseModel):
    company_name: str

    # Primary Mailing Details
    user_id: str
    mailing_name: Optional[str] = None
    address_1: Optional[str] = None
    address_2: Optional[str] = None
    pinCode: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    # Contact Details
    phone: Optional[PhoneNumber] = None
    email: Optional[str] = None

    # Financial Year
    financial_year_start: datetime.date
    books_begin_from: datetime.date

    # Optional fields
    image: Optional[str] = None
    tin: Optional[str] = ""
    website: Optional[str] = None
    is_deleted: bool = False
