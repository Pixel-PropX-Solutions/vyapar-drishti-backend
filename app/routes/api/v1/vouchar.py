import json
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from app.database.repositories.CompanySettingsRepo import company_settings_repo
from app.database.repositories.companyRepo import company_repo
from fastapi.responses import ORJSONResponse, HTMLResponse
from pydantic import BaseModel
import app.http_exception as http_exception
from app.routes.api.v1.taxModel import generate_tax_summary, get_current_user_tax_model
from app.schema.token import TokenData
from app.oauth2 import get_current_user
from app.database.repositories.voucharRepo import vouchar_repo
from app.routes.api.v1.voucharCounter import get_cuurent_counter
from app.database.repositories.voucharCounterRepo import vouchar_counter_repo
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.database.repositories.ledgerRepo import ledger_repo
from app.database.repositories.accountingRepo import accounting_repo
from app.database.repositories.InventoryRepo import inventory_repo
from app.database.models.Vouchar import Voucher, VoucherCreate, VoucherUpdate
from app.database.models.VoucharCounter import VoucherCounter
from app.database.models.Accounting import Accounting, AccountingUpdate
from typing import Optional, List
from app.database.models.Inventory import (
    InventoryItem,
    UpdateInventoryItemWithTAX,
    CreateInventoryItemWithTAX,
)
from fastapi import Query
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest
from app.database.repositories.stockItemRepo import stock_item_repo
from jinja2 import Template
import aiofiles
from num2words import num2words
from math import ceil
import sys
import asyncio
from datetime import datetime
import calendar

# from playwright.async_api import async_playwright

Vouchar = APIRouter()


class VoucherWithTAXCreate(BaseModel):
    company_id: str
    date: str
    voucher_type: str
    voucher_type_id: str
    voucher_number: str
    party_name: str
    party_name_id: str
    narration: Optional[str] = ""
    reference_number: Optional[str] = None
    reference_date: Optional[str] = None
    place_of_supply: Optional[str] = None
    vehicle_number: Optional[str] = None
    mode_of_transport: Optional[str] = None
    payment_mode: Optional[str] = None
    due_date: Optional[str] = None

    paid_amount: Optional[float] = 0.0  # Amount paid by the customer
    total: Optional[float] = 0.0  # Total amount before taxes and discounts
    discount: Optional[float] = 0.0  # Discount applied to the invoice
    total_amount: Optional[float] = 0.0  # Total amount after discounts but before taxes
    total_tax: Optional[float] = 0.0  # Total tax applied to the invoice
    additional_charge: Optional[float] = 0.0  # Any additional charges applied
    roundoff: Optional[float] = 0.0  # Round off amount
    grand_total: float  # Total amount including taxes, discounts, and additional charges
    accounting: List[Accounting]
    items: List[CreateInventoryItemWithTAX]


class TAXVoucherUpdate(BaseModel):
    vouchar_id: str
    user_id: str
    company_id: str
    date: str
    voucher_type: str
    voucher_type_id: str
    voucher_number: str
    party_name: str
    party_name_id: str
    narration: Optional[str]
    reference_number: Optional[str]
    reference_date: Optional[str]
    place_of_supply: Optional[str]
    vehicle_number: Optional[str] = None
    mode_of_transport: Optional[str] = None
    payment_mode: Optional[str] = None
    due_date: Optional[str] = None
    paid_amount: Optional[float] = 0.0  # Amount paid by the customer
    total: Optional[float] = 0.0  # Total amount before taxes and discounts
    discount: Optional[float] = 0.0  # Discount applied to the invoice
    total_amount: Optional[float] = 0.0  # Total amount after discounts but before taxes
    total_tax: Optional[float] = 0.0  # Total tax applied to the invoice
    additional_charge: Optional[float] = 0.0  # Any additional charges applied
    roundoff: Optional[float] = 0.0  # Round off amount
    grand_total: float  # Total amount including taxes, discounts, and additional charges

    accounting: List[AccountingUpdate]
    items: Optional[List[UpdateInventoryItemWithTAX]]


async def render_paginated_html(template_path, template_vars, items, items_per_page=17):
    """
    Splits items into pages, renders HTML for each page, and returns all rendered HTMLs.
    """
    pages = [items[i : i + items_per_page] for i in range(0, len(items), items_per_page)]
    rendered_pages = []
    async with aiofiles.open(template_path, "r") as f:
        template_str = await f.read()
    template = Template(template_str)
    for page_items in pages:
        page_vars = dict(template_vars)
        page_vars["invoice"]["items"] = page_items
        page_vars["no_of_items"] = len(page_items)
        page_vars["invoice"]["page_number"] = len(rendered_pages) + 1
        page_vars["invoice"]["total_pages"] = len(pages)
        html = template.render(**page_vars)
        rendered_pages.append({"html": html, "page_number": len(rendered_pages) + 1})
    return rendered_pages


