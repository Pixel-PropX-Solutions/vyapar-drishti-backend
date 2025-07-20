from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import Optional


# Base Category Schema
class Category(BaseModel):
    # required fields
    category_name: str
    company_id: str
    user_id: str
    is_deleted: bool = False
    image: Optional[str] = None
    description: Optional[str] = None


# Database Schema
class CategoryDB(Category):
    category_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())


# Schema for Creating a New Category
class CategoryCreate(BaseModel):
    # required fields
    category_name: str
    user_id: str
    company_id: str
    image: Optional[str] = None
    description: Optional[str] = None
    is_deleted: Optional[bool] = False
