from app.Config import ENV_PROJECT
from app.database.models.GST_Rate import GSTRate, GSTRateDB
from .crud.base_mongo_crud import BaseMongoDbCrud


class GSTRateRepo(BaseMongoDbCrud[GSTRateDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "GSTRate",
            unique_attributes=["item", "_item", "user_id", 'company_id', 'hsn_code'],
        )

    async def new(self, sub: GSTRate):
        return await self.save(GSTRateDB(**sub.model_dump()))


gst_rate_repo = GSTRateRepo()
