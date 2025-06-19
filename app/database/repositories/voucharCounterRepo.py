from app.Config import ENV_PROJECT
from app.database.models.VoucharCounter import VoucherCounter, VoucherCounterDB
from .crud.base_mongo_crud import BaseMongoDbCrud


class VoucherCounterRepo(BaseMongoDbCrud[VoucherCounterDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "VoucherCounter",
            unique_attributes=["voucher_type", "company_id", "user_id"],
        )

    async def new(self, sub: VoucherCounter):
        return await self.save(VoucherCounterDB(**sub.model_dump()))


vouchar_counter_repo = VoucherCounterRepo()
