from app.Config import ENV_PROJECT
from app.database.models.Debitor import Debitor, DebitorDB
from .crud.base_mongo_crud import BaseMongoDbCrud
from app.database.repositories.crud.base import (
    PageRequest,
    Meta,
    PaginatedResponse,
    Sort,
    SortingOrder,
)


class debitorRepo(BaseMongoDbCrud[DebitorDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE, "Debitor", unique_attributes=["name", "user_id"]
        )

    async def new(self, sub: Debitor):
        return await self.save(DebitorDB(**sub.model_dump()))


debitor_repo = debitorRepo()
