from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.oauth2 import get_current_user
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.database.models.CompanySettings import CompanySettings
from app.database.repositories.CompanySettingsRepo import company_settings_repo
from datetime import datetime
from uuid import uuid4
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)

company_settings_router = APIRouter()


async def initialize_company_settings(
    user_id: str,
    company_id: str,
    config: dict,
):
    """Initialize company settings with default values."""
    company_settings = {
        "company_id": company_id,
        "user_id": user_id,
        "company_name": config.get("company_name", "Default Company"),
        "books_start_date": config.get("financial_year", "2024-04-01"),
        "country": config.get("country", "India"),
        "state": config.get("state", "Rajasthan"),
        "features": {
            "enable_gst": config.get("enable_gst", False),
            "enable_inventory": config.get("enable_inventory", True),
        },
        "currency": config.get("currency", "INR"),
        "gst_details": {
            "gstin": config.get("gstin", None),
            "gst_registration_type": config.get("gst_registration_type", None),
            "place_of_supply": config.get("place_of_supply", None),
        },
        "is_deleted": False,
    }
    await company_settings_repo.new(CompanySettings(**company_settings))

    return {"message": "Company Settings initialized."}
