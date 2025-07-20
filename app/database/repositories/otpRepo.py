# from .crud.base_mongo_crud import BaseMongoDbCrud
# from app.database.models.OTP import OTP, OTPDB
# from app.Config import ENV_PROJECT


# class OTPRepository(BaseMongoDbCrud[OTPDB]):
#     """Repository for handling OTP operations."""
#     def __init__(self):
#         super().__init__(
#             ENV_PROJECT.MONGO_DATABASE,
#             "OTP",
#             unique_attributes=["phone_number", "otp"],
#         )

#     async def new(self, sub: OTPDB):
#         return await self.save(OTPDB(**sub.model_dump()))


# otp_repo = OTPRepository()