@Vouchar.post(
    "/create/vouchar", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createVouchar(
    vouchar: VoucherCreate,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    companyExists = await company_repo.findOne(
        {"_id": current_user.current_company_id, "user_id": current_user.user_id}
    )

    if not companyExists:
        raise http_exception.ResourceNotFoundException(
            detail="Company not found. Please check your company ID."
        )

    db_invoice_no = await get_cuurent_counter(
        voucher_type=vouchar.voucher_type,
        company_id=current_user.current_company_id,
        current_user=current_user,
    )

    shouldIncreaseCounter = db_invoice_no == vouchar.voucher_number
    shouldDecreaseCounter = False

    if len(vouchar.date) < 10:
        # Assuming the date is in 'YYYY-MM-DD' format, we can pad it with zeros where required.
        # e.g '2023-01-1' should become '2023-01-01', '2023-1-1' should become '2023-01-01', '2023-1-01' should become '2023-01-01'.
        parts = vouchar.date.split("-")
        for i in range(len(parts)):
            parts[i] = parts[i].zfill(2)
        vouchar.date = "-".join(parts)

    vouchar_data = {
        "user_id": current_user.user_id,
        "company_id": current_user.current_company_id,
        "date": vouchar.date,
        "voucher_number": vouchar.voucher_number,
        "voucher_type": vouchar.voucher_type,
        "voucher_type_id": vouchar.voucher_type_id,
        "narration": vouchar.narration,
        "party_name": vouchar.party_name,
        "party_name_id": vouchar.party_name_id,
        # Conditional fields
        "reference_number": (
            vouchar.reference_number if vouchar.reference_number else ""
        ),
        "reference_date": (vouchar.reference_date if vouchar.reference_date else ""),
        "place_of_supply": (vouchar.place_of_supply if vouchar.place_of_supply else ""),
        "vehicle_number": (vouchar.vehicle_number if vouchar.vehicle_number else ""),
        "mode_of_transport": (
            vouchar.mode_of_transport if vouchar.mode_of_transport else ""
        ),
        "due_date": (vouchar.due_date if vouchar.due_date else ""),
        "payment_mode": (
            vouchar.payment_mode if hasattr(vouchar, "payment_mode") else ""
        ),
        "paid_amount": vouchar.paid_amount if vouchar.paid_amount else 0.0,
        "total": vouchar.total if vouchar.total else 0.0,
        "discount": vouchar.discount if vouchar.discount else 0.0,
        "total_amount": vouchar.total_amount if vouchar.total_amount else 0.0,
        "total_tax": 0.0,  # Assuming total_tax is 0 for non tax voucher
        "additional_charge": (
            vouchar.additional_charge if vouchar.additional_charge else 0.0
        ),
        "roundoff": vouchar.roundoff if vouchar.roundoff else 0.0,
        "grand_total": vouchar.grand_total if vouchar.grand_total else 0.0,
        "is_deleted": False,
    }

    accounting_data = vouchar.accounting
    inventory_data = vouchar.items

    response = await vouchar_repo.new(Voucher(**vouchar_data))

    if response:
        try:

            for entry in accounting_data:
                if vouchar.voucher_type in ["Sales", "Purchase"]:
                    ledger = (
                        "Sales"
                        if vouchar.voucher_type.lower() == "sales"
                        else "Purchases"
                    )
                    party_ledger = await ledger_repo.findOne(
                        {
                            "company_id": current_user.current_company_id,
                            "ledger_name": ledger,
                            "user_id": current_user.user_id,
                        }
                    )

                    entry_data = {
                        "vouchar_id": response.vouchar_id,
                        "ledger": (
                            entry.ledger
                            if entry.ledger == vouchar.party_name
                            else party_ledger["ledger_name"]
                        ),
                        "ledger_id": (
                            entry.ledger_id
                            if entry.ledger == vouchar.party_name
                            else party_ledger["_id"]
                        ),
                        "amount": entry.amount,
                    }
                    await accounting_repo.new(Accounting(**entry_data))

                else:

                    entry_data = {
                        "vouchar_id": response.vouchar_id,
                        "ledger": entry.ledger,
                        "ledger_id": entry.ledger_id,
                        "amount": entry.amount,
                    }
                    await accounting_repo.new(Accounting(**entry_data))

            # Create all inventory items
            for item in inventory_data:
                item_data = {
                    "vouchar_id": response.vouchar_id,
                    "item": item.item,
                    "item_id": item.item_id,
                    "quantity": item.quantity,
                    "rate": item.rate,
                    "amount": item.amount,
                    "total_amount": item.total_amount,
                    "discount_amount": (
                        item.discount_amount if item.discount_amount else 0.0
                    ),
                    "godown": item.godown if item.godown else "",
                    "godown_id": item.godown_id if item.godown_id else "",
                    "tax_rate": 0,
                    "tax_amount": 0,
                    "hsn_code": "",
                    "unit": item.unit if item.unit else "",
                }
                await inventory_repo.new(InventoryItem(**item_data))

            if shouldIncreaseCounter:
                # Increase the vouchar counter for the voucher type
                await vouchar_counter_repo.update_one(
                    {
                        "voucher_type": vouchar.voucher_type,
                        "company_id": current_user.current_company_id,
                        "user_id": current_user.user_id,
                    },
                    {"$inc": {"current_number": 1}},
                )
                shouldDecreaseCounter = True

        except Exception as e:
            # Rollback vouchar creation if any error occurs
            print("Error during vouchar creation:", e)
            if shouldDecreaseCounter:
                await vouchar_counter_repo.update_one(
                    {
                        "voucher_type": vouchar.voucher_type,
                        "company_id": current_user.current_company_id,
                        "user_id": current_user.user_id,
                    },
                    {"$inc": {"current_number": -1}},
                )
            await accounting_repo.deleteAll({"vouchar_id": response.vouchar_id})
            await inventory_repo.deleteAll({"vouchar_id": response.vouchar_id})
            await vouchar_repo.deleteById(response.vouchar_id)

            raise http_exception.BadRequestException()

        return {"success": True, "message": "Vouchar Created Successfully"}

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Vouchar Already Exists. Please try with different vouchar name."
        )


@Vouchar.put(
    "/update/vouchar/{vouchar_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateVouchar(
    vouchar_id: str,
    vouchar: VoucherUpdate,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    vouchar_exists = await vouchar_repo.findOne(
        {"_id": vouchar_id, "user_id": current_user.user_id}
    )

    if not vouchar_exists:
        raise http_exception.ResourceNotFoundException(
            detail="Vouchar not found. Please check the vouchar ID."
        )
    vouchar_data = {
        "date": vouchar.date,
        "voucher_number": vouchar.voucher_number,
        "narration": vouchar.narration,
        "party_name": vouchar.party_name,
        "party_name_id": vouchar.party_name_id,
        # Conditional fields
        "reference_number": (
            vouchar.reference_number if hasattr(vouchar, "reference_number") else ""
        ),
        "reference_date": (
            vouchar.reference_date if hasattr(vouchar, "reference_date") else ""
        ),
        "place_of_supply": (
            vouchar.place_of_supply if hasattr(vouchar, "place_of_supply") else ""
        ),
        "vehicle_number": (
            vouchar.vehicle_number if hasattr(vouchar, "vehicle_number") else ""
        ),
        "mode_of_transport": (
            vouchar.mode_of_transport if hasattr(vouchar, "mode_of_transport") else ""
        ),
        "payment_mode": (
            vouchar.payment_mode if hasattr(vouchar, "payment_mode") else ""
        ),
        "due_date": (vouchar.due_date if hasattr(vouchar, "due_date") else ""),
        "paid_amount": vouchar.paid_amount if vouchar.paid_amount else 0.0,
        "total": vouchar.total if vouchar.total else 0.0,
        "discount": vouchar.discount if vouchar.discount else 0.0,
        "total_amount": vouchar.total_amount if vouchar.total_amount else 0.0,
        "total_tax": 0.0,  # Assuming total_tax is 0 for non tax voucher
        "additional_charge": (
            vouchar.additional_charge if vouchar.additional_charge else 0.0
        ),
        "roundoff": vouchar.roundoff if vouchar.roundoff else 0.0,
        "grand_total": vouchar.grand_total if vouchar.grand_total else 0.0,
        "is_deleted": False,
    }

    accounting_data = vouchar.accounting
    inventory_data = vouchar.items

    response = await vouchar_repo.update_one(
        {
            "_id": vouchar_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id
            or userSettings["current_company_id"],
        },
        {"$set": vouchar_data},
    )

    if response:
        try:
            # First, get all existing inventory items for this vouchar
            existing_acc = await accounting_repo.collection.aggregate(
                [{"$match": {"vouchar_id": vouchar_id}}]
            ).to_list(None)
            existing_acc_ids = {str(acc.get("_id")) for acc in existing_acc}

            # Track the item entry_ids received in the update
            received_acc_ids = set()
            for entry in accounting_data:
                acc_id = getattr(entry, "entry_id", None)
                received_acc_ids.add(str(acc_id))
                # Check if entry already exists
                existing_acc = await accounting_repo.findOne(
                    {"_id": entry.entry_id, "vouchar_id": vouchar_id}
                )

                acc_data = {
                    "ledger": entry.ledger,
                    "ledger_id": entry.ledger_id,
                    "amount": entry.amount,
                }

                if existing_acc:
                    await accounting_repo.update_one(
                        {"_id": entry.entry_id, "vouchar_id": vouchar_id},
                        {"$set": acc_data},
                    )
                else:
                    acc_data.update(
                        {
                            "vouchar_id": vouchar_id,
                        }
                    )
                    await accounting_repo.new(Accounting(**acc_data))

            acc_to_delete = existing_acc_ids - received_acc_ids
            if acc_to_delete:
                await accounting_repo.deleteAll(
                    {
                        "_id": {"$in": list(acc_to_delete)},
                        "vouchar_id": vouchar_id,
                    }
                )

            # First, get all existing inventory items for this vouchar
            existing_items = await inventory_repo.collection.aggregate(
                [{"$match": {"vouchar_id": vouchar_id}}]
            ).to_list(None)

            existing_item_ids = {str(item.get("_id")) for item in existing_items}

            # Track the item entry_ids received in the update
            received_entry_ids = set()
            for item in inventory_data:
                entry_id = getattr(item, "entry_id", None)
                received_entry_ids.add(str(entry_id))
                # Check if item already exists
                existing_item = await inventory_repo.findOne(
                    {
                        "_id": entry_id,
                        "vouchar_id": vouchar_id,
                        "item_id": item.item_id,
                    }
                )
                item_data = {
                    "quantity": item.quantity,
                    "rate": item.rate,
                    "amount": item.amount,
                    "discount_amount": (
                        item.discount_amount if item.discount_amount else 0.0
                    ),
                    "total_amount": item.total_amount,
                    "godown": item.godown if item.godown else "",
                    "godown_id": item.godown_id if item.godown_id else "",
                }
                if existing_item:
                    await inventory_repo.update_one(
                        {
                            "_id": entry_id,
                            "vouchar_id": vouchar_id,
                            "item_id": item.item_id,
                        },
                        {"$set": item_data},
                    )
                else:
                    item_data.update(
                        {
                            "vouchar_id": vouchar_id,
                            "item": item.item,
                            "item_id": item.item_id,
                        }
                    )
                    await inventory_repo.new(InventoryItem(**item_data))

                    # Delete inventory items that are in DB but not in the received update
            items_to_delete = existing_item_ids - received_entry_ids
            if items_to_delete:
                await inventory_repo.deleteAll(
                    {
                        "_id": {"$in": list(items_to_delete)},
                        "vouchar_id": vouchar_id,
                    }
                )

        except Exception as e:
            print("Error during vouchar update:", e)
            # Rollback vouchar update if any error occurs
            raise http_exception.BadRequestException()

        return {"success": True, "message": "Vouchar Updated Successfully"}

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Vouchar Already Exists. Please try with different vouchar name."
        )


@Vouchar.post(
    "/create/vouchar/tax", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createVoucharWithTAX(
    vouchar: VoucherWithTAXCreate,
    current_user: TokenData = Depends(get_current_user),
):
    print("Creating vouchar with TAX:", vouchar)
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    companyExists = await company_repo.findOne(
        {"_id": current_user.current_company_id, "user_id": current_user.user_id}
    )

    if not companyExists:
        raise http_exception.ResourceNotFoundException(
            detail="Company not found. Please check your company ID."
        )

    db_invoice_no = await get_cuurent_counter(
        voucher_type=vouchar.voucher_type,
        company_id=current_user.current_company_id,
        current_user=current_user,
    )

    shouldIncreaseCounter = db_invoice_no == vouchar.voucher_number
    shouldDecreaseCounter = False

    if len(vouchar.date) < 10:
        # Assuming the date is in 'YYYY-MM-DD' format, we can pad it with zeros where required.
        # e.g '2023-01-1' should become '2023-01-01', '2023-1-1' should become '2023-01-01', '2023-1-01' should become '2023-01-01'.
        parts = vouchar.date.split("-")
        for i in range(len(parts)):
            parts[i] = parts[i].zfill(2)
        vouchar.date = "-".join(parts)

    vouchar_data = {
        "user_id": current_user.user_id,
        "company_id": current_user.current_company_id,
        "date": vouchar.date,
        "voucher_number": vouchar.voucher_number,
        "voucher_type": vouchar.voucher_type,
        "voucher_type_id": vouchar.voucher_type_id,
        "narration": vouchar.narration,
        "party_name": vouchar.party_name,
        "party_name_id": vouchar.party_name_id,
        # Conditional fields
        "reference_number": (
            vouchar.reference_number if vouchar.reference_number else ""
        ),
        "reference_date": (vouchar.reference_date if vouchar.reference_date else ""),
        "place_of_supply": (vouchar.place_of_supply if vouchar.place_of_supply else ""),
        "vehicle_number": (vouchar.vehicle_number if vouchar.vehicle_number else ""),
        "mode_of_transport": (
            vouchar.mode_of_transport if vouchar.mode_of_transport else ""
        ),
        "payment_mode": (vouchar.payment_mode if vouchar.payment_mode else ""),
        "due_date": (vouchar.due_date if vouchar.due_date else ""),
        "paid_amount": vouchar.paid_amount if vouchar.paid_amount else 0.0,
        "total": vouchar.total if vouchar.total else 0.0,
        "discount": vouchar.discount if vouchar.discount else 0.0,
        "total_amount": vouchar.total_amount if vouchar.total_amount else 0.0,
        "total_tax": vouchar.total_tax if vouchar.total_tax else 0.0,
        "additional_charge": (
            vouchar.additional_charge if vouchar.additional_charge else 0.0
        ),
        "roundoff": vouchar.roundoff if vouchar.roundoff else 0.0,
        "grand_total": vouchar.grand_total if vouchar.grand_total else 0.0,
        "is_deleted": False,
    }

    accounting_data = vouchar.accounting
    inventory_data = vouchar.items

    response = await vouchar_repo.new(Voucher(**vouchar_data))

    if response:
        try:
            # Create all accounting entries
            for entry in accounting_data:
                if vouchar.voucher_type in ["Sales", "Purchase"]:
                    ledger = (
                        "Sales"
                        if vouchar.voucher_type.lower() == "sales"
                        else "Purchases"
                    )
                    party_ledger = await ledger_repo.findOne(
                        {
                            "company_id": current_user.current_company_id,
                            "ledger_name": ledger,
                            "user_id": current_user.user_id,
                        }
                    )

                    entry_data = {
                        "vouchar_id": response.vouchar_id,
                        "ledger": (
                            entry.ledger
                            if entry.ledger == vouchar.party_name
                            else party_ledger["ledger_name"]
                        ),
                        "ledger_id": (
                            entry.ledger_id
                            if entry.ledger == vouchar.party_name
                            else party_ledger["_id"]
                        ),
                        "amount": entry.amount,
                    }
                    await accounting_repo.new(Accounting(**entry_data))

                else:

                    entry_data = {
                        "vouchar_id": response.vouchar_id,
                        "ledger": entry.ledger,
                        "ledger_id": entry.ledger_id,
                        "amount": entry.amount,
                    }
                    await accounting_repo.new(Accounting(**entry_data))

            # Create all inventory items
            for item in inventory_data:
                item_data = {
                    "vouchar_id": response.vouchar_id,
                    "item": item.item,
                    "item_id": item.item_id,
                    "quantity": item.quantity,
                    "rate": item.rate,
                    "amount": item.amount,
                    "total_amount": item.total_amount,
                    "discount_amount": (
                        item.discount_amount if item.discount_amount else 0.0
                    ),
                    "godown": item.godown if item.godown else "",
                    "godown_id": item.godown_id if item.godown_id else "",
                    "tax_rate": item.tax_rate if item.tax_rate else None,
                    "tax_amount": item.tax_amount if item.tax_amount else None,
                    "hsn_code": item.hsn_code if item.hsn_code else None,
                    "unit": item.unit if item.unit else None,
                }
                await inventory_repo.new(InventoryItem(**item_data))

            if shouldIncreaseCounter:
                await vouchar_counter_repo.update_one(
                    {
                        "voucher_type": vouchar.voucher_type,
                        "company_id": current_user.current_company_id,
                        "user_id": current_user.user_id,
                    },
                    {"$inc": {"current_number": 1}},
                )
                shouldDecreaseCounter = True

        except Exception as e:
            # Rollback vouchar creation if any error occurs
            print("Error during vouchar creation:", e)
            if shouldDecreaseCounter:
                await vouchar_counter_repo.update_one(
                    {
                        "voucher_type": vouchar.voucher_type,
                        "company_id": current_user.current_company_id,
                        "user_id": current_user.user_id,
                    },
                    {"$inc": {"current_number": -1}},
                )
            await accounting_repo.deleteAll({"vouchar_id": response.vouchar_id})
            await inventory_repo.deleteAll({"vouchar_id": response.vouchar_id})
            await vouchar_repo.deleteById(response.vouchar_id)

            raise http_exception.BadRequestException()

        return {"success": True, "message": "Vouchar Created Successfully"}

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Vouchar Already Exists. Please try with different vouchar name."
        )


@Vouchar.put(
    "/update/vouchar/tax/{vouchar_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateVoucharWithTAX(
    vouchar_id: str,
    vouchar: TAXVoucherUpdate,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    companyExists = await company_repo.findOne(
        {"_id": current_user.current_company_id, "user_id": current_user.user_id}
    )

    if not companyExists:
        raise http_exception.ResourceNotFoundException(
            detail="Company not found. Please check your company ID."
        )

    companySettings = await company_settings_repo.findOne(
        {
            "company_id": current_user.current_company_id,
            "user_id": current_user.user_id,
        }
    )

    if not companySettings:
        raise http_exception.ResourceNotFoundException(
            detail="Company settings not found. Please check your company ID."
        )

    vouchar_exists = await vouchar_repo.findOne(
        {"_id": vouchar_id, "user_id": current_user.user_id}
    )

    if not vouchar_exists:
        raise http_exception.ResourceNotFoundException(
            detail="Vouchar not found. Please check the vouchar ID."
        )

    vouchar_data = {
        "date": vouchar.date,
        "voucher_number": vouchar.voucher_number,
        "narration": vouchar.narration,
        "party_name": vouchar.party_name,
        "party_name_id": vouchar.party_name_id,
        # Conditional fields
        "reference_number": (
            vouchar.reference_number if hasattr(vouchar, "reference_number") else ""
        ),
        "reference_date": (
            vouchar.reference_date if hasattr(vouchar, "reference_date") else ""
        ),
        "place_of_supply": (
            vouchar.place_of_supply if hasattr(vouchar, "place_of_supply") else ""
        ),
        "vehicle_number": (
            vouchar.vehicle_number if hasattr(vouchar, "vehicle_number") else ""
        ),
        "mode_of_transport": (
            vouchar.mode_of_transport if hasattr(vouchar, "mode_of_transport") else ""
        ),
        "payment_mode": (
            vouchar.payment_mode if hasattr(vouchar, "payment_mode") else ""
        ),
        "due_date": (vouchar.due_date if hasattr(vouchar, "due_date") else ""),
        "paid_amount": vouchar.paid_amount if vouchar.paid_amount else 0.0,
        "total": vouchar.total if vouchar.total else 0.0,
        "discount": vouchar.discount if vouchar.discount else 0.0,
        "total_amount": vouchar.total_amount if vouchar.total_amount else 0.0,
        "total_tax": vouchar.total_tax if vouchar.total_tax else 0.0,
        "additional_charge": (
            vouchar.additional_charge if vouchar.additional_charge else 0.0
        ),
        "roundoff": vouchar.roundoff if vouchar.roundoff else 0.0,
        "grand_total": vouchar.grand_total if vouchar.grand_total else 0.0,
        "is_deleted": False,
    }

    accounting_data = vouchar.accounting
    inventory_data = vouchar.items

    response = await vouchar_repo.update_one(
        {
            "_id": vouchar_id,
            "user_id": current_user.user_id,
            "company_id": current_user.current_company_id,
        },
        {"$set": vouchar_data},
    )

    if response:
        try:
            # First, get all existing inventory items for this vouchar
            existing_entry = await accounting_repo.collection.aggregate(
                [{"$match": {"vouchar_id": vouchar_id}}]
            ).to_list(None)

            existing_entry_ids = {str(entry.get("_id")) for entry in existing_entry}

            # Track the entry_ids received in the update
            received_entry_ids = set()
            for entry in accounting_data:
                entry_id = getattr(entry, "entry_id", None)
                received_entry_ids.add(str(entry_id))
                # Check if item already exists
                existing_acc = await accounting_repo.findOne(
                    {
                        "_id": entry_id,
                        "vouchar_id": vouchar_id,
                        "ledger_id": entry.ledger_id,
                    }
                )

                entry_data = {
                    "ledger": entry.ledger,
                    "ledger_id": entry.ledger_id,
                    "amount": entry.amount,
                }

                if existing_acc:
                    await accounting_repo.update_one(
                        {
                            "_id": entry_id,
                            "vouchar_id": vouchar_id,
                            "ledger_id": entry.ledger_id,
                        },
                        {"$set": entry_data},
                    )
                else:
                    entry_data.update(
                        {
                            "vouchar_id": vouchar_id,
                        }
                    )
                    await accounting_repo.new(Accounting(**entry_data))

                    # Delete accounting entries that are in DB but not in the received update
            entries_to_delete = existing_entry_ids - received_entry_ids
            if entries_to_delete:
                await accounting_repo.deleteAll(
                    {
                        "vouchar_id": vouchar_id,
                        "_id": {"$in": list(entries_to_delete)},
                    }
                )

            # First, get all existing inventory items for this vouchar
            existing_items = await inventory_repo.collection.aggregate(
                [{"$match": {"vouchar_id": vouchar_id}}]
            ).to_list(None)

            existing_item_ids = {str(item.get("_id")) for item in existing_items}

            # Track the item entry_ids received in the update
            received_entry_ids = set()
            for item in inventory_data:
                entry_id = getattr(item, "entry_id", None)
                received_entry_ids.add(str(entry_id))
                # Check if item already exists
                existing_item = await inventory_repo.findOne(
                    {
                        "_id": entry_id,
                        "vouchar_id": vouchar_id,
                        "item_id": item.item_id,
                    }
                )

                item_data = {
                    "quantity": item.quantity,
                    "rate": item.rate,
                    "amount": item.amount,
                    "discount_amount": (
                        item.discount_amount if item.discount_amount else 0.0
                    ),
                    "tax_rate": item.tax_rate if item.tax_rate else None,
                    "tax_amount": item.tax_amount if item.tax_amount else None,
                    "total_amount": item.total_amount,
                    "godown": item.godown if item.godown else "",
                    "godown_id": item.godown_id if item.godown_id else "",
                }

                if existing_item:
                    await inventory_repo.update_one(
                        {
                            "_id": entry_id,
                            "vouchar_id": vouchar_id,
                            "item_id": item.item_id,
                        },
                        {"$set": item_data},
                    )

                else:
                    item_data.update(
                        {
                            "vouchar_id": vouchar_id,
                            "item": item.item,
                            "item_id": item.item_id,
                            "hsn_code": item.hsn_code,
                            "unit": item.unit,
                        }
                    )

                    await inventory_repo.new(InventoryItem(**item_data))

                    # Delete inventory items that are in DB but not in the received update
            items_to_delete = existing_item_ids - received_entry_ids
            if items_to_delete:
                await inventory_repo.deleteAll(
                    {
                        "_id": {"$in": list(items_to_delete)},
                        "vouchar_id": vouchar_id,
                    }
                )

        except Exception as e:
            print("Error during vouchar update:", str(e))
            raise http_exception.BadRequestException()

        return {"success": True, "message": "Vouchar Updated Successfully"}

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Vouchar Already Exists. Please try with different vouchar name."
        )


@Vouchar.get(
    "/view/all/vouchar", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def view_all_vouchar(
    current_user: TokenData = Depends(get_current_user),
    company_id: str = Query(...),
    search: str = None,
    type: str = None,
    start_date: str = None,
    end_date: str = None,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=sys.maxsize),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()
    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await vouchar_repo.viewAllVouchar(
        search=search,
        company_id=current_user.current_company_id,
        type=type,
        pagination=page_request,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
        current_user=current_user,
        # is_deleted=is_deleted,
    )

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@Vouchar.get(
    "/get/vouchar/{vouchar_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def getVouchar(
    vouchar_id: str,
    current_user: TokenData = Depends(get_current_user),
    company_id: str = Query(""),
):
    if current_user.user_type not in {"user", "admin"}:
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    companySettings = await company_settings_repo.findOne(
        {
            "company_id": current_user.current_company_id,
            "user_id": current_user.user_id,
        }
    )

    if not companySettings:
        raise http_exception.ResourceNotFoundException(
            detail="Company settings not found. Please contact support."
        )

    data = await vouchar_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": vouchar_id,
                    "company_id": current_user.current_company_id,
                    "user_id": current_user.user_id,
                }
            },
            {
                "$lookup": {
                    "from": "Inventory",
                    "let": {"vouchar_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$vouchar_id", "$$vouchar_id"]}}}
                    ],
                    "as": "inventory",
                }
            },
            {
                "$addFields": {
                    "inventory": {
                        "$sortArray": {
                            "input": "$inventory",
                            "sortBy": {"created_at": 1},
                        }
                    }
                }
            },
            {
                "$lookup": {
                    "from": "Accounting",
                    "let": {"vouchar_id": "$_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$vouchar_id", "$$vouchar_id"]}}}
                    ],
                    "as": "accounting_entries",
                }
            },
            {
                "$lookup": {
                    "from": "Ledger",
                    "let": {"ledger_id": "$party_name_id"},
                    "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", "$$ledger_id"]}}}],
                    "as": "party_details",
                }
            },
            {
                "$unwind": {
                    "path": "$party_details",
                }
            },
        ]
    ).to_list(length=1)

    if not data:
        raise http_exception.ResourceNotFoundException(
            detail="Vouchar not found. Please check the vouchar ID."
        )

    return {
        "success": True,
        "message": "Vouchar Fetched Successfully",
        "data": data[0],
    }


