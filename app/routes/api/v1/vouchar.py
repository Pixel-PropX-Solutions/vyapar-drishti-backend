from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from app.database.repositories.user import user_repo
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel
import app.http_exception as http_exception
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.oauth2 import get_current_user
from app.schema.token import TokenData
from app.utils.cloudinary_client import cloudinary_client
from app.database.repositories.voucharRepo import vouchar_repo
from app.database.repositories.accountingRepo import accounting_repo
from app.database.repositories.InventoryRepo import inventory_repo
from app.database.models.Vouchar import Voucher, VoucherDB, VoucherCreate
from app.database.models.Accounting import Accounting
from typing import Optional, List
from app.database.models.Inventory import InventoryItem
from pydantic import BaseModel
from fastapi import APIRouter, Depends, status, File, UploadFile, Form
from fastapi.responses import ORJSONResponse
import app.http_exception as http_exception
from app.schema.token import TokenData
import app.http_exception as http_exception
from app.oauth2 import get_current_user
from fastapi import Query
from app.schema.token import TokenData
from app.database.repositories.crud.base import SortingOrder, Sort, Page, PageRequest

from app.database.models.StockItem import StockItemCreate
from app.database.repositories.stockItemRepo import stock_item_repo
from app.database.repositories.InventoryRepo import inventory_repo
from app.database.models.StockItem import StockItem
from app.utils.cloudinary_client import cloudinary_client
from typing import Optional, Union

from fastapi.responses import HTMLResponse
from jinja2 import Template
import aiofiles
from num2words import num2words

Vouchar = APIRouter()


class VoucherItem(BaseModel):
    item: str
    _item: str
    quantity: float
    rate: float
    amount: float


