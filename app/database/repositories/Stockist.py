# from app.Config import ENV_PROJECT
# from app.database.models.Company import Company, CompanyDB
# from .crud.base_mongo_crud import BaseMongoDbCrud

# class CompanyRepo(BaseMongoDbCrud[CompanyDB]):
#     def __init__(self):
#         super().__init__(
#             ENV_PROJECT.MONGO_DATABASE, "Stockist", unique_attributes=[]
#         )

#     async def new(self, sub: Company):
#         return await self.save(
#             CompanyDB(**sub.model_dump())
#         )

# company_repo = CompanyRepo()
