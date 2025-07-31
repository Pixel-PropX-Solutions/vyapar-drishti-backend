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
    Request,
    Response,
    Header,
)
from app.oauth2 import get_current_user, create_access_token, set_cookies
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.database.models.UserSettings import UserSettings
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.database.repositories.companyRepo import company_repo
from datetime import datetime
import pytz
from user_agents import parse
from device_detector import DeviceDetector

user_settings_router = APIRouter()


def extract_device_info(user_agent_str: str):
    ua = parse(user_agent_str)

    device_type = "Mobile" if ua.is_mobile else "Tablet" if ua.is_tablet else "PC"
    os = ua.os.family  # e.g., "Windows"
    os_version = ua.os.version_string  # e.g., "10"
    browser = ua.browser.family  # e.g., "Edge"

    browser_version = ua.browser.version_string  # e.g., "136.0.0.0"

    return f"{device_type} | OS: {os} {os_version} | Browser: {browser} {browser_version}"


def classify_client(user_agent_str: str) -> Dict[str, str]:
    if not user_agent_str:
        return {
            "info": "Unknown | OS: Unknown | Browser: Unknown",
            "device_type": "Unknown",
        }

    # Try DeviceDetector first
    dd = DeviceDetector(user_agent_str).parse()

    if dd.is_bot():
        bot_name = dd.bot_name() or "Unknown Bot"
        bot_type = dd.bot_type() or "Unknown Type"
        return {
            "info": f"Bot | Type: {bot_type} | Name: {bot_name}",
            "device_type": "Bot",
        }

    # Then try user_agents
    ua = parse(user_agent_str)

    if ua.is_pc:
        device_type = "PC"
    elif ua.is_tablet:
        device_type = "Tablet"
    elif ua.is_mobile:
        device_type = "Mobile"
    else:
        device_type = "Other"

    os = ua.os.family or "Unknown"
    os_version = ua.os.version_string or ""
    browser = ua.browser.family or "Unknown"
    browser_version = ua.browser.version_string or ""

    # Heuristic for identifying apps
    app_indicators = ["okhttp", "dalvik", "cfnetwork", "okhttp", "curl", "python", "java"]
    if any(indicator in user_agent_str.lower() for indicator in app_indicators):
        return {
            "info": f"App | OS: {os} {os_version} | Agent: {browser} {browser_version}",
            "device_type": "App",
        }

    return {
        "info": f"{device_type} | OS: {os} {os_version} | Browser: {browser} {browser_version}",
        "device_type": device_type,
    }


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


@user_settings_router.post(
    "/switch-company/{company_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def switch_company(
    request: Request,
    response: Response,
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    # Optional: Validate company belongs to user
    company = await company_repo.findOne(
        {"_id": company_id, "user_id": current_user.user_id}
    )
    if not company:
        raise http_exception.ResourceNotFoundException("Company not found.")

    client_info = classify_client(request.headers.get("user-agent", "unknown"))

    if client_info.get("device_type") in ["Unknown", "Bot"]:
        raise http_exception.UnknownDeviceException(
            detail="Try accessing via another device. This device is compromised or not supported."
        )

    new_token_data = TokenData(
        user_id=current_user.user_id,
        user_type=current_user.user_type,
        scope=current_user.scope,
        current_company_id=company_id,
        device_type=client_info.get("device_type"),
    )

    token_generated = await create_access_token(
        new_token_data, device_type=client_info.get("device_type")
    )
    set_cookies(response, token_generated.access_token, token_generated.refresh_token)

    return {
        "success": True,
        "accessToken": token_generated.access_token,
        "refreshToken": token_generated.refresh_token,
        "message": "Switched to company successfully.",
    }
