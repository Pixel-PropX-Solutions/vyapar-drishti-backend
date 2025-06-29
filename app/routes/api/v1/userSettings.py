from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
from typing import Dict, Optional, Any
from datetime import datetime
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
    status,
    Body,
)
from app.oauth2 import get_current_user
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.database.models.UserSettings import UserSettings
from app.database.repositories.UserSettingsRepo import user_settings_repo
from datetime import datetime
import pytz
from user_agents import parse

user_settings_router = APIRouter()


def extract_device_info(user_agent_str: str):
    ua = parse(user_agent_str)

    device_type = "Mobile" if ua.is_mobile else "Tablet" if ua.is_tablet else "PC"
    os = ua.os.family  # e.g., "Windows"
    os_version = ua.os.version_string  # e.g., "10"
    browser = ua.browser.family  # e.g., "Edge"
    
    browser_version = ua.browser.version_string  # e.g., "136.0.0.0"
    
    return f"{device_type} | OS: {os} {os_version} | Browser: {browser} {browser_version}"


async def initialize_user_settings(
    user_id: str,
    last_login_ip: Optional[str] = None,
    last_login_device: Optional[str] = None,
    role: str = "user",
):
    """Initialize user settings with default values."""
    now = datetime.now(tz=pytz.timezone("Asia/Kolkata"))
    user_settigs = {
        "user_id": user_id,
        "current_company_id": "",
        "current_company_name": "",
        "role": role,
        "is_deleted": False,
        "created_at": now,
        "updated_at": now,
        "last_login": now,
        "last_login_ip": last_login_ip,
        "last_login_device": extract_device_info(last_login_device),
    }
    await user_settings_repo.new(UserSettings(**user_settigs))

    return {"message": "User Settings initialized"}


@user_settings_router.put(
    "/update/{settings_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateUserSettings(
    settings_id: str,
    user_settings: Dict[str, Any] = Body(...),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne(
        {"_id": settings_id, "user_id": current_user.user_id, "is_deleted": False},
    )

    if userSettings is None:
        raise http_exception.ResourceNotFoundException()

    updated_dict = {}

    for k, v in dict(user_settings).items():
        if isinstance(v, str) and v not in ["", None]:
            updated_dict[k] = v
        elif isinstance(v, dict):
            temp_dict = {} 
            for k1, v1 in v.items():
                if isinstance(v1, str) and v1 not in ["", None]:
                    temp_dict[k1] = v1

            if temp_dict:  #
                updated_dict[k] = temp_dict

    await user_settings_repo.update_one(
        {"_id": settings_id, "user_id": current_user.user_id},
        {"$set": updated_dict, "$currentDate": {"updated_at": True}},
    )

    # Fetch the updated document after update
    updatedSettings = await user_settings_repo.findOne(
        {"_id": settings_id, "user_id": current_user.user_id, "is_deleted": False},
    )

    return {
        "success": True,
        "message": "User Settings Updated Successfully",
        "data": updatedSettings,
    }
