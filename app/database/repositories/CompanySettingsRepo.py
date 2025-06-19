from app.Config import ENV_PROJECT
from app.database.models.CompanySettings import CompanySettings, CompanySettingsDB
from .crud.base_mongo_crud import BaseMongoDbCrud


class CompanySettingsRepo(BaseMongoDbCrud[CompanySettingsDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "CompanySettings",
            unique_attributes=[
                "user_id",
                "company_id",
                "company_name",
                "state",
                "books_start_date",
            ],
        )

    async def new(self, sub: CompanySettings):
        return await self.save(CompanySettingsDB(**sub.model_dump()))


company_settings_repo = CompanySettingsRepo()
