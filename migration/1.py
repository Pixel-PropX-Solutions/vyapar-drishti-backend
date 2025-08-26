from pymongo import MongoClient

# -----------------------------
# MongoDB Connection
# -----------------------------
client = MongoClient("")  # update with your connection string
db = client[""]  # change to your DB name


def run_migrations():
    tax_models = [
        {
            "_id": "c2a19edf-b4fb-4ff9-a2ea-a996e0fee9e1",
            "tax_name": "GST",
            "tax_code": "GST",
            "tax_description": "Goods and Service Tax",
            "jurisdiction": ["+91"],
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
        },
        {
            "_id": "50dabce6-8ac9-4ca0-9d4f-588648e45fde",
            "tax_name": "VAT",
            "tax_code": "VAT",
            "tax_description": "Value Added Tax",
            "jurisdiction": ["+1"],
            "tax_type": "VAT",
            "tax_rate": 1,
            "tax_rate_type": "percentage",
            "components": [],
            "dependencies": [],
            "created_at": {"$date": "2025-08-15T16:46:05.724Z"},
            "updated_at": {"$date": "2025-08-15T16:46:05.724Z"},
        },
    ]

    # 1. First query to update the fields
    db.StockItem.aggregate([
        {"$addFields": {
            "hsn_code": "$gst_hsn_code",
            "nature_of_goods": "$gst_nature_of_goods",
            "taxability": "$gst_taxability"
        }},
        {"$project": {
            "gst_hsn_code": 0,
            "gst_nature_of_goods": 0,
            "gst_taxability": 0
        }},
        {"$lookup": {
            "from": "GSTRate",
            "let": {"hsn": "$hsn_code", "nature": "$nature_of_goods", "taxability": "$taxability", "itemId": "$_id"},
            "pipeline": [
                {"$match": {"$expr": {
                    "$and": [
                        {"$eq": ["$item_id", "$$itemId"]},
                        {"$eq": ["$hsn_code", "$$hsn"]},
                        {"$eq": ["$nature_of_goods", "$$nature"]},
                        {"$eq": ["$taxability", "$$taxability"]}
                    ]
                }}},
                {"$project": {"_id": 0, "rate": 1}}
            ],
            "as": "rate_data"
        }},
        {"$addFields": {"tax_rate": {"$arrayElemAt": ["$rate_data.rate", 0]}}},
        {"$project": {"rate_data": 0}},
        {"$merge": {"into": "StockItem", "whenMatched": "merge", "whenNotMatched": "discard"}}
    ])
    
    print('Tax fields added to StockItem')

    # 2. Remove unused fields
    db.StockItem.update_many({}, {"$unset": {
        "gst_hsn_code": "",
        "gst_nature_of_goods": "",
        "gst_taxability": ""
    }})
    print('Unused GST fields removed from StockItem')

    # 3. Convert tax_rate from string to float
    db.StockItem.update_many({"tax_rate": {"$type": "string"}}, [
        {"$set": {"tax_rate": {"$toDouble": "$tax_rate"}}}
    ])
    print('Converted tax_rate from string to float in StockItem')

    # 4. Add tax_rate, hsn_code, and tax_amount to inventory
    for doc in db.VoucherGST.aggregate([
        {"$unwind": "$item_gst_details"},
        {"$project": {
            "vouchar_id": "$voucher_id",
            "item_id": "$item_gst_details.item_id",
            "hsn_code": "$item_gst_details.hsn_code",
            "tax_rate": {"$toDouble": "$item_gst_details.gst_rate"},
            "tax_amount": {"$round": [
                {"$subtract": ["$item_gst_details.total_amount", "$item_gst_details.taxable_value"]}, 2]}
        }}
    ]):
        db.Inventory.update_many(
            {"vouchar_id": doc["vouchar_id"], "item_id": doc["item_id"]},
            {"$set": {
                "hsn_code": doc.get("hsn_code"),
                "tax_rate": doc.get("tax_rate"),
                "tax_amount": doc.get("tax_amount")
            }}
        )
    print('Added tax_rate, hsn_code, and tax_amount to Inventory')

    # 5. Add total_tax and total_amount to voucher
    db.Voucher.aggregate([
        {"$lookup": {
            "from": "Inventory",
            "localField": "_id",
            "foreignField": "vouchar_id",
            "as": "inventory_items"
        }},
        {"$addFields": {
            "total_amount": {"$round": [{"$sum": "$inventory_items.amount"}, 2]},
            "total_tax": {"$round": [{"$sum": "$inventory_items.tax_amount"}, 2]}
        }},
        {"$project": {"inventory_items": 0}},
        {"$merge": {"into": "Voucher", "whenMatched": "merge", "whenNotMatched": "discard"}}
    ])
    print('Added total_tax and total_amount to Voucher')

    # 6. Remove unused fields from voucher
    db.Voucher.update_many({}, {"$unset": {
        "is_invoice": "",
        "is_accounting_voucher": "",
        "is_order_voucher": "",
        "is_inventory_voucher": ""
    }})
    print('Removed unused fields from Voucher')

    # 7. Add additional_charge, discount, total, grand_total
    db.Voucher.update_many({}, [
        {"$set": {
            "additional_charge": 0,
            "discount": 0,
            "total": {"$round": [{"$subtract": ["$total_amount", 0]}, 2]},
            "grand_total": {"$round": [
                {"$subtract": [{"$add": ["$total_amount", "$total_tax", 0]}, 0]}, 2]}
        }}
    ])
    print('Added additional_charge, discount, total, grand_total to Voucher')

    # 8. Update grand_total from accounting
    db.Voucher.aggregate([
        {"$lookup": {
            "from": "Accounting",
            "localField": "_id",
            "foreignField": "vouchar_id",
            "as": "accounting_items"
        }},
        {"$set": {
            "grand_total": {"$abs": {"$first": "$accounting_items.amount"}}
        }},
        {"$project": {"accounting_items": 0}},
        {"$merge": {"into": "Voucher", "whenMatched": "merge", "whenNotMatched": "discard"}}
    ])
    print('Updated grand_total from Accounting in Voucher')

    # 9. Update inventory unused fields
    db.Inventory.update_many({}, [
        {"$set": {
            "total_amount": "$additional_amount",
            "tax_amount": 0,
            "tax_rate": 0
        }},
        {"$unset": ["additional_amount", "order_number", "order_due_date"]}
    ])
    print('Updated unused fields in Inventory')

    # 10. Update inventory total_amount, tax_rate, etc. from StockItem
    db.Inventory.aggregate([
        {"$lookup": {
            "from": "StockItem",
            "localField": "item_id",
            "foreignField": "_id",
            "as": "stock"
        }},
        {"$set": {"stock": {"$arrayElemAt": ["$stock", 0]}}},
        {"$set": {
            "tax_rate": {"$ifNull": ["$stock.tax_rate", 0]},
            "hsn_code": {"$ifNull": ["$stock.hsn_code", None]},
            "unit": {"$ifNull": ["$stock.unit", None]},
            "tax_amount": {"$round": [
                {"$multiply": ["$amount", {"$divide": [{"$ifNull": ["$stock.tax_rate", 0]}, 100]}]}, 2]},
            "total_amount": {"$round": [
                {"$add": ["$amount", {"$multiply": ["$amount", {"$divide": [{"$ifNull": ["$stock.tax_rate", 0]}, 100]}]}]}, 2]}
        }},
        {"$unset": "stock"},
        {"$merge": {"into": "Inventory", "whenMatched": "merge", "whenNotMatched": "discard"}}
    ])
    print('Updated inventory total_amount, tax_rate, etc. from StockItem')

    # 11. Update Company
    db.Company.update_many({}, [
        {"$set": {"tin": "$gstin"}},
        {"$unset": ["gstin", "pan"]}
    ])
    print('Updated Company with tin from gstin')

    # 12. Update CompanySettings
    db.CompanySettings.update_many({}, [
        {"$set": {
            "tax_details": {
                "tin": "$gst_details.gstin",
                "tax_registration": "$gst_details.gst_registration_type",
                "place_of_supply": "$gst_details.place_of_supply"
            },
            "features.enable_tax": "$features.enable_gst",
            "features.item_wise_tax": "$features.item_wise_gst"
        }},
        {"$unset": ["gst_details", "features.enable_gst", "features.item_wise_gst", "financial_year_format"]}
    ])
    print('Updated CompanySettings with tax_details and features')

    # 13. Update Ledger
    db.Ledger.update_many({}, [
        {"$set": {
            "tin": "$gstin",
            "tax_registration": "$gst_registration_type"
        }},
        {"$unset": ["gstin", "gst_registration_type", "it_pan", "gst_supply_type"]}
    ])
    print('Updated Ledger with tin and tax_registration from gstin and gst_registration_type')
    
    # 14. Use upsert-like logic: only insert if not already present
    for model in tax_models:
        db.TaxModel.update_one({"_id": model["_id"]}, {"$setOnInsert": model}, upsert=True)
    print('Inserted predefined Tax Models if not already present')

    # -------------------------------------------------
    # 15: Drop GSTRate and VoucherGST collections
    # -------------------------------------------------
    db.drop_collection("GSTRate")
    db.drop_collection("VoucherGST")
    print('Dropped GSTRate and VoucherGST collections')


if __name__ == "__main__":
    run_migrations()
    print("All migration queries executed successfully.")
