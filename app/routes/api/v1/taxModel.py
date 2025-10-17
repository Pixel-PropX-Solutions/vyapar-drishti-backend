from fastapi import FastAPI, status, Depends
from fastapi.responses import ORJSONResponse
from fastapi import APIRouter
from app.schema.token import TokenData
from app.oauth2 import get_current_user

import app.http_exception as http_exception
from app.database.repositories.taxModelRepo import tax_model_repo
from app.database.repositories.user import user_repo
from app.database.models.TaxModel import TaxModel
import re
from collections import defaultdict


admin = APIRouter()

GSTModel = {
    "_id": "c2a19edf-b4fb-4ff9-a2ea-a996e0fee9e1",
    "tax_name": "GST",
    "tax_code": "GST",
    "tax_description": "Goods and Service Tax",
    "tax_type": "GST",
    "tax_rate": 1,
    "tax_rate_type": "percentage",
    "components": [
        {"name": "IGST", "rate": 1, "rate_type": "percentage"},
        {"name": "CGST", "rate": 0.5, "rate_type": "percentage"},
        {"name": "SGST", "rate": 0.5, "rate_type": "percentage"},
    ],
    "dependencies": [],
    "created_at": {"$date": "2025-08-15T13:56:13.946Z"},
    "updated_at": {"$date": "2025-08-15T13:56:13.946Z"},
}

VATModel = {
    "_id": "50dabce6-8ac9-4ca0-9d4f-588648e45fde",
    "tax_name": "VAT",
    "tax_code": "VAT",
    "tax_description": "Value Added Tax",
    "tax_type": "VAT",
    "tax_rate": 1,
    "tax_rate_type": "percentage",
    "components": [],
    "dependencies": [],
    "created_at": {"$date": "2025-08-15T16:46:05.724Z"},
    "updated_at": {"$date": "2025-08-15T16:46:05.724Z"},
}


async def get_current_user_tax_model(
    current_user: TokenData,
):
    userExists = await user_repo.findOne({"_id": current_user.user_id})
    if userExists is None:
        raise http_exception.ResourceNotFoundException(detail="User not found.")

    if '91' in userExists["phone"]["code"]:
        return GSTModel
    else:
        return VATModel

    # result = await tax_model_repo.findOne(
    #     {"jurisdiction": {"$in": [userExists["phone"]["code"]]}}
    # )
    # if result is None:
    #     raise http_exception.ResourceNotFoundException(detail="Tax model not found.")
    # return result


def generate_gst_summary(items: list, party_details: dict, company: dict):

    is_same_state = party_details.get("mailing_state", "") == company.get("state", "")

    tax_summary = defaultdict(
        lambda: {
            "igst": 0.0,
            "sgst": 0.0,
            "cgst": 0.0,
            "tax_amount": 0.0,
            "taxable_value": 0.0,
        }
    )

    for detail in items:
        try:
            rate = float(detail.get("tax_rate", 0))
        except Exception:
            rate = 0.0

        tax_summary[rate]["sgst"] += (
            float(detail.get("tax_amount", 0.0) / 2) if is_same_state else 0.0
        )
        tax_summary[rate]["cgst"] += (
            float(detail.get("tax_amount", 0.0) / 2) if is_same_state else 0.0
        )
        tax_summary[rate]["igst"] += (
            float(detail.get("tax_amount", 0.0)) if not is_same_state else 0.0
        )

        tax_summary[rate]["taxable_value"] += float(
            detail.get("total_amount", 0.0) - detail.get("tax_amount", 0.0)
        )
        tax_summary[rate]["tax_amount"] += float(detail.get("tax_amount", 0.0))

    invoice_taxes = []

    totals = {
        "igst": 0.0,
        "sgst": 0.0,
        "cgst": 0.0,
        "tax_amount": 0.0,
        "taxable_value": 0.0,
    }

    for rate, vals in tax_summary.items():
        invoice_taxes.append(
            {
                "entity": rate,
                "igst": round(vals["igst"], 2),
                "sgst": round(vals["sgst"], 2),
                "cgst": round(vals["cgst"], 2),
                "taxable_value": round(vals["taxable_value"], 2),
                "tax_amount": round(vals["tax_amount"], 2),
            }
        )
        totals["igst"] += vals["igst"]
        totals["sgst"] += vals["sgst"]
        totals["cgst"] += vals["cgst"]
        totals["taxable_value"] += vals["taxable_value"]
        totals["tax_amount"] += vals["tax_amount"]

    tax_headers = [
        "GST (%)",
        "Taxable Amt.",
        "IGST",
        "CGST",
        "SGST",
        "GST Amt.",
    ]

    totals = {k: round(v, 2) for k, v in totals.items()}
    return totals, invoice_taxes, tax_headers


