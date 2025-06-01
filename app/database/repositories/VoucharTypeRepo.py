from fastapi import Depends
from app.Config import ENV_PROJECT
from app.database.models.VoucharType import VoucherType, VoucherTypeDB
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


class VoucherTypeRepo(BaseMongoDbCrud[VoucherTypeDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "VoucherType",
            unique_attributes=["name", "user_id", "company_id"],
        )

    async def new(self, sub: VoucherType):
        return await self.save(VoucherTypeDB(**sub.model_dump()))



vouchar_type_repo = VoucherTypeRepo()
