from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.Company import Company, CompanyDB
from app.oauth2 import get_current_user
from app.schema.token import TokenData
from .crud.base_mongo_crud import BaseMongoDbCrud
from app.database.repositories.crud.base import (
    PageRequest,
    Meta,
    PaginatedResponse,
    SortingOrder,
    Sort,
    Page,
)
from pydantic import BaseModel
from typing import List
import re


class CompanyRepo(BaseMongoDbCrud[CompanyDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE, "Company", unique_attributes=["company_name", "user_id", 'state', 'country']
        )

    async def new(self, sub: Company):
        return await self.save(CompanyDB(**sub.model_dump()))


company_repo = CompanyRepo()

