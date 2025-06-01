# from fastapi import (
#     APIRouter,
#     Depends,
#     Form,
#     status,
# )
# from fastapi.responses import ORJSONResponse
# from pydantic import BaseModel
# import app.http_exception as http_exception
# from app.schema.token import TokenData
# import app.http_exception as http_exception
# from app.oauth2 import get_current_user
# # from app.database.repositories.company import billing_repo, Billing
# from app.schema.token import TokenData
# from app.database.repositories.company import company_repo
# from typing import Optional


# billing = APIRouter()


# class TenantID(BaseModel):
#     tenant_id: Optional[str] = None
#     tenant_email: Optional[str] = None


# class Email_Body(BaseModel):
#     email: str


# @billing.post(
#     "/create/billing", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
# )
# async def create_billing(
#     # company_id: str = Form(...),
#     state: str = Form(...),
#     address_1: str = Form(...),
#     address_2: str = Form(None),
#     pinCode: str = Form(None),
#     city: str = Form(None),
#     country: str = Form(None),
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "user" and current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()    
    
#     billing_data = {
#         "user_id": current_user.user_id,
#         # "company_id": company_id,
#         "state": state,
#         "address_1": address_1,
#         "address_2": address_2,
#         "pinCode": pinCode,
#         "city": city,
#         "country": country,
#         "is_deleted": False,
#     }
    

#     response = await billing_repo.new(Billing(**billing_data))
#     if not response:
#         raise http_exception.ResourceNotFoundException(detail="Billing Address Not Created")
    
#     return {"success": True, "message": "Billing Address Created", "data": response}


# @billing.get(
#     "/get/billing/{billing_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def get_billing(
#     billing_id: str, current_user: TokenData = Depends(get_current_user)
# ):
#     from app.database.repositories.company import billing_repo

#     billing = await billing_repo.findOne(
#         {"_id": billing_id, "user_id": current_user.user_id}
#     )
#     if not billing:
#         raise http_exception.ResourceNotFoundException(detail="Billing Address Not Found")
#     return {"success": True, "data": billing}


# @billing.get(
#     "/get/all/billing",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def get_all_billing(current_user: TokenData = Depends(get_current_user)):

#     if current_user.user_type != "user" and current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()

#     billing = await billing_repo.collection.aggregate(
#         [
#             {
#                 "$match": {
#                     "user_id": current_user.user_id,
#                     "is_deleted": False,
#                 }
#             },
#             {
#                 "$project": {
#                     "created_at": 0,
#                     "updated_at": 0,
#                 }
#             },
#         ]
#     ).to_list(None)

#     if not billing:
#         raise http_exception.ResourceNotFoundException(detail="Billing Address Not Found")

#     return {"success": True, "data": billing}


# @billing.put(
#     "/update/billing/{billing_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def update_billing(
#     billing_id: str,
#     state: str = Form(...),
#     address_1: str = Form(...),
#     address_2: str = Form(None),
#     pinCode: str = Form(None),
#     city: str = Form(None),
#     country: str = Form(None),
#     current_user: TokenData = Depends(get_current_user),
# ):

#     update_fields = {
#         "state": state,
#         "address_1": address_1,
#         "address_2": address_2,
#         "pinCode": pinCode,
#         "city": city,
#         "country": country,
#     }
#     await billing_repo.update_one(
#         {"_id": billing_id, "user_id": current_user.user_id}, {"$set": update_fields}
#     )
#     return {"success": True, "message": "Billing Address Updated"}


# @billing.delete(
#     "/delete/billing/{billing_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def delete_billing(
#     billing_id: str, current_user: TokenData = Depends(get_current_user)
# ):
#     # from app.database.repositories.company import billing_repo
#     billing = await billing_repo.findOne(
#         {"_id": billing_id, "user_id": current_user.user_id}
#     )

#     if not billing:
#         raise http_exception.ResourceNotFoundException(detail="Billing Address Not Found")

#     if billing.get("is_deleted", True):
#         raise http_exception.ResourceNotFoundException(
#             detail="Billing Address Already Deleted"
#         )

#     # Mark the billing address as deleted instead of removing it
#     await billing_repo.update_one(
#         {"_id": billing_id, "user_id": current_user.user_id},
#         {"$set": {"is_deleted": True}},
#     )
#     # await billing_repo.delete_one({"_id": billing_id, "user_id": current_user.user_id})

#     return {"success": True, "message": "Billing Address Deleted"}


# @billing.put(
#     "/restore/billing/{billing_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def restore_billing(
#     billing_id: str, current_user: TokenData = Depends(get_current_user)
# ):
#     billing = await billing_repo.findOne(
#         {"_id": billing_id, "user_id": current_user.user_id, "is_deleted": True}
#     )

#     if not billing:
#         raise http_exception.ResourceNotFoundException(detail="Billing Address Not Found")

#     await billing_repo.update_one(
#         {"_id": billing_id, "user_id": current_user.user_id, "is_deleted": True},
#         {"$set": {"is_deleted": False}},
#     )

#     return {"success": True, "message": "Billing Address Restored"}
