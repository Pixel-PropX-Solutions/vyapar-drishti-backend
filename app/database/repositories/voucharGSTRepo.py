from app.Config import ENV_PROJECT
from app.database.models.VoucharGST import VoucherGST, VoucherGSTDB
from .crud.base_mongo_crud import BaseMongoDbCrud


class VoucherGSTRepo(BaseMongoDbCrud[VoucherGSTDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "VoucherGST",
            unique_attributes=[
                "voucher_id",
                "is_gst_applicable",
                "user_id",
                "company_id",
                "party_gstin",
                "place_of_supply",
            ],
        )

    async def new(self, sub: VoucherGST):
        return await self.save(VoucherGSTDB(**sub.model_dump()))


vouchar_gst_repo = VoucherGSTRepo()