@Vouchar.get(
    "/get/timeline",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def getTimeline(
    current_user: TokenData = Depends(get_current_user),
    company_id: str = Query(""),
    search: str = "",
    category: str = "",
    start_date: str = "",
    end_date: str = "",
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=sys.maxsize),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type not in {"user", "admin"}:
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await vouchar_repo.viewTimeline(
        search=search,
        company_id=current_user.current_company_id,
        category=category,
        pagination=page_request,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
        current_user=current_user,
    )

    return {
        "success": True,
        "message": "Data Fetched Successfully...",
        "data": result,
    }


@Vouchar.get(
    "/print/vouchar",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def print_invoice(
    vouchar_id: str = Query(...),
    company_id: str = Query(...),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type not in {"user", "admin"}:
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    invoice_data = await vouchar_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": vouchar_id,
                    "company_id": current_user.current_company_id,
                    "user_id": current_user.user_id,
                }
            },
            # Attach all accounting entries
            {
                "$lookup": {
                    "from": "Company",
                    "localField": "company_id",
                    "foreignField": "_id",
                    "as": "company",
                }
            },
            {
                "$lookup": {
                    "from": "Accounting",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "accounting_entries",
                }
            },
            # Attach inventory
            {
                "$lookup": {
                    "from": "Inventory",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "inventory",
                }
            },
            {
                "$lookup": {
                    "from": "Ledger",
                    "localField": "party_name_id",
                    "foreignField": "_id",
                    "as": "party_details",
                }
            },
            {"$unwind": {"path": "$company", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$party_details", "preserveNullAndEmptyArrays": True}},
            {"$project": {"accounting_entries": 0}},
        ]
    ).to_list(length=1)

    if not invoice_data:
        raise http_exception.ResourceNotFoundException()

    invoice = invoice_data[0]

    # Prepare item rows
    items = []
    for item in invoice.get("inventory", []):
        items.append(
            {
                "name": item.get("item", ""),
                "item_id": item.get("item_id", ""),
                "qty": item.get("quantity", 0),
                "rate": item.get("rate", 0),
                "amount": item.get("amount", 0),
                "discount_amount": item.get("discount_amount", 0),
                "total_amount": item.get("total_amount", 0),
                "pack": item.get("unit", 0),
            }
        )

    grand_total = invoice.get("grand_total", 0)
    total_words = num2words(grand_total, lang="en_IN").title() + " Rupees Only"

    # Template variables
    template_vars = {
        "invoice": {
            "voucher_type": invoice.get("voucher_type", ""),
            "voucher_number": invoice.get("voucher_number", ""),
            "date": invoice.get("date", ""),
            "vehicle_number": invoice.get("vehicle_number", ""),
            "mode_of_transport": invoice.get("mode_of_transport", ""),
            "payment_mode": invoice.get("payment_mode", ""),
            "place_of_supply": invoice.get("place_of_supply", ""),
            "items": items,
            "total": invoice.get("total", 0),
            "discount": invoice.get("discount", 0),
            "total_amount": invoice.get("total_amount", 0),
            "additional_charge": invoice.get("additional_charge", 0),
            "roundoff": invoice.get("roundoff", 0),
            "grand_total": grand_total,
            "grand_total_words": total_words,
        },
        "party": {
            "name": invoice.get("party_details", {}).get("ledger_name", ""),
            "address": invoice.get("party_details", {}).get("mailing_address", ""),
            "mailing_state": invoice.get("party_details", {}).get("mailing_state", ""),
            "mailing_country": invoice.get("party_details", {}).get(
                "mailing_country", ""
            ),
            "mailing_pincode": invoice.get("party_details", {}).get(
                "mailing_pincode", ""
            ),
            "phone": invoice.get("party_details", {}).get("phone", ""),
            "email": invoice.get("party_details", {}).get("email", ""),
            "tin": invoice.get("party_details", {}).get("tin", "") or "",
            "bank_name": invoice.get("party_details", {}).get("bank_name", ""),
            "bank_branch": invoice.get("party_details", {}).get("bank_branch", ""),
            "account_no": invoice.get("party_details", {}).get("account_number", ""),
            "account_name": invoice.get("party_details", {}).get("account_holder", ""),
            "ifsc": invoice.get("party_details", {}).get("bank_ifsc", ""),
        },
        "qr_code_url": "",
        "company": invoice.get("company", {}),
        "company.motto": "LIFE'S A JOURNEY, KEEP SMILING",
    }

    # Load HTML template (assuming you have it in a file)
    async with aiofiles.open("app/utils/templates/no_tax_template.html", "r") as f:
        template_str = await f.read()

    template = Template(template_str)
    vars_with_items = dict(template_vars)
    vars_with_items["invoice"]["items"] = items
    rendered_html = template.render(**vars_with_items)

    async with aiofiles.open(
        "app/utils/templates/no_tax_download_template.html", "r"
    ) as g:
        template_str_download = await g.read()

    template_download = Template(template_str_download)
    vars_with_items = dict(template_vars)
    vars_with_items["invoice"]["items"] = items
    rendered_download_html = template_download.render(**vars_with_items)

    template_path = "app/utils/templates/no_tax_template.html"
    rendered_pages = await render_paginated_html(
        template_path, template_vars, items, items_per_page=17
    )

    # async with async_playwright() as p:
    #     browser = await p.chromium.launch()
    #     page = await browser.new_page()
    #     await page.set_content(rendered_html, wait_until="networkidle")
    #     pdf_bytes = await page.pdf(format="A4", print_background=True, path="out.pdf")
    #     await browser.close()
    # return HTMLResponse(content=rendered_download_html, status_code=status.HTTP_200_OK)

    return {
        "success": True,
        "message": "Data Fetched Successfully...",
        "data": {
            "paginated_data": rendered_pages,
            "complete_data": rendered_html,
            "download_data": rendered_download_html,
        },
    }


@Vouchar.get(
    "/print/vouchar/tax",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def print_invoice_tax(
    vouchar_id: str = Query(...),
    company_id: str = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type not in {"user", "admin"}:
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    # Fetch invoice/voucher details
    invoice_data = await vouchar_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": vouchar_id,
                    "company_id": current_user.current_company_id,
                    "user_id": current_user.user_id,
                }
            },
            {
                "$lookup": {
                    "from": "Company",
                    "localField": "company_id",
                    "foreignField": "_id",
                    "as": "company",
                }
            },
            {
                "$lookup": {
                    "from": "Inventory",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "inventory",
                }
            },
            {
                "$addFields": {
                    "inventory": {
                        "$sortArray": {"input": "$inventory", "sortBy": {"created_at": 1}}
                    }
                }
            },
            {
                "$lookup": {
                    "from": "Ledger",
                    "localField": "party_name",
                    "foreignField": "ledger_name",
                    "as": "party_details",
                }
            },
            {"$unwind": {"path": "$company", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$party_details", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "CompanySettings",
                    "localField": "company._id",
                    "foreignField": "company_id",
                    "as": "company_settings",
                }
            },
            {
                "$unwind": {
                    "path": "$company_settings",
                    "preserveNullAndEmptyArrays": True,
                }
            },
        ]
    ).to_list(length=1)

    if not invoice_data:
        raise http_exception.ResourceNotFoundException(detail="Vouchar not found.")

    invoice = invoice_data[0]
    items = []

    for item in invoice.get("inventory", []):
        item_id = str(item.get("item_id", ""))
        items.append(
            {
                "item_id": item_id,
                "name": item.get("item", ""),
                "pack": item.get("unit", ""),
                "hsn": item.get("hsn_code", ""),
                "qty": item.get("quantity", 0),
                "rate": item.get("rate", 0),
                "amount": item.get("amount", 0),
                "discount_amount": item.get("discount_amount", 0),
                "tax_rate": item.get("tax_rate", ""),
                "tax_amount": item.get("tax_amount", 0),
                "total_amount": item.get("total_amount", 0),
            }
        )

    totals, invoice_taxes, tax_headers, tax_code = await generate_tax_summary(
        items=items,
        party_details=invoice.get("party_details", {}),
        company=invoice.get("company", {}),
        current_user=current_user,
    )

    # Template variables
    template_vars = {
        "invoice": {
            "voucher_type": invoice.get("voucher_type", ""),
            "voucher_number": invoice.get("voucher_number", ""),
            "date": invoice.get("date", ""),
            "vehicle_number": invoice.get("vehicle_number", ""),
            "mode_of_transport": invoice.get("mode_of_transport", ""),
            "payment_mode": invoice.get("payment_mode", ""),
            "place_of_supply": invoice.get("place_of_supply", ""),
            "total": invoice.get("total", 0),
            "discount": invoice.get("discount", 0),
            "total_amount": invoice.get("total_amount", 0),
            "total_tax": invoice.get("total_tax", 0),
            "additional_charge": invoice.get("additional_charge", 0),
            "roundoff": invoice.get("roundoff", 0),
            "grand_total": invoice.get("grand_total", 0),
            "is_reversed_charge": (
                "Yes" if invoice.get("is_reversed_charge", False) else "No"
            ),
            "tax_code": tax_code,
            "totals": totals,
            "tax_headers": tax_headers,
            "taxes": invoice_taxes,
        },
        "party": {
            "name": invoice.get("party_details", {}).get("ledger_name", ""),
            "mailing_address": invoice.get("party_details", {}).get(
                "mailing_address", ""
            ),
            "mailing_state": invoice.get("party_details", {}).get("mailing_state", ""),
            "mailing_country": invoice.get("party_details", {}).get(
                "mailing_country", ""
            ),
            "mailing_pincode": invoice.get("party_details", {}).get(
                "mailing_pincode", ""
            ),
            "phone": invoice.get("party_details", {}).get("phone", ""),
            "email": invoice.get("party_details", {}).get("email", ""),
            "tin": invoice.get("party_details", {}).get("tin", "") or "",
            "bank_name": invoice.get("party_details", {}).get("bank_name", ""),
            "bank_branch": invoice.get("party_details", {}).get("bank_branch", ""),
            "account_no": invoice.get("party_details", {}).get("account_number", ""),
            "account_name": invoice.get("party_details", {}).get("account_holder", ""),
            "ifsc": invoice.get("party_details", {}).get("bank_ifsc", ""),
        },
        "company": invoice.get("company", {}),
        "company.bank_name": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("bank_name", ""),
        "company.bank_branch": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("bank_branch", ""),
        "company.account_no": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("account_number", ""),
        "company.account_name": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("account_holder", ""),
        "company.ifsc": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("bank_ifsc", ""),
        "company.qr_code_url": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("qr_code_url", ""),
        "company.motto": invoice.get("company_settings", {}).get(
            "motto", "LIFE'S A JOURNEY, KEEP SMILING"
        ),
    }

    if invoice.get("voucher_type", "") == "Sales":
        async with aiofiles.open(
            "app/utils/templates/tax_sale_invoice_template.html", "r"
        ) as f:
            template_str = await f.read()

        template = Template(template_str)
        vars_with_items = dict(template_vars)
        vars_with_items["invoice"]["items"] = items
        rendered_html = template.render(**vars_with_items)
        # return HTMLResponse(
        #     content=rendered_html
        # )

        async with aiofiles.open(
            "app/utils/templates/tax_sale_invoice_download_template.html", "r"
        ) as g:
            template_str_download = await g.read()

        template = Template(template_str_download)
        vars_with_items = dict(template_vars)
        vars_with_items["invoice"]["items"] = items
        rendered_download_html = template.render(**vars_with_items)

        template_path = "app/utils/templates/tax_sale_invoice_template.html"
        rendered_pages = await render_paginated_html(
            template_path, template_vars, items, items_per_page=17
        )

        return {
            "success": True,
            "message": "Data Fetched Successfully...",
            "data": {
                "paginated_data": rendered_pages,
                "complete_data": rendered_html,
                "download_data": rendered_download_html,
            },
        }

    else:
        async with aiofiles.open(
            "app/utils/templates/tax_purchase_template.html", "r"
        ) as f:
            template_str = await f.read()

        template = Template(template_str)
        vars_with_items = dict(template_vars)
        vars_with_items["invoice"]["items"] = items
        rendered_html = template.render(**vars_with_items)

        async with aiofiles.open(
            "app/utils/templates/tax_purchase_download_template.html", "r"
        ) as g:
            template_str_download = await g.read()

        template = Template(template_str_download)
        vars_with_items = dict(template_vars)
        vars_with_items["invoice"]["items"] = items
        rendered_download_html = template.render(**vars_with_items)

        template_path = "app/utils/templates/tax_purchase_template.html"
        rendered_pages = await render_paginated_html(
            template_path, template_vars, items, items_per_page=17
        )
        # return HTMLResponse(
        #     content=rendered_download_html, status_code=status.HTTP_200_OK
        # )

        return {
            "success": True,
            "message": "Data Fetched Successfully...",
            "data": {
                "paginated_data": rendered_pages,
                "complete_data": rendered_html,
                "download_data": rendered_download_html,
            },
        }


