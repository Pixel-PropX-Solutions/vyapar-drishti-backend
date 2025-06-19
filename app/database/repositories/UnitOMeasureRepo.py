from app.Config import ENV_PROJECT
from app.database.models.UnitOMeasure import UOM, UOMDB
from .crud.base_mongo_crud import BaseMongoDbCrud


class UnitOMeasureRepo(BaseMongoDbCrud[UOMDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE,
            "UnitsOfMeasure",
            unique_attributes=["unit_name", "formalname", "user_id", 'company_id'],
        )

    async def new(self, sub: UOM):
        return await self.save(UOMDB(**sub.model_dump()))


units_repo = UnitOMeasureRepo()
