from fastapi import APIRouter

from app.Config import ENV_PROJECT
from app.routes.api.v1.auth import auth as auth_endpoints
from app.routes.api.v1.user import user as user_endpoints
from app.routes.api.v1.admin import admin as admin_endponits
from app.routes.api.v1.stockItem import Product as stock_items_endpoints
from app.routes.api.v1.voucharType import VoucharType as vouchar_type_endpoints
from app.routes.api.v1.vouchar import Vouchar as vouchar_endpoints
from app.routes.api.v1.voucharCounter import counter_router as vouchar_counter_endpoints
from app.routes.api.v1.userSettings import user_settings_router as user_settings_endpoints
from app.routes.api.v1.taxModel import admin as admin_tax_endponits
from app.routes.api.v1.companySettings import (
    company_settings_router as company_settings_endpoints,
)
from app.routes.api.v1.category import category_router as category_endpoints
from app.routes.api.v1.extraction import extraction as extraction_endpoints
from app.routes.api.v1.accountingGroup import (
    accounting_group_router as accounting_group_endpoints,
)
from app.routes.api.v1.inventoryGroup import (
    inventory_group_router as inventory_group_endpoints,
)
from app.routes.api.v1.ledger import ledger as customer_endpoints

routers = APIRouter()

routers.include_router(
    auth_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/auth",
    tags=["Authentication"],
)

routers.include_router(
    admin_endponits, prefix=ENV_PROJECT.BASE_API_V1 + "/admin", tags=["Admin"]
)

routers.include_router(
    admin_tax_endponits, prefix=ENV_PROJECT.BASE_API_V2 + "/admin/tax", tags=["Admin"]
)

routers.include_router(
    user_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user",
    tags=["User"],
)

routers.include_router(
    user_settings_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user/settings",
    tags=["User Settings"],
)

routers.include_router(
    company_settings_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user/company/settings",
    tags=["User Company Settings"],
)

routers.include_router(
    customer_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/ledger",
    tags=["Customers"],
)

routers.include_router(
    accounting_group_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user",
    tags=["Customer Group"],
)

routers.include_router(
    stock_items_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/product",
    tags=["Stock Items"],
)

routers.include_router(
    inventory_group_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user",
    tags=["Stock Items Group"],
)

routers.include_router(
    category_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/category",
    tags=["Stock Items Category"],
)

routers.include_router(
    vouchar_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/invoices",
    tags=["Vouchars"],
)

routers.include_router(
    vouchar_type_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/invoices",
    tags=["Vouchar Type"],
)

routers.include_router(
    vouchar_counter_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/invoices/serial-number",
    tags=["Serial Numbers"],
)

routers.include_router(
    extraction_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/extraction",
    tags=["Extraction"],
)
