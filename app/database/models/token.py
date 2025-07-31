import datetime
from uuid import uuid4
from typing import List
from pydantic import BaseModel, Field

from app.database.models import CommonData
from app.schema.enums import UserTypeEnum


class RefreshTokenCreate(BaseModel):
    refresh_token: str
    user_id: str
    user_type: UserTypeEnum
    device_type: str
    token_version: int = 1  


class RefreshTokenDB(RefreshTokenCreate):
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class RefreshTokenOut(RefreshTokenCreate, CommonData): ...
