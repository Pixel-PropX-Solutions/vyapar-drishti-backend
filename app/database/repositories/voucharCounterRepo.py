from app.Config import ENV_PROJECT
from app.database.models.VoucharCounter import VoucherCounter, VoucherCounterDB
from .crud.base_mongo_crud import BaseMongoDbCrud
import datetime


class VoucherCounterRepo(BaseMongoDbCrud[VoucherCounterDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "VoucherCounter",
            unique_attributes=["voucher_type", "company_id", "user_id"],
        )

    async def new(self, sub: VoucherCounter):
        return await self.save(VoucherCounterDB(**sub.model_dump()))

    async def increaseVoucharCounter(
        self, voucher_type: str, company_id: str, user_id: str
    ) -> str:
        """
        Increase the voucher counter for a specific voucher type.
        This method reserves the next voucher number and updates the counter.
        """
        query = {
            "voucher_type": voucher_type,
            "company_id": company_id,
            "user_id": user_id,
        }
        vouchar_counter = await self.findOne(query)

        if not vouchar_counter:
            raise ValueError("Voucher counter not found for the given parameters.")

        await self.update_one(
            query,
            {
                "$inc": {"current_number": 1},
                "$set": {"updated_at": datetime.datetime.utcnow()},
            },
        )

        return {
            "success": True,
            "message": "Vouchar Counter Increased Successfully",
        }

    async def decreaseVoucharCounter(
        self, voucher_type: str, company_id: str, user_id: str
    ) -> str:
        """
        Decrease the voucher counter for a specific voucher type.
        This method decrements the current number in the counter.
        """
        query = {
            "voucher_type": voucher_type,
            "company_id": company_id,
            "user_id": user_id,
        }
        vouchar_counter = await self.findOne(query)

        if not vouchar_counter:
            raise ValueError("Voucher counter not found for the given parameters.")

        await self.update_one(
            query,
            {
                "$inc": {"current_number": -1},
            },
        )

        return {
            "success": True,
            "message": "Vouchar Counter Decreased Successfully",
        }


vouchar_counter_repo = VoucherCounterRepo()