def generate_hsn_gst_summary(items: list, party_details: dict, company: dict):
    is_same_state = party_details.get("mailing_state", "") == company.get("state", "")

    tax_summary = defaultdict(
        lambda: {
            "igst": 0.0,
            "sgst": 0.0,
            "cgst": 0.0,
            "tax_amount": 0.0,
            "taxable_value": 0.0,
        }
    )

    for detail in items:
        try:
            hsn_code = detail.get("hsn", "")
        except Exception:
            hsn_code = ""

        tax_summary[hsn_code]["sgst"] += (
            float(detail.get("tax_amount", 0.0) / 2) if is_same_state else 0.0
        )
        tax_summary[hsn_code]["cgst"] += (
            float(detail.get("tax_amount", 0.0) / 2) if is_same_state else 0.0
        )
        tax_summary[hsn_code]["igst"] += (
            float(detail.get("tax_amount", 0.0)) if not is_same_state else 0.0
        )

        tax_summary[hsn_code]["taxable_value"] += float(
            detail.get("total_amount", 0.0) - detail.get("tax_amount", 0.0)
        )
        tax_summary[hsn_code]["tax_amount"] += float(detail.get("tax_amount", 0.0))

    invoice_taxes = []

    totals = {
        "igst": 0.0,
        "sgst": 0.0,
        "cgst": 0.0,
        "tax_amount": 0.0,
        "taxable_value": 0.0,
    }

    for hsn_code, vals in tax_summary.items():
        invoice_taxes.append(
            {
                "entity": hsn_code,
                "igst": round(vals["igst"], 2),
                "sgst": round(vals["sgst"], 2),
                "cgst": round(vals["cgst"], 2),
                "taxable_value": round(vals["taxable_value"], 2),
                "tax_amount": round(vals["tax_amount"], 2),
            }
        )
        totals["igst"] += vals["igst"]
        totals["sgst"] += vals["sgst"]
        totals["cgst"] += vals["cgst"]
        totals["taxable_value"] += vals["taxable_value"]
        totals["tax_amount"] += vals["tax_amount"]

    tax_headers = [
        "HSN Code",
        "Taxable Amt.",
        "IGST",
        "CGST",
        "SGST",
        "GST Amt.",
    ]

    totals = {k: round(v, 2) for k, v in totals.items()}
    return totals, invoice_taxes, tax_headers


async def generate_tax_summary(
    items: list, party_details: dict, company: dict, current_user: TokenData
):
    tax_model = await get_current_user_tax_model(current_user)
    if tax_model["tax_code"] == "GST":
        totals, invoice_taxes, tax_headers = generate_gst_summary(
            items=items, party_details=party_details, company=company
        )
        return totals, invoice_taxes, tax_headers, tax_model["tax_code"]
    else:
        return '', '', '', "VAT"


@admin.post("/create/tax", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def create_tax(
    tax: TaxModel,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    taxExists = await tax_model_repo.findOne({"tax_code": tax.tax_code})
    if taxExists is not None:
        raise http_exception.ResourceNotFoundException(
            detail="Tax with this code already exists."
        )

    # Validate tax_code format
    if not re.match(r"^[A-Z0-9]+$", tax.tax_code):
        raise http_exception.ValidationException(
            detail="Tax code must be alphanumeric and uppercase."
        )
    # Validate jurisdiction format
    if not isinstance(tax.jurisdiction, list) or not all(
        re.match(r"^\+\d{1,3}$", code) for code in tax.jurisdiction
    ):
        raise http_exception.ValidationException(
            detail="Jurisdiction must be a list of valid country codes."
        )
    # Validate tax_rate
    if tax.tax_rate < 0:
        raise http_exception.ValidationException(
            detail="Tax rate must be a non-negative number."
        )

    # Convert TaxModel to TaxModelDB
    inserted_dict = tax.model_dump()

    await tax_model_repo.new(TaxModel(**inserted_dict))

    return {"success": True, "message": "Tax Inserted Successfully"}


@admin.get("/get/tax", response_class=ORJSONResponse, status_code=status.HTTP_200_OK)
async def get_tax(
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException(
            detail="You do not have permission to access this resource."
        )

    response = await tax_model_repo.findMany({})

    return {
        "success": True,
        "message": "Tax fetched successfully",
        "data": response,
    }


@admin.get(
    "/get/tax/{tax_id}", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def get_tax_by_id(
    tax_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    response = await tax_model_repo.findOne({"id": tax_id})
    if response is None:
        raise http_exception.ResourceNotFoundException(detail="Tax not found.")

    return ORJSONResponse(
        content={
            "success": True,
            "message": "Tax fetched successfully",
            "data": response,
        },
        status_code=status.HTTP_200_OK,
    )


@admin.put(
    "/update/tax/{tax_id}", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def update_tax(
    tax_id: str,
    tax: TaxModel,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    existing_tax = await tax_model_repo.findOne({"id": tax_id})
    if existing_tax is None:
        raise http_exception.ResourceNotFoundException(detail="Tax not found.")

    # Validate and update the tax model
    tax_data = tax.model_dump()
    await tax_model_repo.update({"id": tax_id}, tax_data)

    return ORJSONResponse(
        content={
            "success": True,
            "message": "Tax updated successfully",
            "data": tax_data,
        },
        status_code=status.HTTP_200_OK,
    )


@admin.delete(
    "/delete/tax/{tax_id}", response_class=ORJSONResponse, status_code=status.HTTP_200_OK
)
async def delete_tax(
    tax_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    if current_user.user_type != "admin":
        raise http_exception.CredentialsInvalidException()

    existing_tax = await tax_model_repo.findOne({"id": tax_id})
    if existing_tax is None:
        raise http_exception.ResourceNotFoundException(detail="Tax not found.")

    await tax_model_repo.delete({"id": tax_id})

    return ORJSONResponse(
        content={"success": True, "message": "Tax deleted successfully"},
        status_code=status.HTTP_200_OK,
    )
