from fastapi import APIRouter

from app.Config import ENV_PROJECT
from app.routes.api.v1.auth import auth as auth_endpoints
from app.routes.api.v1.user import user as user_endpoints

# from app.routes.api.v1.billing import billing as billing_endpoints
# from app.routes.api.v1.shipping import shipping as shipping_endpoints
# from app.routes.api.v1.creditor import creditor as creditor_endpoints
# from app.routes.api.v1.debitor import debitor as debitor_endpoints
from app.routes.api.v1.admin import admin as admin_endponits
from app.routes.api.v1.stockItem import Product as product_endpoints
from app.routes.api.v1.voucharType import VoucharType as vouchar_type_endpoints
from app.routes.api.v1.vouchar import Vouchar as vouchar_endpoints
from app.routes.api.v1.voucharCounter import counter_router as vouchar_counter_endpoints

# from app.routes.api.v1.cloudinary import Cloudinary as cloudinary_endpoints
from app.routes.api.v1.category import category_router as category_endpoints

# from app.routes.api.v1.inventory import inventory as inventory_endpoints
# from app.routes.api.v1.orders import OrdersRouter as orders_endpoints
from app.routes.api.v1.extraction import extraction as extraction_endpoints

# from app.routes.api.v1.product_stock import product_Stock as product_Stock_endpoints
# from app.routes.api.v1.stock_movement import stock_movement as stock_movement_endpoints

from app.routes.api.v1.accountingGroup import accounting_group_router as accounting_group_endpoints
from app.routes.api.v1.inventoryGroup import inventory_group_router as inventory_group_endpoints
from app.routes.api.v1.ledger import ledger as ledger_endpoints
# from app.routes.api.v1.analytics import Analytics as analytics_endpoints

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
    user_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user",
    tags=["User"],
)

routers.include_router(
    vouchar_type_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user",
    tags=["Vouchar Type"],
)

routers.include_router(
    vouchar_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user",
    tags=["Vouchars"],
)

routers.include_router(
    vouchar_counter_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user/vouchar_counter",
    tags=["Vouchar Counter"],
)

routers.include_router(
    accounting_group_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user",
    tags=["Accounting Group"],
)

routers.include_router(
    inventory_group_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/user",
    tags=["Inventory Group"],
)

routers.include_router(
    ledger_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/ledger",
    tags=["Ledger"],
)

# routers.include_router(
#     shipping_endpoints,
#     prefix=ENV_PROJECT.BASE_API_V1 + "/user",
#     tags=["Shipping"],
# )

routers.include_router(
    product_endpoints, prefix=ENV_PROJECT.BASE_API_V1 + "/product", tags=["Product"]
)

# routers.include_router(
#     cloudinary_endpoints,
#     prefix=ENV_PROJECT.BASE_API_V1 + "/cloudinary",
#     tags=["Cloudinary"],
# )

routers.include_router(
    category_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/category",
    tags=["Category"],
)

# routers.include_router(
#     inventory_endpoints, prefix=ENV_PROJECT.BASE_API_V1 + "/inventory", tags=["Inventory"]
# )

# routers.include_router(
#     orders_endpoints, prefix=ENV_PROJECT.BASE_API_V1 + "/orders", tags=["Orders"]
# )

routers.include_router(
    extraction_endpoints,
    prefix=ENV_PROJECT.BASE_API_V1 + "/extraction",
    tags=["Extraction"],
)

# routers.include_router(
#     product_Stock_endpoints,
#     prefix=ENV_PROJECT.BASE_API_V1 + "/product_stock",
#     tags=["Product Stock"],
# )

# routers.include_router(
#     stock_movement_endpoints,
#     prefix=ENV_PROJECT.BASE_API_V1 + "/stock_movement",
#     tags=["Stock Movement"],
# )

# routers.include_router(
#     sales_endpoints,
#     prefix=ENV_PROJECT.BASE_API_V1 + "/sales",
#     tags=["Sales"],
# )

# routers.include_router(
#     analytics_endpoints,
#     prefix=ENV_PROJECT.BASE_API_V1 + "/analytics",
#     tags=["Analytics"],
# )