@Vouchar.get(
    "/print/vouchar/receipt",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def print_receipt(
    vouchar_id: str = Query(...),
    company_id: str = Query(...),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type not in {"user", "admin"}:
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    # Fetch invoice/voucher details
    invoice_data = await vouchar_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": vouchar_id,
                    "company_id": current_user.current_company_id
                    or userSettings["current_company_id"],
                    "user_id": current_user.user_id,
                }
            },
            # Attach all accounting entries
            {
                "$lookup": {
                    "from": "Accounting",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "accounting_entries",
                }
            },
            # Attach inventory
            {
                "$lookup": {
                    "from": "Inventory",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "inventory",
                }
            },
            # Attach party ledger details
            {
                "$lookup": {
                    "from": "Ledger",
                    "localField": "party_name",
                    "foreignField": "ledger_name",
                    "as": "party_details",
                }
            },
            {"$unwind": {"path": "$party_details", "preserveNullAndEmptyArrays": True}},
            # Pick the first non-party accounting record as "accounting"
            {
                "$addFields": {
                    "accounting": {
                        "$first": {
                            "$filter": {
                                "input": "$accounting_entries",
                                "as": "acc",
                                "cond": {"$ne": ["$$acc.ledger", "$party_name"]},
                            }
                        }
                    }
                }
            },
            # Lookup the customer (i.e., ledger of the accounting entry)
            {
                "$lookup": {
                    "from": "Ledger",
                    "let": {"ledger_name": "$accounting.ledger"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$ledger_name", "$$ledger_name"]}}}
                    ],
                    "as": "customer",
                }
            },
            {"$unwind": {"path": "$customer", "preserveNullAndEmptyArrays": True}},
            # Final clean-up: remove temp accounting_entries
            {"$project": {"accounting_entries": 0}},
        ]
    ).to_list(length=1)

    if not invoice_data:
        raise http_exception.ResourceNotFoundException()

    invoice = invoice_data[0]

    total = abs(invoice.get("accounting", {}).get("amount", 0))
    total_int = int(total)
    total_frac = int(round((total - total_int) * 100))
    if total_frac > 0:
        total_words = (
            num2words(total_int, lang="en_IN").title()
            + " Rupees And "
            + num2words(total_frac, lang="en_IN").title()
            + " Paise only"
        )
    else:
        total_words = num2words(total_int, lang="en_IN").title() + " Rupees Only"

    # Template variables
    date_val = invoice.get("date", "")
    if hasattr(date_val, "strftime"):
        formatted_date = date_val.strftime("%d %b, %Y")
    elif isinstance(date_val, str) and date_val:
        formatted_date = date_val  # Already a string, use as-is
    else:
        formatted_date = ""

    template_vars = {
        "invoice": {
            "vouchar_type": invoice.get("voucher_type", ""),
            "voucher_number": invoice.get("voucher_number", ""),
            "party_name": invoice.get("party_name", ""),
            "narration": invoice.get("narration", ""),
            "date": formatted_date,
            "amount": total,
            "amount_words": total_words,
            "email": invoice.get("party_details", {}).get("email", ""),
            "customer": invoice.get("customer", {}).get("ledger_name", ""),
            "company": {"motto": "LIFE'S A JOURNEY, KEEP SMILING"},
        },
    }

    # Load HTML template (assuming you have it in a file)
    async with aiofiles.open("app/utils/templates/reciept_template.html", "r") as f:
        template_str = await f.read()

    template = Template(template_str)
    rendered_html = template.render(**template_vars)
    return {
        "success": True,
        "message": "Data Fetched Successfully...",
        "data": rendered_html,
    }


