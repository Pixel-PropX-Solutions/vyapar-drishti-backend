from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.Accounting import Accounting, AccountingDB
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


class AccountingRepo(BaseMongoDbCrud[AccountingDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "Accounting",
            unique_attributes=["vouchar_id", "ledger", "amount", "_id"],
        )

    async def new(self, sub: Accounting):
        return await self.save(AccountingDB(**sub.model_dump()))


accounting_repo = AccountingRepo()
