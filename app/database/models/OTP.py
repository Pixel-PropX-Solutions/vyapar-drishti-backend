# import datetime
# from uuid import uuid4
# from typing import List
# from pydantic import BaseModel, Field
# from app.schema.enums import UserTypeEnum


# class OTP(BaseModel):
#     phone_number: str
#     otp: str
#     user_type: UserTypeEnum


# class OTPDB(OTP):
#     id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
#     created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
#     updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
