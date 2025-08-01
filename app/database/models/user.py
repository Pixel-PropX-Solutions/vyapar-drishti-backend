from typing import Union, List, Optional
from pydantic import BaseModel, Field
import datetime
from app.database.models.entity import Name, PhoneNumber
from app.schema.enums import UserTypeEnum
from uuid import uuid4


class User(BaseModel):
    name: Name
    email: str
    phone: PhoneNumber
    image: Optional[str] = None
    password: str
    user_type: Optional[UserTypeEnum] = UserTypeEnum.USER
    is_deleted: bool = False
    is_verified: bool = False

# db.users.dropIndex("email_1")
# db.users.createIndex({ phone: 1 }, { unique: true })

class UserDB(User):
    id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


class UserCreate(BaseModel):
    name: Name
    email: str
    phone: PhoneNumber
    password: str
