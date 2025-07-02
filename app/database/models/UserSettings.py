import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class UserPermissions(BaseModel):
    create_vouchers: bool = True
    # delete_ledgers: bool = False
    # view_reports: bool = True
    # export_data: bool = False
    # approve_vouchers: bool = False


class UIPreferences(BaseModel):
    theme: str = "light"  # or 'dark'
    # default_voucher_type: Optional[str] = "Sales"
    # autosave_interval: int = 5  # in minutes
    # language: str = "en"


class UserSettings(BaseModel):
    user_id: str
    current_company_id: str
    current_company_name: str
    role: str = "User"

    permissions: UserPermissions = Field(default_factory=UserPermissions)
    ui_preferences: UIPreferences = Field(default_factory=UIPreferences)

    # Activity
    last_login: Optional[datetime.datetime] = None
    last_login_ip: Optional[str] = None
    last_login_device: Optional[str] = None
    is_deleted: bool = False


class UserSettingsDB(UserSettings):
    settings_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now())
