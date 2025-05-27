# from fastapi import APIRouter, Depends, File, UploadFile
# from app.utils.cloudinary_client import cloudinary_client
# import app.http_exception as http_exception
# from app.schema.token import TokenData
# import app.http_exception as http_exception
# from app.oauth2 import get_current_user
# from app.schema.token import TokenData


# Cloudinary = APIRouter()


# @Cloudinary.post("/upload-image")
# async def upload_image(
#     image: UploadFile = File(...),
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "user" and current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()
#     if not image:
#         raise http_exception.BadRequestException(detail="No image provided")

#     if image.content_type not in ["image/jpeg", "image/jpg", "image/png", "image/gif"]:
#         raise http_exception.BadRequestException(
#             detail="Invalid image type. Only JPEG, JPG, PNG, and GIF are allowed."
#         )
#     if image.size > 5 * 1024 * 1024:  # 5 MB limit
#         raise http_exception.BadRequestException(
#             detail="File size exceeds the 5 MB limit."
#         )

#     result = await cloudinary_client.upload_file(image)
#     return {"message": "Upload successful", "data": result, "success": True}
