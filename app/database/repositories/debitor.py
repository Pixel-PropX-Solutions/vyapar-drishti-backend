# from app.Config import ENV_PROJECT
# from app.database.models.Debitor import Debitor, DebitorDB
# from .crud.base_mongo_crud import BaseMongoDbCrud
# from app.database.repositories.crud.base import (
#     PageRequest,
#     Meta,
#     PaginatedResponse,
#     Sort,
#     SortingOrder,
# )


# class debitorRepo(BaseMongoDbCrud[DebitorDB]):
#     def __init__(self):
#         super().__init__(
#             ENV_PROJECT.MONGO_DATABASE, "Debitor", unique_attributes=["name", "user_id"]
#         )

#     async def new(self, sub: Debitor):
#         return await self.save(DebitorDB(**sub.model_dump()))

#     async def viewAllDebitors(
#         self,
#         search: str,
#         is_deleted: bool,
#         pagination: PageRequest,
#         sort: Sort,
#         current_user_id: str = None,
#     ):
#         filter_params = {}
#         if search not in ["", None]:
#             filter_params["$or"] = [
#                 {"email": {"$regex": f"^{search}", "$options": "i"}},
#                 {
#                     "name": {
#                         "$regex": f"^{search}",
#                         "$options": "i",
#                     }
#                 },
#                 {
#                     "company_name": {
#                         "$regex": f"^{search}",
#                         "$options": "i",
#                     }
#                 },
#                 {
#                     "tags": {
#                         "$regex": f"^{search}",
#                         "$options": "i",
#                     }
#                 },
#             ]

#         sort_fields_mapping = {
#             "name": "name",
#             "company_name": "company_name",
#             "debit_limit": "debit_limit",
#             "balance_type": "balance_type",
#             "city": "billing.city",
#             "state": "billing.state",
#             "created_at": "created_at",
#         }

#         sort_field_mapped = sort_fields_mapping.get(sort.sort_field, "name")
#         sort_order_value = 1 if sort.sort_order == SortingOrder.ASC else -1
#         sort_criteria = {sort_field_mapped: sort_order_value}

#         pipeline = []
#         pipeline.extend(
#             [
#                 {"$match": {"is_deleted": is_deleted, "user_id": current_user_id}},
#                 {
#                     "$lookup": {
#                         "from": "Billing",
#                         "localField": "billing",
#                         "foreignField": "_id",
#                         "as": "billing",
#                     }
#                 },
#                 {"$unwind": {"path": "$billing", "preserveNullAndEmptyArrays": True}},
#                 {
#                     "$project": {
#                         "billing.user_id": 0,
#                         "billing.updated_at": 0,
#                     }
#                 },
#                 {"$match": filter_params},
#                 {"$sort": sort_criteria},
#             ]
#         )

#         pipeline.append(
#             {
#                 "$facet": {
#                     "docs": [
#                         {
#                             "$skip": (pagination.paging.page - 1)
#                             * (pagination.paging.limit)
#                         },
#                         {"$limit": pagination.paging.limit},
#                     ],
#                     "count": [{"$count": "count"}],
#                 }
#             }
#         )

#         unique_states_pipeline = [
#             {"$match": {"user_id": current_user_id}},
#             {
#                 "$lookup": {
#                     "from": "Billing",
#                     "localField": "billing",
#                     "foreignField": "_id",
#                     "as": "billing",
#                 }
#             },
#             {"$unwind": {"path": "$billing", "preserveNullAndEmptyArrays": True}},
#             {
#                 "$project": {
#                     "billing_state": "$billing.state",
#                 }
#             },
#             {
#                 "$project": {
#                     "states": {
#                         "$setUnion": [
#                             {
#                                 "$cond": [
#                                     {
#                                         "$and": [
#                                             {"$ne": ["$billing_state", None]},
#                                             {"$ne": ["$billing_state", ""]},
#                                         ]
#                                     },
#                                     ["$billing_state"],
#                                     [],
#                                 ]
#                             },
#                         ]
#                     }
#                 }
#             },
#             {"$unwind": "$states"},
#             {"$group": {"_id": "$states"}},
#             {"$sort": {"_id": 1}},
#             {"$project": {"state": "$_id", "_id": 0}},
#         ]

#         res = [doc async for doc in self.collection.aggregate(pipeline)]
#         states_res = [
#             doc async for doc in self.collection.aggregate(unique_states_pipeline)
#         ]
#         docs = res[0]["docs"]
#         count = res[0]["count"][0]["count"] if len(res[0]["count"]) > 0 else 0
#         unique_states = [entry["state"] for entry in states_res]

#         return PaginatedResponse(
#             docs=docs,
#             meta=Meta(
#                 **pagination.paging.model_dump(), total=count, unique=unique_states
#             ),
#         )


# debitor_repo = debitorRepo()
