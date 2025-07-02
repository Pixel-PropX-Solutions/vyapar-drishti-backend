from typing import Union, List, Optional
from pydantic import BaseModel, Field
import datetime
from app.database.models.entity import Name, PhoneNumber
from app.schema.enums import UserTypeEnum
from uuid import uuid4


class UOM(BaseModel):
    unit_name: str
    company_id: str
    user_id: str
    formalname: str = ""
    is_simple_unit: int
    base_units: str = ""
    additional_units: str = ""
    conversion: int


class UOMDB(UOM):
    unit_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class UOMCreate(BaseModel):
    unit_name: str
    company_id: str
    user_id: str
    formalname: str = ""
    is_simple_unit: int
    base_units: str = ""
    additional_units: str = ""
    conversion: int


class UOMUpdate(BaseModel):
    unit_name: Optional[str] = None
    formalname: Optional[str] = None
    is_simple_unit: Optional[int] = None
    base_units: Optional[str] = None
    additional_units: Optional[str] = None
    conversion: Optional[int] = None
