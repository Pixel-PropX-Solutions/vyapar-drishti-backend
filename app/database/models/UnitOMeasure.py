from typing import Optional
from pydantic import BaseModel, Field, validator
from uuid import uuid4
import datetime
from enum import Enum


class SIRepresentationEnum(str, Enum):
    integer = "integer"
    decimal = "decimal"


class UOM(BaseModel):
    unit_name: str
    company_id: str
    user_id: str
    formalname: str = ""
    is_simple_unit: bool = False
    base_units: str = ""
    additional_units: str = ""
    conversion: float = 1
    si_representation: SIRepresentationEnum
    description: Optional[str] = ""
    symbol: Optional[str] = ""
    is_deleted: bool = False

    @validator("unit_name", pre=True)
    def normalize_unit_name(cls, v):
        return v.strip().lower()


class UOMDB(UOM):
    unit_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class UOMCreate(BaseModel):
    unit_name: str
    company_id: str
    user_id: str
    formalname: str = ""
    is_simple_unit: bool = False
    base_units: str = ""
    additional_units: str = ""
    conversion: float
    si_representation: SIRepresentationEnum
    description: Optional[str] = ""
    symbol: Optional[str] = ""


class UOMUpdate(BaseModel):
    unit_id: str
    company_id: str
    user_id: str
    unit_name: Optional[str] = None
    formalname: Optional[str] = None
    is_simple_unit: Optional[bool] = False
    base_units: Optional[str] = None
    additional_units: Optional[str] = None
    conversion: Optional[float] = None
    si_representation: Optional[SIRepresentationEnum] = None
    description: Optional[str] = None
    symbol: Optional[str] = None
