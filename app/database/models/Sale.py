# from pydantic import BaseModel, Field
# import datetime
# from uuid import uuid4
# from enum import Enum
# from app.database.models.entity import ProductDetails
# from app.schema.enums import Status, PaymentMode


# class Sale(BaseModel):
#     status: Status = Status.PENDING
#     creditor_id: str
#     user_id: str
#     debitor_id: str
#     sale_number: str
#     product_details: list[ProductDetails]
#     date: str
#     due_date: str
#     payment_method: PaymentMode = PaymentMode.CASH
#     gst_total: float
#     total_discount: float
#     total_amount: float
#     total_tax_amount: float
#     round_off_amount: float
#     grand_total: float


# class SaleDB(Sale):
#     sale_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
#     updated_at: datetime.datetime = Field(
#         default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
#     )
#     created_at: datetime.datetime = Field(
#         default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
#     )


# class SaleCreate(BaseModel):
#     status: Status = Status.PENDING
#     creditor_id: str
#     user_id: str
#     debitor_id: str
#     sale_number: str
#     product_details: list[ProductDetails]
#     date: str
#     due_date: str
#     payment_method: PaymentMode = PaymentMode.CASH
#     gst_total: float
#     discount: float
#     total_amount: float
#     tax_amount: float
#     round_off_amount: float
#     grand_total: float
