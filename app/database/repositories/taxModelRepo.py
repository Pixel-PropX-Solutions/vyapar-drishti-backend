from typing import List

from fastapi import status
from loguru import logger
from pymongo.errors import DuplicateKeyError

from app.Config import ENV_PROJECT
from app import http_exception

from app.database.models.TaxModel import TaxModel, TaxModelDB
from .crud.base_mongo_crud import BaseMongoDbCrud


class TaxModelRepository(BaseMongoDbCrud[TaxModelDB]):
    def __init__(self):
        super().__init__(
            ENV_PROJECT.MONGO_DATABASE, "TaxModel", unique_attributes=["tax_code", 'tax_name']
        )

    async def new(self, data: TaxModel):
        data = TaxModelDB(**data.model_dump())
        try:
            res = await self.save(data)
            return res
        except DuplicateKeyError as e:
            logger.error(e)
            raise http_exception.ResourceConflictException()
        except Exception as e:
            logger.error(e)
            raise http_exception.InternalServerErrorException()
        


tax_model_repo = TaxModelRepository()