@Vouchar.post(
    "/create/vouchar", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def createVouchar(
    vouchar: VoucherCreate,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()
    print("Creating vouchar with data:", vouchar)

    vouchar_data = {
        "user_id": current_user.user_id,
        "company_id": vouchar.company_id,
        "date": vouchar.date,
        "voucher_number": vouchar.voucher_number,
        "voucher_type": vouchar.voucher_type,
        "_voucher_type": vouchar.voucher_type,
        "narration": vouchar.narration,
        "party_name": vouchar.party_name,
        "_party_name": vouchar.party_name,
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

    response = await vouchar_repo.new(Voucher(**vouchar_data))

    if response:
        try:
            # Create all accounting entries
            for entry in accounting_data:
                entry_data = {
                    "vouchar_id": response.vouchar_id,
                    "ledger": entry.ledger,
                    "_ledger": entry.ledger,
                    "amount": entry.amount,
                }
                await accounting_repo.new(Accounting(**entry_data))

            # Create all inventory items
            for item in inventory_data:
                item_data = {
                    "vouchar_id": response.vouchar_id,
                    "item": item.item,
                    "_item": item.item,
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
                    "_godown": item._godown if hasattr(item, "_godown") else "",
                    "order_number": (
                        item.order_number if hasattr(item, "order_number") else None
                    ),
                    "order_due_date": (
                        item.order_due_date if hasattr(item, "order_due_date") else None
                    ),
                }
                await inventory_repo.new(InventoryItem(**item_data))

        except Exception as e:
            # Rollback vouchar creation if any error occurs
            await vouchar_repo.delete(response.vouchar_id)
            raise http_exception.DatabaseException(
                detail=f"Failed to create vouchar details: {str(e)}"
            )

        return {"success": True, "message": "Vouchar Created Successfully"}

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
    # is_deleted: bool = False,
    page_no: int = Query(1, ge=1),
    limit: int = Query(10, le=60),
    sortField: str = "created_at",
    sortOrder: SortingOrder = SortingOrder.DESC,
):
    if current_user.user_type != "user" and current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    page = Page(page=page_no, limit=limit)
    sort = Sort(sort_field=sortField, sort_order=sortOrder)
    page_request = PageRequest(paging=page, sorting=sort)

    result = await vouchar_repo.viewAllVouchar(
        search=search,
        company_id=company_id,
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

    # Fetch invoice/voucher details
    invoice_data = await vouchar_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": vouchar_id,
                    "company_id": company_id,
                    "user_id": current_user.user_id,
                }
            },
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
                "$lookup": {
                    "from": "Ledger",
                    "localField": "party_name",
                    "foreignField": "ledger_name",
                    "as": "party_details",
                }
            },
            {"$unwind": {"path": "$party_details", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$accounting", "preserveNullAndEmptyArrays": True}},
            {
                "$addFields": {
                    "do_ledger_lookup": {"$ne": ["$accounting.ledger", "$party_name"]}
                }
            },
            {
                "$lookup": {
                    "from": "Ledger",
                    "let": {
                        "customer_name": "$accounting.ledger",
                        "do_lookup": "$do_ledger_lookup",
                    },
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$ledger_name", "$$customer_name"]},
                                        {"$eq": ["$$do_lookup", True]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "accounting.ledger_details",
                }
            },
            {
                "$unwind": {
                    "path": "$accounting.ledger_details",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$unwind": {
                    "path": "$accounting",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "user_id": {"$first": "$user_id"},
                    "date": {"$first": "$date"},
                    "voucher_number": {"$first": "$voucher_number"},
                    "voucher_type": {"$first": "$voucher_type"},
                    "narration": {"$first": "$narration"},
                    "party_name": {"$first": "$party_name"},
                    "reference_date": {"$first": "$reference_date"},
                    "reference_number": {"$first": "$reference_number"},
                    "place_of_supply": {"$first": "$place_of_supply"},
                    "is_invoice": {"$first": "$is_invoice"},
                    "is_accounting_voucher": {"$first": "$is_accounting_voucher"},
                    "is_inventory_voucher": {"$first": "$is_inventory_voucher"},
                    "is_order_voucher": {"$first": "$is_order_voucher"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                    "party_details": {"$first": "$party_details"},
                    "accounting": {"$first": "$accounting"},
                    "inventory": {"$first": "$inventory"},
                }
            },
        ]
    ).to_list(length=1)

    print("Fetched invoice data:", invoice_data)

    if not invoice_data:
        raise http_exception.ResourceNotFoundException()

    invoice = invoice_data[0]

    # Simulate customer info from the ledger party for this template
    customer = {
        "name": invoice.get("accounting", {})
        .get("ledger_details", {})
        .get("ledger_name", ""),
        "address": invoice.get("accounting", {})
        .get("ledger_details", {})
        .get("mailing_address", ""),
        "phone": invoice.get("accounting", {}).get("ledger_details", {}).get("phone", ""),
        "gst_no": "08ABIPJ1392D1ZT",
        # "gst_no": invoice.get("accounting", {}).get("ledger_details", {}).get("gst_no", ""),
        "pan_no": "08ABIPJ1392D1ZT",
        # "pan_no": invoice.get("accounting", {}).get("ledger_details", {}).get("pan_no", ""),
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
                "pack": item.get("pack", ""),
                "hsn": item.get("hsn", ""),
            }
        )

    total = sum(i["amount"] for i in items)
    grand_total = abs(invoice.get("accounting", {}).get("amount", 0))

    # Template variables
    template_vars = {
        "invoice": {
            "voucher_type": invoice.get("voucher_type", ""),
            "voucher_number": invoice.get("voucher_number", ""),
            "date": invoice.get("date", ""),
            "items": items,
            "total": f"{total:.2f}",
            "grand_total": grand_total,
        },
        "party": {
            "name": invoice.get("party_details", {}).get("ledger_name", ""),
            "address": invoice.get("party_details", {}).get("mailing_address", ""),
            "phone": invoice.get("party_details", {}).get("phone", ""),
            "email": invoice.get("party_details", {}).get("email", ""),
            "gst_no": "08ABIPJ1392D1ZT",
            # invoice.get("party_details", {}).get("gst_no", ""),
            "pan_no": "08ABIPJ1392D1ZT",
            # invoice.get("party_details", {}).get("pan_no", ""),
            # "bank_details": invoice.get("party_details", {}).get("bank_name", ""),
            # "account_no": invoice.get("party_details", {}).get("bank_account_no", ""),
            # "ifsc": invoice.get("party_details", {}).get("bank_ifsc", ""),
            "bank_name": "HDFC BANK",
            "bank_branch": "BRANCH CHETAK",
            "account_no": "01198430000036",
            "ifsc": "HDFC0000119",
        },
        "customer": customer,
        "company": {"motto": "LIFE'S A JOURNEY, KEEP SMILING"},
    }

    # print("Template variables prepared:", template_vars)

    # Load HTML template (assuming you have it in a file)
    async with aiofiles.open("app/utils/templates/invoice_template.html", "r") as f:
        template_str = await f.read()

    template = Template(template_str)
    rendered_html = template.render(**template_vars)
    return {
        "success": True,
        "message": "Data Fetched Successfully...",
        "data": rendered_html,
    }


@Vouchar.get(
    "/print/vouchar/receipt",
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

    # Fetch invoice/voucher details
    invoice_data = await vouchar_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": vouchar_id,
                    "company_id": company_id,
                    "user_id": current_user.user_id,
                }
            },
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
                "$lookup": {
                    "from": "Ledger",
                    "localField": "party_name",
                    "foreignField": "name",
                    "as": "party_details",
                }
            },
            {"$unwind": {"path": "$party_details", "preserveNullAndEmptyArrays": True}},
            # Unwind accounting for further processing
            {"$unwind": {"path": "$accounting", "preserveNullAndEmptyArrays": True}},
            # Only do the ledger lookup if accounting.ledger != party_name
            {
                "$addFields": {
                    "do_ledger_lookup": {"$ne": ["$accounting.ledger", "$party_name"]}
                }
            },
            {
                "$lookup": {
                    "from": "Ledger",
                    "let": {
                        "ledger_name": "$accounting.ledger",
                        "do_lookup": "$do_ledger_lookup",
                    },
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$name", "$$ledger_name"]},
                                        {"$eq": ["$$do_lookup", True]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "accounting.ledger_details",
                }
            },
            {
                "$unwind": {
                    "path": "$accounting.ledger_details",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$unwind": {
                    "path": "$accounting",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "user_id": {"$first": "$user_id"},
                    "date": {"$first": "$date"},
                    "voucher_number": {"$first": "$voucher_number"},
                    "voucher_type": {"$first": "$voucher_type"},
                    "narration": {"$first": "$narration"},
                    "party_name": {"$first": "$party_name"},
                    "reference_date": {"$first": "$reference_date"},
                    "reference_number": {"$first": "$reference_number"},
                    "place_of_supply": {"$first": "$place_of_supply"},
                    "is_invoice": {"$first": "$is_invoice"},
                    "is_accounting_voucher": {"$first": "$is_accounting_voucher"},
                    "is_inventory_voucher": {"$first": "$is_inventory_voucher"},
                    "is_order_voucher": {"$first": "$is_order_voucher"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                    "party_details": {"$first": "$party_details"},
                    "accounting": {"$first": "$accounting"},
                    "inventory": {"$first": "$inventory"},
                }
            },
        ]
    ).to_list(length=1)

    # print("Fetched invoice data:", invoice_data)

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
            "customer": invoice.get("accounting", {})
            .get("ledger_details", {})
            .get("name", ""),
            "company": {"motto": "LIFE'S A JOURNEY, KEEP SMILING"},
        },
    }

    # print("Template variables prepared:", template_vars)

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
async def print_invoice(
    vouchar_id: str = Query(...),
    company_id: str = Query(...),
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type not in {"user", "admin"}:
        raise http_exception.CredentialsInvalidException()

    # Fetch invoice/voucher details
    invoice_data = await vouchar_repo.collection.aggregate(
        [
            {
                "$match": {
                    "_id": vouchar_id,
                    "company_id": company_id,
                    "user_id": current_user.user_id,
                }
            },
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
                    "from": "Company",
                    "localField": "company_id",
                    "foreignField": "_id",
                    "as": "company",
                }
            },
            {
                "$lookup": {
                    "from": "Ledger",
                    "localField": "party_name",
                    "foreignField": "name",
                    "as": "party_details",
                }
            },
            {"$unwind": {"path": "$party_details", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$accounting", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$company", "preserveNullAndEmptyArrays": True}},
            {
                "$addFields": {
                    "do_ledger_lookup": {"$ne": ["$accounting.ledger", "$party_name"]}
                }
            },
            {
                "$lookup": {
                    "from": "Ledger",
                    "let": {
                        "ledger_name": "$accounting.ledger",
                        "do_lookup": "$do_ledger_lookup",
                    },
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$name", "$$ledger_name"]},
                                        {"$eq": ["$$do_lookup", True]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "accounting.ledger_details",
                }
            },
            {
                "$unwind": {
                    "path": "$accounting.ledger_details",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$unwind": {
                    "path": "$accounting",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$group": {
                    "_id": "$_id",
                    "company_id": {"$first": "$company_id"},
                    "user_id": {"$first": "$user_id"},
                    "date": {"$first": "$date"},
                    "voucher_number": {"$first": "$voucher_number"},
                    "voucher_type": {"$first": "$voucher_type"},
                    "narration": {"$first": "$narration"},
                    "party_name": {"$first": "$party_name"},
                    "reference_date": {"$first": "$reference_date"},
                    "reference_number": {"$first": "$reference_number"},
                    "place_of_supply": {"$first": "$place_of_supply"},
                    "is_invoice": {"$first": "$is_invoice"},
                    "is_accounting_voucher": {"$first": "$is_accounting_voucher"},
                    "is_inventory_voucher": {"$first": "$is_inventory_voucher"},
                    "is_order_voucher": {"$first": "$is_order_voucher"},
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"},
                    "party_details": {"$first": "$party_details"},
                    "accounting": {"$first": "$accounting"},
                    "company": {"$first": "$company"},
                }
            },
        ]
    ).to_list(length=1)

    # print("Fetched invoice data:", invoice_data)

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
            "voucher_number": invoice.get("voucher_number", ""),
            "party_name": invoice.get("party_name", ""),
            "narration": invoice.get("narration", ""),
            "date": formatted_date,
            "amount": total,
            "amount_words": total_words,
            "email": invoice.get("party_details", {}).get("email", ""),
            "customer": invoice.get("accounting", {})
            .get("ledger_details", {})
            .get("name", ""),
            "company_name": invoice.get("company", {}).get("name", ""),
            "year_start": year_val,
            "year_end": str(int(year_val) + 1),
            "mailling_state": invoice.get("company", {}).get("state", ""),
            "company_email": invoice.get("company", {}).get("email", ""),
        },
    }

    # print("Template variables prepared:", template_vars)

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


