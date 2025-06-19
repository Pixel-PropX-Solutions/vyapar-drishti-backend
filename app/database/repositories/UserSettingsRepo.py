from app.Config import ENV_PROJECT
from app.database.models.UserSettings import UserSettings, UserSettingsDB
from .crud.base_mongo_crud import BaseMongoDbCrud


class UserSettingsRepo(BaseMongoDbCrud[UserSettingsDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "UserSettings",
            unique_attributes=["current_company_id", "user_id", "role", 'last_login'],
        )

    async def new(self, sub: UserSettings):
        return await self.save(UserSettingsDB(**sub.model_dump()))


user_settings_repo = UserSettingsRepo()