@Vouchar.get(
    "/print/vouchar/payment",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def print_payment(
    vouchar_id: str = Query(...),
    company_id: str = Query(...),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type not in {"user", "admin"}:
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    # Fetch invoice/voucher details
    invoice_data = await vouchar_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": vouchar_id,
                    "company_id": userSettings["current_company_id"],
                    "user_id": current_user.user_id,
                }
            },
            # Attach all accounting entries
            {
                "$lookup": {
                    "from": "Accounting",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "accounting_entries",
                }
            },
            {
                "$lookup": {
                    "from": "Company",
                    "localField": "company_id",
                    "foreignField": "_id",
                    "as": "company",
                }
            },
            # Attach inventory
            {
                "$lookup": {
                    "from": "Inventory",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "inventory",
                }
            },
            # Attach party ledger details
            {
                "$lookup": {
                    "from": "Ledger",
                    "localField": "party_name",
                    "foreignField": "ledger_name",
                    "as": "party_details",
                }
            },
            {"$unwind": {"path": "$party_details", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$company", "preserveNullAndEmptyArrays": True}},
            # Pick the first non-party accounting record as "accounting"
            {
                "$addFields": {
                    "accounting": {
                        "$first": {
                            "$filter": {
                                "input": "$accounting_entries",
                                "as": "acc",
                                "cond": {"$ne": ["$$acc.ledger", "$party_name"]},
                            }
                        }
                    }
                }
            },
            # Lookup the customer (i.e., ledger of the accounting entry)
            {
                "$lookup": {
                    "from": "Ledger",
                    "let": {"ledger_name": "$accounting.ledger"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$ledger_name", "$$ledger_name"]}}}
                    ],
                    "as": "customer",
                }
            },
            {"$unwind": {"path": "$customer", "preserveNullAndEmptyArrays": True}},
            # Final clean-up: remove temp accounting_entries
            {"$project": {"accounting_entries": 0}},
        ]
    ).to_list(length=1)

    if not invoice_data:
        raise http_exception.ResourceNotFoundException()

    invoice = invoice_data[0]

    total = abs(invoice.get("accounting", {}).get("amount", 0))
    total_int = int(total)
    total_frac = int(round((total - total_int) * 100))
    if total_frac > 0:
        total_words = (
            num2words(total_int, lang="en_IN").title()
            + " Rupees And "
            + num2words(total_frac, lang="en_IN").title()
            + " Paise only"
        )
    else:
        total_words = num2words(total_int, lang="en_IN").title() + " Rupees Only"

    # Template variables
    date_val = invoice.get("date", "")
    if hasattr(date_val, "strftime"):
        formatted_date = date_val.strftime("%d %b, %Y")
    elif isinstance(date_val, str) and date_val:
        formatted_date = date_val  # Already a string, use as-is
    else:
        formatted_date = ""

    # Extract year from "2025-05-01" style date string
    year_val = ""
    if isinstance(invoice.get("company", {}).get("financial_year_start", ""), str):
        fy_start = invoice.get("company", {}).get("financial_year_start", "")
        if fy_start:
            year_val = fy_start.split("-")[0]

    template_vars = {
        "invoice": {
            "vouchar_type": invoice.get("voucher_type", ""),
            "vouchar_number": invoice.get("voucher_number", ""),
            "party_name": invoice.get("party_name", ""),
            "narration": invoice.get("narration", ""),
            "date": formatted_date,
            "amount": total,
            "amount_words": total_words,
            "email": invoice.get("party_details", {}).get("email", ""),
            "customer": invoice.get("customer", {}).get("ledger_name", ""),
            "company_name": invoice.get("company", {}).get("name", ""),
            "year_start": year_val,
            "year_end": str(int(year_val) + 1),
            "mailling_state": invoice.get("company", {}).get("state", ""),
            "company_email": invoice.get("company", {}).get("email", ""),
        },
    }

    # Load HTML template (assuming you have it in a file)
    async with aiofiles.open("app/utils/templates/payment_template.html", "r") as f:
        template_str = await f.read()

    template = Template(template_str)
    rendered_html = template.render(**template_vars)
    # return HTMLResponse(
    #     content=rendered_html,
    #     media_type="text/html",
    #     status_code=status.HTTP_200_OK,
    # )
    return {
        "success": True,
        "message": "Data Fetched Successfully...",
        "data": rendered_html,
    }


