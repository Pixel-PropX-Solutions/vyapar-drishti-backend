from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.oauth2 import get_current_user
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.database.models.VoucharCounter import VoucherCounter
from app.database.repositories.voucharCounterRepo import vouchar_counter_repo
from app.database.repositories.UserSettingsRepo import user_settings_repo
from datetime import datetime
import pytz

counter_router = APIRouter()


DEFAULT_VOUCHER_TYPES = {
    "Sales": {"prefix": "INV", "suffix": "", "separator": "-", "reset_cycle": "yearly"},
    "Purchase": {
        "prefix": "PUR",
        "suffix": "",
        "separator": "-",
        "reset_cycle": "yearly",
    },
    "Payment": {
        "prefix": "PAY",
        "suffix": "",
        "separator": "-",
        "reset_cycle": "monthly",
    },
    "Receipt": {
        "prefix": "REC",
        "suffix": "",
        "separator": "-",
        "reset_cycle": "monthly",
    },
    "Journal": {"prefix": "JRN", "suffix": "", "separator": "-", "reset_cycle": "yearly"},
    "Contra": {"prefix": "CON", "suffix": "", "separator": "-", "reset_cycle": "yearly"},
}


class CounterUpdateRequest(BaseModel):
    voucher_type: str
    financial_year: str
    current_number: int
    prefix: Optional[str] = ""
    suffix: Optional[str] = ""
    reset_cycle: Optional[str] = "yearly"


async def initialize_voucher_counters(user_id: str, company_id: str):
    now = datetime.now(tz=pytz.timezone("Asia/Kolkata"))
    counters = []

    for voucher_type, config in DEFAULT_VOUCHER_TYPES.items():
        counter = {
            "company_id": company_id,
            "user_id": user_id,
            "voucher_type": voucher_type,
            "current_number": 1,
            "prefix": config["prefix"],
            "suffix": config["suffix"],
            "separator": config["separator"],
            "reset_cycle": config["reset_cycle"],
            "created_at": now,
            "updated_at": now,
            "last_reset": now,
        }
        counters.append(counter)
        await vouchar_counter_repo.new(VoucherCounter(**counter))

    return {"message": "Voucher counters initialized", "count": len(counters)}


async def get_cuurent_counter(
    voucher_type: str,
    current_user: TokenData,
    company_id: str = "",
):
    query = {
        "company_id": current_user.current_company_id or company_id,
        "user_id": current_user.user_id,
        "voucher_type": voucher_type,
    }

    counter = await vouchar_counter_repo.findOne(query)

    # Format the current number with prefix, suffix, and padding
    if counter:
        pad_length = counter["pad_length"] or 4  # Default padding length if not set
        separator = counter["separator"]
        padded_number = str(counter["current_number"]).zfill(pad_length)
        if counter["suffix"]:
            formatted_number = f"{counter['prefix']}{separator}{padded_number}{separator}{counter['suffix']}"
        else:
            formatted_number = f"{counter['prefix']}{separator}{padded_number}"

    return formatted_number


@counter_router.get("/get/current/{voucher_type}", summary="Get voucher counter details")
async def get_counter(
    voucher_type: str,
    company_id: str = "",
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    query = {
        "company_id": current_user.current_company_id
        or userSettings["current_company_id"],
        "user_id": current_user.user_id,
        "voucher_type": voucher_type,
    }

    counter = await vouchar_counter_repo.findOne(query)

    # Format the current number with prefix, suffix, and padding
    if counter:
        pad_length = counter["pad_length"] or 4  # Default padding length if not set
        separator = counter["separator"]
        padded_number = str(counter["current_number"]).zfill(pad_length)
        if counter["suffix"]:
            formatted_number = f"{counter['prefix']}{separator}{padded_number}{separator}{counter['suffix']}"
        else:
            formatted_number = f"{counter['prefix']}{separator}{padded_number}"

    if not counter:
        raise HTTPException(status_code=404, detail="Counter not found")

    return {
        "success": True,
        "message": "Counter retrieved successfully",
        "data": {
            "voucher_type": counter["voucher_type"],
            "current_number": formatted_number,
        },
    }


@counter_router.put("/update", summary="Create or update a voucher counter")
async def update_counter(
    request: CounterUpdateRequest,
    company_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    query = {
        "company_id": current_user.current_company_id
        or userSettings["current_company_id"],
        "user_id": current_user.user_id,
        "voucher_type": request.voucher_type,
        "financial_year": request.financial_year,
    }

    update = {
        "$set": {
            "current_number": request.current_number,
            "prefix": request.prefix,
            "suffix": request.suffix,
            "reset_cycle": request.reset_cycle,
            "updated_at": datetime.utcnow(),
        },
        "$setOnInsert": {"created_at": datetime.utcnow(), "last_reset": None},
    }

    result = await vouchar_counter_repo.update_one(query, update, upsert=True)

    if result.upserted_id:
        return {"message": "Counter created", "id": str(result.upserted_id)}
    return {"message": "Counter updated"}


@counter_router.post("/reset", summary="Reset counters manually")
async def reset_counter(
    company_id: str,
    voucher_type: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    query = {
        "company_id": current_user.current_company_id
        or userSettings["current_company_id"],
        "user_id": current_user.user_id,
        "voucher_type": voucher_type,
    }

    counter = await vouchar_counter_repo.findOne(query)

    if not counter:
        raise HTTPException(status_code=404, detail="Counter not found")

    await vouchar_counter_repo.update_one(
        query,
        {
            "$set": {
                "current_number": 1,
                "last_reset": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        },
    )

    return {"message": "Counter reset to 1"}
