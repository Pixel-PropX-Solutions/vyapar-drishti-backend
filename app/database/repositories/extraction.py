import json
import cv2
import fitz
import numpy as np
import pytesseract
import tempfile
from uuid import uuid4
from pdf2image import convert_from_path
from app.Config import ENV_PROJECT

# import google
# # from google import genai
# from app.utils.openai import gemini
# from google import genai
pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"
from app.Config import ENV_PROJECT

import google.generativeai as genai

genai.configure(api_key=ENV_PROJECT.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")


class ExtractionTools:
    async def text_extraction_for_scanned_and_selectable_file_for_json_format_through_gemini(
        self, file
    ):
        input_token = 0
        output_token = 0
        extracted_text = ""

        filename = file.filename
        text_file_name = str(uuid4()) + filename.split("/")[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file_content = await file.read()
            temp_file.write(temp_file_content)
            temp_file_path = temp_file.name

        docs = fitz.open(temp_file_path)
        for page_num in range(len(docs)):
            data = docs[page_num].get_text("text")
            extracted_text += data

        if len(extracted_text) < 50:
            extracted_text = ""
            with open("./extract.txt", mode="w") as text_file:
                images = convert_from_path(temp_file_path)
                for i, image in enumerate(images):
                    image = np.array(image)
                    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    text = pytesseract.image_to_string(grey)
                    extracted_text += text
                    text_file.write(f"{text_file_name} - Page No {i + 1}\n\n")
                    text_file.write(text)
                    text_file.write("\n\n")
        prompt = f"""
        You are a billing parser that extracts the following information from a bill text into a JSON object. The bill can be either a sale or a purchase, but not both. If a field is not found, use "null". If the bill is a sale, fill the 'sale' object (using the Sale model fields) and set 'purchase' to null. If the bill is a purchase, fill the 'purchase' object (using the Purchase model fields) and set 'sale' to null. Use the following structure and field names:

        Output Format:
        {{
            "sale": {{
                "status": "string",
                "creditor": {{
                    "name": {{
                        "first": "string",
                        "last": "string",
                    }},
                    "phone": "string",
                    "email": "string",
                    "tin": "string",
                    "company_name": "string",
                    "billing_address": {{
                        "state":  "string",
                        "address_1":  "string",
                        "address_2":  "string",
                        "pinCode": "string",
                        "city": "string",
                        "country": "string",
                    }},
                    "shipping_address":{{
                        "title": "string",
                        "notes": "string",
                        "state":  "string",
                        "address_1":  "string",
                        "address_2":  "string",
                        "pinCode": "string",
                        "city": "string",
                        "country": "string",
                    }},
                }},
                "debitor": {{
                    "name": {{
                        "first": "string",
                        "last": "string",
                    }},
                    "billing_address": {{
                        "state":  "string",
                        "address_1":  "string",
                        "address_2":  "string",
                        "pinCode": "string",
                        "city": "string",
                        "country": "string",
                    }},
                    "phone": "string",
                    "email": "string",
                    "company_name": "string",
                    "tin": "string",
                }},
                "product_details": [
                    {{
                        "name": "string",
                        "quantity": 0,
                        "unit_price": 0.0,
                        "total_price": 0.0,
                        "tax_rate": 0.0,
                        "tax_amount": 0.0,
                        "discount": 0.0,
                        "discount_amount": 0.0
                    }}
                ],
                "sale_number": "string",
                "date": "DD-MM-YYYY",
                "due_date": "DD-MM-YYYY",
                "payment_method": "string",
                "tax_total": 0.0,
                "total_discount": 0.0,
                "total_amount": 0.0,
                "total_tax_amount": 0.0,
                "round_off_amount": 0.0,
                "grand_total": 0.0
            }},
            "purchase": {{
                "status": "string",
                "creditor": {{
                    "name": {{
                        "first": "string",
                        "last": "string",
                    }},
                    "phone": "string",
                    "email": "string",
                    "tin": "string",
                    "company_name": "string",
                    "billing_address": {{
                        "state":  "string",
                        "address_1":  "string",
                        "address_2":  "string",
                        "pinCode": "string",
                        "city": "string",
                        "country": "string",
                    }},
                    "shipping_address": {{
                        "title": "string",
                        "notes": "string",
                        "state":  "string",
                        "address_1":  "string",
                        "address_2":  "string",
                        "pinCode": "string",
                        "city": "string",
                        "country": "string",
                    }},
                }},
                "debitor": {{
                    "name": {{
                        "first": "string",
                        "last": "string",
                    }},
                    "billing_address": {{
                        "state":  "string",
                        "address_1":  "string",
                        "address_2":  "string",
                        "pinCode": "string",
                        "city": "string",
                        "country": "string",
                    }},
                    "phone": "string",
                    "email": "string",
                    "company_name": "string",
                    "tin": "string",
                }},
                "product_details": [
                    {{
                        "name": "string",
                        "quantity": 0,
                        "unit_price": 0.0,
                        "total_price": 0.0,
                        "tax_rate": 0.0,
                        "tax_amount": 0.0,
                        "discount": 0.0,
                        "discount_amount": 0.0
                    }}
                ],
                "date": "DD-MM-YYYY",
                "due_date": "DD-MM-YYYY",
                "purchase_number": "string",
                "invoice_number": "string",
                "payment_method": "string",
                "tax_total": 0.0,
                "total_discount": 0.0,
                "total_amount": 0.0,
                "toatal_tax_amount": 0.0,
                "round_off_amount": 0.0,
                "grand_total": 0.0
            }}
        }}
        
        Field Explanations:
        - sale / purchase: The root object will have both "sale" and "purchase" keys. Only one will be filled based on the bill type; the other will be null.
        
        creditor: The party selling the goods/services (for sale: seller, for purchase: supplier)
        - name: Name of the creditor (seller/supplier).
            - name.first: First name of the creditor.
            - name.last: Last name of the creditor (if available).
        - phone: Contact number of the creditor.
        - email: Email address of the creditor.
        - tin: TAX Identification Number of the creditor.
        - company_name: Name of the creditor's company.
        - billing_address: Object containing the billing address fields:
            - state: State of the billing address.
            - address_1: First line of the billing address.
            - address_2: Second line of the billing address.
            - pinCode: Postal code of the billing address.
            - city: City of the billing address.
            - country: Country of the billing address.
        - shipping_address: Object containing the shipping address fields:
            - title: Title or label for the shipping address (optional).
            - notes: Any notes related to the shipping address (optional).
            - state: State of the shipping address.
            - address_1: First line of the shipping address.
            - address_2: Second line of the shipping address.
            - pinCode: Postal code of the shipping address.
            - city: City of the shipping address.
            - country: Country of the shipping address.
        
        debitor: The party buying the goods/services (for sale: buyer, for purchase: purchaser)
        - name: Name of the debitor (buyer/purchaser).
            - name.first: First name of the debitor.
            - name.last: Last name of the debitor (if available).
        - billing_address: Object containing the billing address fields:
            - state: State of the billing address.
            - address_1: First line of the billing address.
            - address_2: Second line of the billing address.
            - pinCode: Postal code of the billing address.
            - city: City of the billing address.
            - country: Country of the billing address.
        - phone: Contact number of the debitor.
        - email: Email address of the debitor.
        - company_name: Name of the debitor's company.
        - tin: TAX Identification Number of the debitor.
        
        product_details: A list of products/items in the bill. Each item contains:
        - name: Name of the product (can expand upto 2 or three lines).
        - quantity: Number of units of the product.
        - unit_price: Price per unit of the product.
        - total_price: Total price for the product (quantity × unit_price).
        - tax_rate: Tax rate applied to the product (percentage) (sum of all the type of tax rates for that product)..
        - tax_amount: Tax amount for the product (sum of all the type of taxes for that product).
        - discount: Discount rate applied to the product can be percentage or a particular amount for that product.
        - discount_amount: Discount amount for the product.
        
        Sale-Specific Fields:
        - sale_number: Unique sequential code assigned to the sale bill.
        - date: Date of the sale bill in DD-MM-YYYY format.
        - due_date: Due date for payment in DD-MM-YYYY format.
        - payment_method: Payment method used (e.g., CASH, CARD, etc.).
        - tax_total: Total TAX amount for the sale.
        - total_discount: Total discount applied to the sale (or can be sum of the individuals discounts of the products in product details).
        - total_amount: Total amount before taxes and discounts.
        - toatal_tax_amount: Total tax amount for the sale (e.g. summation of the tax_amount of all the products in the product_details).
        - round_off_amount: Rounding adjustment applied to the final amount.
        - grand_total: Final/net amount to be paid for the sale.
        - status: Status of the sale bill (e.g., PENDING, PAID).
        
        Purchase-Specific Fields:
        - purchase_number: Unique sequential code assigned to the purchase bill.
        - invoice_number: Invoice number for the purchase bill.
        - date: Date of the purchase bill in DD-MM-YYYY format.
        - due_date: Due date for payment in DD-MM-YYYY format.
        - payment_method: Payment method used (e.g., CASH, CARD, etc.).
        - tax_total: Total TAX amount for the purchase.
        - total_discount: Total discount amount applied to the purchase (or can be sum of the individuals discount_amount of the products in product details).
        - total_amount: Total amount before taxes and discounts.
        - toatal_tax_amount: Total tax amount for the purchase  (e.g. summation of the tax_amount of all the products in the product_details).
        - round_off_amount: Rounding adjustment applied to the final amount (can be positive or negative depending on the amount after the decimal point).
        - grand_total: Final/net amount to be paid for the purchase.
        - status: Status of the purchase bill (e.g., PENDING, PAID).
        
        
        Instructions:
        - Extract the text from the bill and format it into the JSON structure provided.
        - Ensure that the JSON is valid and follows the structure exactly.
        - If a field is not applicable or not found, set it to "null".
        - The 'sale' object should be filled if the bill is a sale, and the 'purchase' object should be null.
        - The 'purchase' object should be filled if the bill is a purchase, and the 'sale' object should be null.
        - The 'status' field should be set to "PENDING" if not specified.
        - The 'payment_method' field should be set to "CASH" if not specified.
        - The 'date' and 'due_date' fields should be in the format "DD-MM-YYYY".
        - The 'product_details' array should contain objects with the specified fields.
        - The 'tax_total', 'discount', 'total_amount', 'tax_amount', 'round_off_amount', and 'grand_total' fields should be numeric values.
        - The 'creditor' and 'debitor' objects should contain the specified fields.
        - Try dividing the address into 'address_1' and 'address_2' if possible, otherwise set 'address_2' to null.
        - Try dividing the name of the creditor and debitor into first name and last name if possible, otherwise set last name to null.
        - The 'billing_address' and 'shipping_address' objects should contain the specified fields.
        - The 'shipping_address' title and notes fields are optional and can be null.
        - The 'company_name' field in the 'creditor' and 'debitor' objects is optional and can be null.
        - The 'address_2' field in the 'billing_address' and 'shipping_address' objects is optional and can be null.
        - The 'phone' and 'email' fields in the 'creditor' and 'debitor' objects are optional and can be null.
        - The 'tin' field in the 'creditor' and 'debitor' objects is optional and can be null.
        - The 'name' field in the 'creditor' and 'debitor' objects is mandatory.
        - The 'product_details' array should contain at least one product object.
        - The 'name' field in the 'product_details' array is mandatory.
        - The 'quantity', 'unit_price', 'total_price', 'tax_rate', 'tax_amount', 'discount', and 'discount_amount' fields in the 'product_details' array are mandatory and should be numeric and if not present in bill then set them to 0 or null as specified.
        - The 'tax_amount' field in the 'product_details' array should be calculated as ('total_price' × 'tax_rate') / 100.
        - The 'discount_amount' field in the 'product_details' array should be calculated as ('total_price' × 'discount') / 100 if the dicount is percentage type.
        - The 'grand_total' field should be calculated as the sum of all 'total_price' in 'product_details' plus 'tax_total' minus 'discount' plus 'round_off_amount'.
        - The 'tax_total' field should be the sum of all 'tax_amount' in 'product_details'.
        
        Only one of 'sale' or 'purchase' will be filled based on the bill type, the other must be null.
        The output should be a valid JSON object with the above structure.
        Input Text:
        {extracted_text}
        """
        response = model.generate_content(prompt)
        content = response.text.strip()
        if content.startswith("```json"):
            content = content[len("```json") :].strip()
        if content.endswith("```"):
            content = content[: -len("```")].strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            print("[Gemini JSON Parse Error]", e)
            print("[Gemini Raw Content]:\n", content)
            # Optionally, you can raise a custom exception or return a structured error
            data = None

        # print("Extracted Data :", data)

        # return data


extraction_tools = ExtractionTools()
