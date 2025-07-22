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
from app.schema.token import TokenData
from app.oauth2 import get_current_user
from app.database.repositories.voucharRepo import vouchar_repo
from app.database.repositories.voucharCounterRepo import vouchar_counter_repo
from app.database.repositories.UserSettingsRepo import user_settings_repo
from app.database.repositories.ledgerRepo import ledger_repo
from app.database.repositories.voucharGSTRepo import vouchar_gst_repo
from app.database.repositories.accountingRepo import accounting_repo
from app.database.repositories.InventoryRepo import inventory_repo
from app.database.models.Vouchar import Voucher, VoucherCreate, VoucherUpdate
from app.database.models.VoucharGST import VoucherGST
from app.database.models.VoucharCounter import VoucherCounter
from app.database.models.Accounting import Accounting, AccountingUpdate
from typing import Optional, List
from app.database.models.Inventory import (
    InventoryItem,
    UpdateInventoryItemWithGST,
    CreateInventoryItemWithGST,
)
from fastapi import Query
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest
from app.database.repositories.stockItemRepo import stock_item_repo
from jinja2 import Template
import aiofiles
from num2words import num2words
from math import ceil

Vouchar = APIRouter()


class VoucherWithGSTCreate(BaseModel):
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
    status: Optional[str] = None
    due_date: Optional[str] = None
    accounting: List[Accounting]
    items: List[CreateInventoryItemWithGST]