@Vouchar.get(
    "/vouchar/{vouchar_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def get_vouchar(
    vouchar_id: str,
    company_id: str = Query(...),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    result = await stock_item_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": vouchar_id,
                    "company_id": current_user.current_company_id
                    or userSettings["current_company_id"],
                    "user_id": current_user.user_id,
                    "is_deleted": False,
                }
            },
            {
                "$lookup": {
                    "from": "Ledger",
                    "localField": "party_name",
                    "foreignField": "name",
                    "as": "party",
                }
            },
            {"$unwind": {"path": "$party", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "Accounting",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "accounting",
                }
            },
            {
                "$lookup": {
                    "from": "Inventory",
                    "localField": "_id",
                    "foreignField": "vouchar_id",
                    "as": "inventory",
                }
            },
            {
                "$addFields": {
                    "ledger_entries": {
                        "$map": {
                            "input": {
                                "$filter": {
                                    "input": "$accounting",
                                    "as": "entry",
                                    "cond": {"$eq": ["$$entry.ledger", "$party_name"]},
                                }
                            },
                            "as": "entry",
                            "in": {
                                "ledgername": "$$entry.ledger",
                                "amount": "$$entry.amount",
                                "is_deemed_positive": {
                                    "$cond": [{"$lt": ["$$entry.amount", 0]}, True, False]
                                },
                                "amount_absolute": {"$abs": "$$entry.amount"},
                            },
                        }
                    }
                }
            },
            {"$unwind": {"path": "$ledger_entries", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": 1,
                    "date": 1,
                    "voucher_number": 1,
                    "voucher_type": 1,
                    "voucher_type_id": 1,
                    "party_name": 1,
                    "party_name_id": 1,
                    "narration": 1,
                    # "amount": "$ledger_entries.amount",
                    "balance_type": 1,
                    # "ledger_name": "$ledger_entries.ledgername',",
                    # "is_deemed_positive": "$ledger_entries.is_deemed_positive",
                    "ledger_entries": 1,
                    "created_at": 1,
                }
            },
        ]
    ).to_list(None)

    return {"success": True, "message": "Data Fetched Successfully...", "data": result}


