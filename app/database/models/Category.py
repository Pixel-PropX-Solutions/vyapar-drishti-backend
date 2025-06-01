from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import Optional


# Base Category Schema
class Category(BaseModel):
    # required fields
    name: str
    under: Optional[str] = "Primary" 
    company_id: str
    user_id: str
    is_deleted: bool
    image: str | None
    description: str | None


# Database Schema
class CategoryDB(Category):
    category_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


# Schema for Creating a New Category
class CategoryCreate(BaseModel):
    # required fields
    name: str
    user_id: str
    under: Optional[str] = "Primary" 
    image: Optional[str] = None
    description: Optional[str] = None
    is_deleted: Optional[bool] = False