# @Vouchar.get(
#     "/print/vouchar{vouchar_id}",
#     response_class=ORJSONResponse,
#     status_code=status.HTTP_200_OK,
# )
# async def view_all_vouchar(
#     vouchar_id: str = Query(...),
#     company_id: str = Query(...),
#     current_user: TokenData = Depends(get_current_user),
# ):
#     if current_user.user_type != "user" and current_user.user_type != "admin":
#         raise http_exception.CredentialsInvalidException()

#     result = await stock_item_repo.collection.aggregate(
#         [
#             {
#                 "$match": {
#                     "_id": vouchar_id,
#                     "company_id": company_id,
#                     "user_id": current_user.user_id,
#                     "is_deleted": False,
#                 }
#             },
#             {
#                 "$lookup": {
#                     "from": "Ledger",
#                     "localField": "party_name",
#                     "foreignField": "name",
#                     "as": "party",
#                 }
#             },
#             {"$unwind": {"path": "$party", "preserveNullAndEmptyArrays": True}},
#             {
#                 "$lookup": {
#                     "from": "Accounting",
#                     "localField": "_id",
#                     "foreignField": "vouchar_id",
#                     "as": "accounting",
#                 }
#             },
#             {
#                 "$lookup": {
#                     "from": "Inventory",
#                     "localField": "_id",
#                     "foreignField": "vouchar_id",
#                     "as": "inventory",
#                 }
#             },
#             {
#                 "$addFields": {
#                     "ledger_entries": {
#                         "$map": {
#                             "input": {
#                                 "$filter": {
#                                     "input": "$accounting",
#                                     "as": "entry",
#                                     "cond": {"$eq": ["$$entry.ledger", "$party_name"]},
#                                 }
#                             },
#                             "as": "entry",
#                             "in": {
#                                 "ledgername": "$$entry.ledger",
#                                 "amount": "$$entry.amount",
#                                 "is_deemed_positive": {
#                                     "$cond": [{"$lt": ["$$entry.amount", 0]}, True, False]
#                                 },
#                                 "amount_absolute": {"$abs": "$$entry.amount"},
#                             },
#                         }
#                     }
#                 }
#             },
#             {"$unwind": {"path": "$ledger_entries", "preserveNullAndEmptyArrays": True}},
#             {
#                 "$project": {
#                     "_id": 1,
#                     "date": 1,
#                     "voucher_number": 1,
#                     "voucher_type": 1,
#                     "_voucher_type": 1,
#                     "party_name": 1,
#                     "_party_name": 1,
#                     "narration": 1,
#                     # "amount": "$ledger_entries.amount",
#                     "balance_type": 1,
#                     # "ledger_name": "$ledger_entries.ledgername',",
#                     # "is_deemed_positive": "$ledger_entries.is_deemed_positive",
#                     "ledger_entries": 1,
#                     "created_at": 1,
#                 }
#             },
#         ]
#     ).to_list(None)

#     return {"success": True, "message": "Data Fetched Successfully...", "data": result}