@Vouchar.delete(
    "/delete/{vouchar_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_vouchar(
    vouchar_id: str,
    company_id: str = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    voucharExists = await vouchar_repo.findOne(
        {
            "_id": vouchar_id,
            "company_id": current_user.current_company_id
            or userSettings["current_company_id"],
            "user_id": current_user.user_id,
        }
    )

    if voucharExists is None:
        raise http_exception.ResourceNotFoundException(
            detail="No Invoice Found. Please delete appropriate invoice."
        )

    query = {
        "company_id": current_user.current_company_id
        or userSettings["current_company_id"],
        "user_id": current_user.user_id,
        "voucher_type": voucharExists["voucher_type"],
    }

    counter = await vouchar_counter_repo.findOne(query)
    pad_length = counter["pad_length"] or 4  # Default padding length if not set
    separator = counter["separator"]
    padded_number = str(counter["current_number"] - 1).zfill(pad_length)
    if counter["suffix"]:
        formatted_number = (
            f"{counter['prefix']}{separator}{padded_number}{separator}{counter['suffix']}"
        )
    else:
        formatted_number = f"{counter['prefix']}{separator}{padded_number}"

    if voucharExists["voucher_number"] == formatted_number:
        # Update the counter only if the voucher number matches the expected format
        await vouchar_counter_repo.update_one(
            query,
            {"$inc": {"current_number": -1}},
        )

    # Delete all accounting entries associated with the vouchers
    await accounting_repo.deleteAll({"vouchar_id": vouchar_id})

    # Delete all the inventory entries associated with the vouchers
    await inventory_repo.deleteAll({"vouchar_id": vouchar_id})

    await vouchar_repo.deleteOne(
        {
            "_id": vouchar_id,
            "company_id": current_user.current_company_id
            or userSettings["current_company_id"],
            "user_id": current_user.user_id,
        }
    )

    return {"success": True, "message": "Invoice Deleted Successfully..."}


@Vouchar.delete(
    "/tax/delete/{vouchar_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_tax_vouchar(
    vouchar_id: str,
    company_id: str = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    voucharExists = await vouchar_repo.findOne(
        {
            "_id": vouchar_id,
            "company_id": current_user.current_company_id
            or userSettings["current_company_id"],
            "user_id": current_user.user_id,
        }
    )

    if voucharExists is None:
        raise http_exception.ResourceNotFoundException(
            detail="No Invoice Found. Please delete appropriate invoice."
        )

    # Delete all accounting entries associated with the vouchers
    await accounting_repo.deleteAll({"vouchar_id": vouchar_id})

    # Delete all the inventory entries associated with the vouchers
    await inventory_repo.deleteAll({"vouchar_id": vouchar_id})

    await vouchar_repo.deleteOne(
        {
            "_id": vouchar_id,
            "company_id": current_user.current_company_id
            or userSettings["current_company_id"],
            "user_id": current_user.user_id,
        }
    )

    return {"success": True, "message": "Invoice Deleted Successfully..."}


@Vouchar.get("/get/analytics", response_class=ORJSONResponse)
async def get_analytics(
    company_id: str = Query(None),
    financial_year: int = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    if financial_year is None:
        financial_year = datetime.now().year

    response = await vouchar_repo.get_analytics_data(
            current_user=current_user,
            year=int(financial_year),
            company_id=current_user.current_company_id or company_id,
        )

    return {
        "success": True,
        "data": response,
        "message": "Data fetched successfully...",
    }

@Vouchar.get("/get/analytics/monthly", response_class=ORJSONResponse)
async def get_analytics_monthly(
    company_id: str = Query(None),
    financial_year: int = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    if financial_year is None:
        financial_year = datetime.now().year

    response = await vouchar_repo.get_monthly_data(
            current_user=current_user,
            year=int(financial_year),
            company_id=current_user.current_company_id or company_id,
        )
    

    return {
        "success": True,
        "data": response,
        "message": "Data fetched successfully...",
    }


@Vouchar.get("/get/analytics/daily", response_class=ORJSONResponse)
async def get_analytics_daily(
    company_id: str = Query(None),
    financial_year: int = Query(None),
    financial_month: int = Query(None),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please contact support."
        )

    if financial_year is None:
        financial_year = datetime.now().year

    if financial_month is None:
        financial_month = datetime.now().month

    response = await vouchar_repo.get_daily_data(
            current_user=current_user,
            year=int(financial_year),
            month=int(financial_month),
            company_id=current_user.current_company_id or company_id,
        ),
    

    return {
        "success": True,
        "data": response,
        "message": "Data fetched successfully...",
    }