class GSTVoucherUpdate(BaseModel):
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
    status: Optional[str] = None
    due_date: Optional[str] = None

    accounting: List[AccountingUpdate]
    items: Optional[List[UpdateInventoryItemWithGST]]


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

    vouchar_data = {
        "user_id": current_user.user_id,
        "company_id": userSettings["current_company_id"],
        "date": vouchar.date,
        "voucher_number": vouchar.voucher_number,
        "voucher_type": vouchar.voucher_type,
        "voucher_type_id": vouchar.voucher_type_id,
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
        "status": (vouchar.status if hasattr(vouchar, "status") else ""),
        "due_date": (vouchar.due_date if hasattr(vouchar, "due_date") else ""),
        "is_deleted": False,
        # Conditional fields for voucher types
        "is_invoice": 1 if vouchar.voucher_type in ["sales", "purchase"] else 0,
        "is_accounting_voucher": (
            1
            if vouchar.voucher_type in ["sales", "purchase", "payment", "receipt"]
            else 0
        ),
        "is_inventory_voucher": (
            1
            if vouchar.voucher_type in ["sales", "purchase"] and len(vouchar.items) > 0
            else 0
        ),
        "is_order_voucher": (
            1 if vouchar.voucher_type.lower() in ["sales order", "purchase order"] else 0
        ),
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
                            "company_id": userSettings["current_company_id"],
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
                    "additional_amount": (
                        item.additional_amount
                        if hasattr(item, "additional_amount")
                        else 0.0
                    ),
                    "discount_amount": (
                        item.discount_amount if hasattr(item, "discount_amount") else 0.0
                    ),
                    "godown": item.godown if hasattr(item, "godown") else "",
                    "godown_id": item.godown_id if hasattr(item, "godown_id") else "",
                    "order_number": (
                        item.order_number if hasattr(item, "order_number") else None
                    ),
                    "order_due_date": (
                        item.order_due_date if hasattr(item, "order_due_date") else None
                    ),
                }
                await inventory_repo.new(InventoryItem(**item_data))

            # Increase the vouchar counter for the voucher type
            await vouchar_counter_repo.update_one(
                {
                    "voucher_type": vouchar.voucher_type,
                    "company_id": userSettings["current_company_id"],
                    "user_id": current_user.user_id,
                },
                {"$inc": {"current_number": 1}},
            )

        except Exception as e:
            # Rollback vouchar creation if any error occurs
            print("Error during vouchar creation:", e)
            await vouchar_counter_repo.update_one(
                {
                    "voucher_type": vouchar.voucher_type,
                    "company_id": userSettings["current_company_id"],
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
        "is_deleted": False,
        # Conditional fields for voucher types
        "is_invoice": 1 if vouchar.voucher_type in ["sales", "purchase"] else 0,
        "is_accounting_voucher": (
            1
            if vouchar.voucher_type in ["sales", "purchase", "payment", "receipt"]
            else 0
        ),
        "is_inventory_voucher": (
            1
            if vouchar.voucher_type in ["sales", "purchase"] and len(vouchar.items) > 0
            else 0
        ),
        "is_order_voucher": (
            1 if vouchar.voucher_type.lower() in ["sales order", "purchase order"] else 0
        ),
    }

    accounting_data = vouchar.accounting
    inventory_data = vouchar.items

    response = await vouchar_repo.update_one(
        {
            "_id": vouchar_id,
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
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
                    "additional_amount": (
                        item.additional_amount
                        if hasattr(item, "additional_amount")
                        else 0.0
                    ),
                    "discount_amount": (
                        item.discount_amount if hasattr(item, "discount_amount") else 0.0
                    ),
                    "godown": item.godown if hasattr(item, "godown") else "",
                    "godown_id": (item.godown_id if hasattr(item, "godown_id") else ""),
                    "order_number": (
                        item.order_number if hasattr(item, "order_number") else None
                    ),
                    "order_due_date": (
                        item.order_due_date if hasattr(item, "order_due_date") else None
                    ),
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
    "/create/vouchar/gst", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createVoucharWithGST(
    vouchar: VoucherWithGSTCreate,
    current_user: TokenData = Depends(get_current_user),
):
    print("Creating VOuchar with GST", vouchar)
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    companyExists = await company_repo.findOne(
        {"_id": userSettings["current_company_id"], "user_id": current_user.user_id}
    )

    if not companyExists:
        raise http_exception.ResourceNotFoundException(
            detail="Company not found. Please check your company ID."
        )

    companyStateCode = companyExists.get("gstin", None)[:2]

    companySettings = await company_settings_repo.findOne(
        {
            "company_id": userSettings["current_company_id"],
            "user_id": current_user.user_id,
        }
    )

    if not companySettings:
        raise http_exception.ResourceNotFoundException(
            detail="Company settings not found. Please check your company ID."
        )

    vouchar_data = {
        "user_id": current_user.user_id,
        "company_id": userSettings["current_company_id"],
        "date": vouchar.date,
        "voucher_number": vouchar.voucher_number,
        "voucher_type": vouchar.voucher_type,
        "voucher_type_id": vouchar.voucher_type_id,
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
        "status": (vouchar.status if hasattr(vouchar, "status") else ""),
        "due_date": (vouchar.due_date if hasattr(vouchar, "due_date") else ""),
        "is_deleted": False,
        # Conditional fields for voucher types
        "is_invoice": 1 if vouchar.voucher_type in ["sales", "purchase"] else 0,
        "is_accounting_voucher": (
            1
            if vouchar.voucher_type in ["sales", "purchase", "payment", "receipt"]
            else 0
        ),
        "is_inventory_voucher": (
            1
            if vouchar.voucher_type in ["sales", "purchase"] and len(vouchar.items) > 0
            else 0
        ),
        "is_order_voucher": (
            1 if vouchar.voucher_type.lower() in ["sales order", "purchase order"] else 0
        ),
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
                            "company_id": userSettings["current_company_id"],
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
                    "additional_amount": (
                        item.additional_amount
                        if hasattr(item, "additional_amount")
                        else 0.0
                    ),
                    "discount_amount": (
                        item.discount_amount if hasattr(item, "discount_amount") else 0.0
                    ),
                    "godown": item.godown if hasattr(item, "godown") else "",
                    "godown_id": item.godown_id if hasattr(item, "godown_id") else "",
                    "order_number": (
                        item.order_number if hasattr(item, "order_number") else None
                    ),
                    "order_due_date": (
                        item.order_due_date if hasattr(item, "order_due_date") else None
                    ),
                }
                await inventory_repo.new(InventoryItem(**item_data))

            party_ledger = await ledger_repo.findOne(
                {
                    "company_id": userSettings["current_company_id"],
                    "ledger_name": vouchar.party_name,
                    "user_id": current_user.user_id,
                }
            )

            if companySettings["features"]["enable_gst"] and party_ledger:
                # If GST is enabled, ensure vouchar created with GST details
                if vouchar.voucher_type == "Purchase":
                    if not party_ledger["gstin"]:
                        raise http_exception.BadRequestException(
                            detail="Party ledger does not have GSTIN. Please update the party ledger."
                        )

                    # Extract Party GSTIN
                    partyStateCode = party_ledger["gstin"][:2]

                    vouchar_gst_data = {
                        "voucher_id": response.vouchar_id,
                        "company_id": userSettings["current_company_id"],
                        "user_id": current_user.user_id,
                        "is_gst_applicable": True,
                        "place_of_supply": (
                            vouchar.place_of_supply
                            if hasattr(vouchar, "place_of_supply")
                            else ""
                        ),
                        "party_gstin": (
                            party_ledger.gstin if hasattr(party_ledger, "gstin") else ""
                        ),
                        "item_gst_details": [
                            {
                                "item": item.item,
                                "item_id": item.item_id,
                                "hsn_code": item.hsn_code,
                                "gst_rate": item.gst_rate,
                                "taxable_value": item.amount,
                                "cgst": (
                                    item.gst_amount / 2
                                    if companyStateCode == partyStateCode
                                    else 0
                                ),  # CGST amount
                                "sgst": (
                                    item.gst_amount / 2
                                    if companyStateCode == partyStateCode
                                    else 0
                                ),  # SGST amount
                                "igst": (
                                    item.gst_amount
                                    if companyStateCode != partyStateCode
                                    else 0
                                ),  # IGST amount
                            }
                            for item in vouchar.items
                        ],
                    }
                    await vouchar_gst_repo.new(VoucherGST(**vouchar_gst_data))
                    # return {"success": True, "message": "Vouchar Created Successfully"}

                elif vouchar.voucher_type == "Sales":

                    if not companyExists.get("gstin", None):
                        raise http_exception.BadRequestException(
                            detail="Company does not have GSTIN. Please update the company details."
                        )

                    companyStateCode = companyExists.get("gstin", None)[:2]

                    if not party_ledger["gstin"]:
                        companyStateCode = companyExists.get("state", None)
                        partyStateCode = party_ledger["mailing_state"]
                    else:
                        partyStateCode = party_ledger["gstin"][:2]

                    vouchar_gst_data = {
                        "voucher_id": response.vouchar_id,
                        "company_id": userSettings["current_company_id"],
                        "user_id": current_user.user_id,
                        "is_gst_applicable": True,
                        "place_of_supply": (
                            vouchar.place_of_supply
                            if hasattr(vouchar, "place_of_supply")
                            else ""
                        ),
                        "party_gstin": (
                            party_ledger.gstin if hasattr(party_ledger, "gstin") else ""
                        ),
                        "item_gst_details": [
                            {
                                "item": item.item,
                                "item_id": item.item_id,
                                "hsn_code": item.hsn_code,
                                "gst_rate": item.gst_rate,
                                "taxable_value": item.amount,
                                "cgst": (
                                    item.gst_amount / 2
                                    if companyStateCode == partyStateCode
                                    else 0
                                ),  # CGST amount
                                "sgst": (
                                    item.gst_amount / 2
                                    if companyStateCode == partyStateCode
                                    else 0
                                ),  # SGST amount
                                "igst": (
                                    item.gst_amount
                                    if companyStateCode != partyStateCode
                                    else 0
                                ),  # IGST amount
                            }
                            for item in vouchar.items
                        ],
                    }
                    await vouchar_gst_repo.new(VoucherGST(**vouchar_gst_data))
                    # return {"success": True, "message": "Vouchar Created Successfully"}

            # Increase the vouchar counter for the voucher type
            await vouchar_counter_repo.update_one(
                {
                    "voucher_type": vouchar.voucher_type,
                    "company_id": userSettings["current_company_id"],
                    "user_id": current_user.user_id,
                },
                {"$inc": {"current_number": 1}},
            )

        except Exception as e:
            # Rollback vouchar creation if any error occurs
            print("Error during vouchar creation:", e)
            await accounting_repo.deleteAll({"vouchar_id": response.vouchar_id})
            await inventory_repo.deleteAll({"vouchar_id": response.vouchar_id})
            await vouchar_gst_repo.deleteAll({"voucher_id": response.vouchar_id})
            await vouchar_repo.deleteById(response.vouchar_id)

            raise http_exception.BadRequestException()

        return {"success": True, "message": "Vouchar Created Successfully"}

    if not response:
        raise http_exception.ResourceAlreadyExistsException(
            detail="Vouchar Already Exists. Please try with different vouchar name."
        )


@Vouchar.put(
    "/update/vouchar/gst/{vouchar_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def updateVoucharWithGST(
    vouchar_id: str,
    vouchar: GSTVoucherUpdate,
    current_user: TokenData = Depends(get_current_user),
):
    print('Updating GST Vouchar with', vouchar)
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    userSettings = await user_settings_repo.findOne({"user_id": current_user.user_id})

    if userSettings is None:
        raise http_exception.ResourceNotFoundException(
            detail="User Settings Not Found. Please create user settings first."
        )

    companyExists = await company_repo.findOne(
        {"_id": userSettings["current_company_id"], "user_id": current_user.user_id}
    )

    companyStateCode = companyExists.get("gstin", None)[:2]

    if not companyExists:
        raise http_exception.ResourceNotFoundException(
            detail="Company not found. Please check your company ID."
        )

    companySettings = await company_settings_repo.findOne(
        {
            "company_id": userSettings["current_company_id"],
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
        "is_deleted": False,
        # Conditional fields for voucher types
        "is_invoice": 1 if vouchar.voucher_type in ["sales", "purchase"] else 0,
        "is_accounting_voucher": (
            1
            if vouchar.voucher_type in ["sales", "purchase", "payment", "receipt"]
            else 0
        ),
        "is_inventory_voucher": (
            1
            if vouchar.voucher_type in ["sales", "purchase"] and len(vouchar.items) > 0
            else 0
        ),
        "is_order_voucher": (
            1 if vouchar.voucher_type.lower() in ["sales order", "purchase order"] else 0
        ),
    }

    accounting_data = vouchar.accounting
    inventory_data = vouchar.items

    response = await vouchar_repo.update_one(
        {
            "_id": vouchar_id,
            "user_id": current_user.user_id,
            "company_id": userSettings["current_company_id"],
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
                    "additional_amount": (
                        item.additional_amount
                        if hasattr(item, "additional_amount")
                        else 0.0
                    ),
                    "discount_amount": (
                        item.discount_amount if hasattr(item, "discount_amount") else 0.0
                    ),
                    "godown": item.godown if hasattr(item, "godown") else "",
                    "godown_id": (item.godown_id if hasattr(item, "godown_id") else ""),
                    "order_number": (
                        item.order_number if hasattr(item, "order_number") else None
                    ),
                    "order_due_date": (
                        item.order_due_date if hasattr(item, "order_due_date") else None
                    ),
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
            party_ledger = await ledger_repo.findOne(
                {
                    "company_id": userSettings["current_company_id"],
                    "ledger_name": vouchar.party_name,
                    "user_id": current_user.user_id,
                }
            )

            if companySettings["features"]["enable_gst"] and party_ledger:
                # If GST is enabled, ensure vouchar updated with GST details
                if vouchar.voucher_type == "Purchase":
                    if not party_ledger['gstin']:
                        raise http_exception.BadRequestException(
                            detail="Party ledger does not have GSTIN. Please update the party ledger."
                        )

                    # Extract Party GSTIN
                    partyStateCode = party_ledger['gstin'][:2]

                    vouchar_gst_data = {
                        "voucher_id": vouchar_id,
                        "company_id": userSettings["current_company_id"],
                        "user_id": current_user.user_id,
                        "is_gst_applicable": True,
                        "place_of_supply": (
                            vouchar.place_of_supply
                            if hasattr(vouchar, "place_of_supply")
                            else ""
                        ),
                        "party_gstin": (
                            party_ledger['gstin'] if hasattr(party_ledger, "gstin") else ""
                        ),
                        "item_gst_details": [
                            {
                                "item": item.item,
                                "item_id": item.item_id,
                                "hsn_code": item.hsn_code,
                                "gst_rate": item.gst_rate,
                                "taxable_value": item.amount,
                                "cgst": (
                                    item.gst_amount / 2
                                    if companyStateCode == partyStateCode
                                    else 0
                                ),  # CGST amount
                                "sgst": (
                                    item.gst_amount / 2
                                    if companyStateCode == partyStateCode
                                    else 0
                                ),  # SGST amount
                                "igst": (
                                    item.gst_amount
                                    if companyStateCode != partyStateCode
                                    else 0
                                ),  # IGST amount
                            }
                            for item in vouchar.items
                        ],
                    }
                    await vouchar_gst_repo.update_one(
                        {"voucher_id": vouchar_id},
                        {"$set": vouchar_gst_data},
                    )

                    return {"success": True, "message": "Vouchar Updated Successfully"}
                elif vouchar.voucher_type == "Sales":
                    if not companyExists["gstin"]:
                        raise http_exception.BadRequestException(
                            detail="Company does not have GSTIN. Please update the company details."
                        )
                    companyStateCode = companyExists["gstin"][:2]
                    if not party_ledger['gstin']:
                        companyStateCode = companyExists["state"]
                        partyStateCode = party_ledger["mailing_state"]
                    else:
                        partyStateCode = party_ledger['gstin'][:2]

                    vouchar_gst_data = {
                        "voucher_id": vouchar_id,
                        "company_id": userSettings["current_company_id"],
                        "user_id": current_user.user_id,
                        "is_gst_applicable": True,
                        "place_of_supply": (
                            vouchar.place_of_supply
                            if hasattr(vouchar, "place_of_supply")
                            else ""
                        ),
                        "party_gstin": (
                            party_ledger['gstin'] if hasattr(party_ledger, "gstin") else ""
                        ),
                        "item_gst_details": [
                            {
                                "item": item.item,
                                "item_id": item.item_id,
                                "hsn_code": item.hsn_code,
                                "gst_rate": item.gst_rate,
                                "taxable_value": item.amount,
                                "cgst": (
                                    item.gst_amount / 2
                                    if companyStateCode == partyStateCode
                                    else 0
                                ),  # CGST amount
                                "sgst": (
                                    item.gst_amount / 2
                                    if companyStateCode == partyStateCode
                                    else 0
                                ),  # SGST amount
                                "igst": (
                                    item.gst_amount
                                    if companyStateCode != partyStateCode
                                    else 0
                                ),  # IGST amount
                            }
                            for item in vouchar.items
                        ],
                    }
                    await vouchar_gst_repo.update_one(
                        {"voucher_id": vouchar_id},
                        {"$set": vouchar_gst_data},
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
    limit: int = Query(10, le=60),
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
        company_id=userSettings["current_company_id"],
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
            "company_id": userSettings["current_company_id"],
            "user_id": current_user.user_id,
        }
    )

    if not companySettings:
        raise http_exception.ResourceNotFoundException(
            detail="Company settings not found. Please contact support."
        )

    if companySettings["features"]["enable_gst"]:
        data = await vouchar_repo.collection.aggregate(
            [
                {
                    "$match": {
                        "_id": vouchar_id,
                        "company_id": userSettings["current_company_id"],
                        "user_id": current_user.user_id,
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
                            "$sortArray": {
                                "input": "$inventory",
                                "sortBy": {"created_at": 1},
                            }
                        }
                    }
                },
                {
                    "$lookup": {
                        "from": "VoucherGST",
                        "localField": "_id",
                        "foreignField": "voucher_id",
                        "as": "voucher_gst",
                    }
                },
                {
                    "$addFields": {
                        "item_gst_details": {
                            "$ifNull": [
                                {
                                    "$ifNull": [
                                        {
                                            "$arrayElemAt": [
                                                "$voucher_gst.item_gst_details",
                                                0,
                                            ]
                                        },
                                        [],
                                    ]
                                },
                                [],
                            ]
                        }
                    }
                },
                {
                    "$addFields": {
                        "inventory": {
                            "$map": {
                                "input": "$inventory",
                                "as": "item",
                                "in": {
                                    "$mergeObjects": [
                                        "$$item",
                                        {
                                            "$let": {
                                                "vars": {
                                                    "gst": {
                                                        "$arrayElemAt": [
                                                            {
                                                                "$filter": {
                                                                    "input": "$item_gst_details",
                                                                    "as": "gst",
                                                                    "cond": {
                                                                        "$eq": [
                                                                            "$$gst.item_id",
                                                                            "$$item.item_id",
                                                                        ]
                                                                    },
                                                                }
                                                            },
                                                            0,
                                                        ]
                                                    }
                                                },
                                                "in": {
                                                    "hsn_code": {
                                                        "$ifNull": [
                                                            "$$gst.hsn_code",
                                                            None,
                                                        ]
                                                    },
                                                    "gst": {
                                                        "$ifNull": [
                                                            "$$gst.gst_rate",
                                                            None,
                                                        ]
                                                    },
                                                    "gst_amount": {
                                                        "$ifNull": [
                                                            {"$subtract":[ "$$gst.total_amount","$$gst.taxable_value",]},
                                                            None,
                                                        ]
                                                    },
                                                },
                                            }
                                        },
                                    ]
                                },
                            }
                        }
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
                {
                    "$project": {
                        "item_gst_details": 0,
                        "voucher_gst": 0,
                    }
                },
            ]
        ).to_list(length=1)
        if not data:
            raise http_exception.ResourceNotFoundException(
                detail="Vouchar not found. Please check the vouchar ID."
            )
    else:
        data = await vouchar_repo.collection.aggregate(
            [
                {
                    "$match": {
                        "_id": vouchar_id,
                        "company_id": userSettings["current_company_id"],
                        "user_id": current_user.user_id,
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
                        "localField": "_id",
                        "foreignField": "vouchar_id",
                        "as": "accounting_entries",
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
    type: str = "",
    start_date: str = "",
    end_date: str = "",
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=60),
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
        company_id=userSettings["current_company_id"],
        type=type,
        pagination=page_request,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
        current_user=current_user,
        # is_deleted=is_deleted,
    )

    # # Fetch invoice/voucher details, flattening inventory and merging vouchar fields
    # timeline_data = await vouchar_repo.collection.aggregate(
    #     [
    #         {
    #             "$match": {
    #                 "company_id": userSettings["current_company_id"],
    #                 "user_id": current_user.user_id,
    #             }
    #         },
    #         {
    #             "$lookup": {
    #                 "from": "Inventory",
    #                 "localField": "_id",
    #                 "foreignField": "vouchar_id",
    #                 "as": "inventory",
    #             }
    #         },
    #         {"$unwind": "$inventory"},
    #         {
    #             "$addFields": {
    #                 "inventory.company_id": "$company_id",
    #                 "inventory.user_id": "$user_id",
    #                 "inventory.date": "$date",
    #                 "inventory.voucher_number": "$voucher_number",
    #                 "inventory.voucher_type": "$voucher_type",
    #                 "inventory.narration": "$narration",
    #                 "inventory.party_name": "$party_name",
    #                 "inventory.place_of_supply": "$place_of_supply",
    #                 "inventory.created_at": "$created_at",
    #                 "inventory.updated_at": "$updated_at",
    #             }
    #         },
    #         {"$replaceRoot": {"newRoot": "$inventory"}},
    #         {"$sort": {"date": -1, "created_at": -1}},
    #     ]
    # ).to_list(length=None)

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
                    "company_id": userSettings["current_company_id"],
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
                    "from": "StockItem",
                    "localField": "inventory.item_id",
                    "foreignField": "_id",
                    "as": "stockItems",
                }
            },
            # Attach party ledger details
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
            # Pick the first non-party accounting record as "accounting"
            {
                "$addFields": {
                    "accounting": {
                        "$first": {
                            "$filter": {
                                "input": "$accounting_entries",
                                "as": "acc",
                                "cond": {"$ne": ["$$acc.ledger_id", "$party_name_id"]},
                            }
                        }
                    }
                }
            },
            # Lookup the customer (i.e., ledger of the accounting entry)
            {
                "$lookup": {
                    "from": "Ledger",
                    "let": {"ledger_id": "$accounting.ledger_id"},
                    "pipeline": [{"$match": {"$expr": {"$eq": ["$_id", "$$ledger_id"]}}}],
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

    # Simulate customer info from the ledger party for this template
    customer = {
        "name": invoice.get("customer", {}).get("ledger_name", ""),
        "address": invoice.get("customer", {}).get("mailing_address", ""),
        "phone": invoice.get("customer", {}).get("phone", ""),
        "gst_no": "08ABIPJ1392D1ZT",
        # "gst_no": invoice.get("customer", {}).get("gst_no", ""),
    }

    # Prepare item rows
    items = []
    for item in invoice.get("inventory", []):
        items.append(
            {
                "name": item.get("item", ""),
                "qty": item.get("quantity", 0),
                "rate": item.get("rate", 0),
                "amount": item.get("amount", 0),
                # "pack": item.get("pack", ""),
                # "hsn": item.get("hsn", ""),
            }
        )

    stock_items = invoice.get("stockItems", [])

    for item in items:
        for si in stock_items:
            if si.get("_id") == item.get("item_id"):
                item["pack"] = si.get("unit", "")

    total = sum(i["amount"] for i in items)
    grand_total = abs(invoice.get("accounting", {}).get("amount", 0))
    total_int = int(grand_total)
    total_frac = int(round((grand_total - total_int) * 100))
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
    template_vars = {
        "invoice": {
            "voucher_type": invoice.get("voucher_type", ""),
            "voucher_number": invoice.get("voucher_number", ""),
            "date": invoice.get("date", ""),
            "items": items,
            "total": f"{total:.2f}",
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
            "gst_no": invoice.get("party_details", {}).get("gstin", "") or "",
            "bank_name": invoice.get("party_details", {}).get("bank_name", ""),
            "bank_branch": invoice.get("party_details", {}).get("bank_branch", ""),
            "account_no": invoice.get("party_details", {}).get("account_number", ""),
            "account_name": invoice.get("party_details", {}).get("account_holder", ""),
            "ifsc": invoice.get("party_details", {}).get("bank_ifsc", ""),
        },
        "customer": customer,
        "qr_code_url": "",
        "company": invoice.get("company", {}),
        "company.motto": "LIFE'S A JOURNEY, KEEP SMILING",
    }

    # Load HTML template (assuming you have it in a file)
    async with aiofiles.open("app/utils/templates/no_gst_template.html", "r") as f:
        template_str = await f.read()

    template = Template(template_str)
    vars_with_items = dict(template_vars)
    vars_with_items["invoice"]["items"] = items
    rendered_html = template.render(**vars_with_items)

    async with aiofiles.open(
        "app/utils/templates/no_gst_download_template.html", "r"
    ) as g:
        template_str_download = await g.read()

    template_download = Template(template_str_download)
    vars_with_items = dict(template_vars)
    vars_with_items["invoice"]["items"] = items
    rendered_download_html = template_download.render(**vars_with_items)

    template_path = "app/utils/templates/no_gst_template.html"
    rendered_pages = await render_paginated_html(
        template_path, template_vars, items, items_per_page=17
    )
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
    "/print/vouchar/gst",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def print_invoice_gst(
    vouchar_id: str = Query(...),
    company_id: str = Query(None),
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
            # Sort inventory items by created_at ascending
            {
                "$addFields": {
                    "inventory": {
                        "$sortArray": {"input": "$inventory", "sortBy": {"created_at": 1}}
                    }
                }
            },
            {
                "$lookup": {
                    "from": "StockItem",
                    "localField": "inventory.item_id",
                    "foreignField": "_id",
                    "as": "stockItems",
                }
            },
            {
                "$lookup": {
                    "from": "VoucherGST",
                    "localField": "_id",
                    "foreignField": "voucher_id",
                    "as": "voucher_gst",
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
        raise http_exception.ResourceNotFoundException()

    invoice = invoice_data[0]

    # Prepare item rows
    items = []
    voucher_gst = invoice.get("voucher_gst", [{}])

    item_gst_details = voucher_gst[0].get("item_gst_details", [])

    # Build a mapping from item_id to GST details
    item_gst_map = {str(gst.get("item_id", "")): gst for gst in item_gst_details}

    for item in invoice.get("inventory", []):
        item_id = str(item.get("item_id", ""))
        item_gst = item_gst_map.get(item_id, {})
        items.append(
            {
                "name": item.get("item", ""),
                "item_id": item_id,
                "qty": item.get("quantity", 0),
                "rate": item.get("rate", 0),
                "amount": item.get("amount", 0),
                # "pack": stock_item.get("unit", ""),
                "hsn": item_gst.get("hsn_code", ""),
                "gst_rate": item_gst.get("gst_rate", ""),
                "taxable_value": item_gst.get("taxable_value", 0),
                "total_amount": item_gst.get("total_amount", 0),
            }
        )

    stock_items = invoice.get("stockItems", [])

    for item in items:
        for si in stock_items:
            if si.get("_id") == item.get("item_id"):
                item["pack"] = si.get("unit", "")

    total = sum(i["amount"] for i in items)
    units = sum(i["qty"] for i in items)
    total_total_amount = sum(i["total_amount"] for i in items)
    total_taxable_value = sum(i["taxable_value"] for i in items)
    total_tax = round(total_total_amount - total_taxable_value, 2)

    # --- GST Tax Table Calculation ---
    from collections import defaultdict

    tax_summary = defaultdict(
        lambda: {
            "igst": 0.0,
            "sgst": 0.0,
            "cgst": 0.0,
            "gst_amt": 0.0,
            "taxable_value": 0.0,
        }
    )

    for detail in item_gst_details:
        try:
            rate = float(detail.get("gst_rate", 0))
        except Exception:
            rate = 0.0
        tax_summary[rate]["igst"] += float(detail.get("igst", 0.0))
        tax_summary[rate]["sgst"] += float(detail.get("sgst", 0.0))
        tax_summary[rate]["cgst"] += float(detail.get("cgst", 0.0))
        tax_summary[rate]["taxable_value"] += float(detail.get("taxable_value", 0.0))
        tax_summary[rate]["gst_amt"] += (
            float(detail.get("igst", 0.0))
            + float(detail.get("sgst", 0.0))
            + float(detail.get("cgst", 0.0))
        )

    invoice_taxes = []
    totals = {"igst": 0.0, "sgst": 0.0, "cgst": 0.0, "gst_amt": 0.0, "taxable_value": 0.0}
    for rate, vals in tax_summary.items():
        invoice_taxes.append(
            {
                "percent": rate,
                "igst": round(vals["igst"], 2),
                "sgst": round(vals["sgst"], 2),
                "cgst": round(vals["cgst"], 2),
                "taxable_value": round(vals["taxable_value"], 2),
                "gst_amt": round(vals["gst_amt"], 2),
            }
        )
        totals["igst"] += vals["igst"]
        totals["sgst"] += vals["sgst"]
        totals["cgst"] += vals["cgst"]
        totals["taxable_value"] += vals["taxable_value"]
        totals["gst_amt"] += vals["gst_amt"]

    totals = {k: round(v, 2) for k, v in totals.items()}
    totals["units"] = units
    # --- END GST Tax Table Calculation ---

    grand_total = abs(total_total_amount)

    # Template variables
    template_vars = {
        "invoice": {
            "voucher_type": invoice.get("voucher_type", ""),
            "voucher_number": invoice.get("voucher_number", ""),
            "date": invoice.get("date", ""),
            "total_tax": total_tax,
            # "roundoff": roundoff,
            "total": f"{total:.2f}",
            "grand_total": grand_total,
            "taxes": invoice_taxes,
            "payment_status": invoice.get("status", ""),
            "station": "Rajkot",
            "is_reversed_charge": (
                "Yes" if invoice.get("is_reversed_charge", False) else "No"
            ),
            "vehicle_number": invoice.get("vehicle_number", ""),
            "mode_of_transport": invoice.get("mode_of_transport", ""),
            "place_of_supply": invoice.get("place_of_supply", ""),
            "additional_charges": 12.34,
            "totals": totals,
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
            "gst_no": invoice.get("party_details", {}).get("gstin", "") or "",
            "bank_name": invoice.get("party_details", {}).get("bank_name", ""),
            "bank_branch": invoice.get("party_details", {}).get("bank_branch", ""),
            "account_no": invoice.get("party_details", {}).get("account_number", ""),
            "account_name": invoice.get("party_details", {}).get("account_holder", ""),
            "ifsc": invoice.get("party_details", {}).get("bank_ifsc", ""),
        },
        "company": invoice.get("company", {}),
        "company.bank_name": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("bank_name", "SBI"),
        "company.bank_branch": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("bank_branch", "Rajkot"),
        "company.account_no": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("account_number", "000 000 000 000"),
        "company.account_name": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("account_holder", "ABC Pvt Ltd"),
        "company.ifsc": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("bank_ifsc", "IFSCCODE1234"),
        "company.qr_code_url": invoice.get("company_settings", {})
        .get("bank_details", {})
        .get("qr_code_url", ""),
        "company.motto": invoice.get("company_settings", {}).get(
            "motto", "LIFE'S A JOURNEY, KEEP SMILING"
        ),
    }

    if invoice.get("voucher_type", "") == "Sales":
        async with aiofiles.open(
            "app/utils/templates/gst_sale_invoice_template.html", "r"
        ) as f:
            template_str = await f.read()

        template = Template(template_str)
        vars_with_items = dict(template_vars)
        vars_with_items["invoice"]["items"] = items
        rendered_html = template.render(**vars_with_items)

        async with aiofiles.open(
            "app/utils/templates/gst_sale_invoice_download_template.html", "r"
        ) as g:
            template_str_download = await g.read()

        template = Template(template_str_download)
        vars_with_items = dict(template_vars)
        vars_with_items["invoice"]["items"] = items
        rendered_download_html = template.render(**vars_with_items)

        template_path = "app/utils/templates/gst_sale_invoice_template.html"
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
            "app/utils/templates/gst_purchase_template.html", "r"
        ) as f:
            template_str = await f.read()

        template = Template(template_str)
        vars_with_items = dict(template_vars)
        vars_with_items["invoice"]["items"] = items
        rendered_html = template.render(**vars_with_items)

        async with aiofiles.open(
            "app/utils/templates/gst_purchase_download_template.html", "r"
        ) as g:
            template_str_download = await g.read()

        template = Template(template_str_download)
        vars_with_items = dict(template_vars)
        vars_with_items["invoice"]["items"] = items
        rendered_download_html = template.render(**vars_with_items)

        template_path = "app/utils/templates/gst_purchase_template.html"
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
                    "company_id": userSettings["current_company_id"],
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
            "company_id": userSettings["current_company_id"],
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
            "company_id": userSettings["current_company_id"],
            "user_id": current_user.user_id,
        }
    )

    return {"success": True, "message": "Invoice Deleted Successfully..."}


@Vouchar.delete(
    "/gst/delete/{vouchar_id}",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_gst_vouchar(
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
            "company_id": userSettings["current_company_id"],
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

    # Delete all the voucher GST entries associated with the company
    await vouchar_gst_repo.deleteOne(
        {
            "voucher_id": vouchar_id,
            "company_id": company_id,
            "user_id": current_user.user_id,
        }
    )

    await vouchar_repo.deleteOne(
        {
            "_id": vouchar_id,
            "company_id": userSettings["current_company_id"],
            "user_id": current_user.user_id,
        }
    )

    return {"success": True, "message": "Invoice Deleted Successfully..."}
