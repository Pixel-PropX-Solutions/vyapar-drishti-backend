from app.Config import ENV_PROJECT
from app.database.models.Inventory import InventoryItem, InventoryItemDB
from .crud.base_mongo_crud import BaseMongoDbCrud


class InventoryRepo(BaseMongoDbCrud[InventoryItemDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "Inventory",
            unique_attributes=["vouchar_id", "item", "_id", "quantity", "rate"],
        )

    async def new(self, sub: InventoryItem):
        return await self.save(InventoryItemDB(**sub.model_dump()))


inventory_repo = InventoryRepo()
