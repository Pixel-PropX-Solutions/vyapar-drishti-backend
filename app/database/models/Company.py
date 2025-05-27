from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from app.database.models.entity import PhoneNumber
from typing import Optional


class Company(BaseModel):
    user_id: str
    brand_name: str
    company_name: str
    phone: Optional[PhoneNumber] = None
    email: Optional[str] = None

    # Optional fields
    image: Optional[str] = None
    gstin: Optional[str] = None
    pan_number: Optional[str] = None
    business_type: Optional[str] = None
    website: Optional[str] = None
    alter_phone: Optional[PhoneNumber] = None
    billing: Optional[str] = None
    shipping: Optional[str] = None

class CompanyDB(Company):
    company_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class CompanyCreate(BaseModel):
    user_id: str
    brand_name: str
    company_name: str