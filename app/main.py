import time

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import ORJSONResponse
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger

from app.Config import ENV_PROJECT
from app.core.app_configure import (
    configure_database,
    configure_logging,
    configure_middleware,
)
from app.database import mongodb
from app.http_exception import http_error_handler
from app.routes.api.routers import routers
from app.schema.health import Health_Schema
from app.utils.uptime import getUptime
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

start_time = time.time()

IS_PROD = ENV_PROJECT.ENV == "production"

app = FastAPI(
    title=ENV_PROJECT.APP_TITILE,
    description=ENV_PROJECT.APP_DESCRIPTION,
    version="v" + ENV_PROJECT.APP_VERSION,
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)

scheduler = BackgroundScheduler()

configs = [
    configure_database,
    configure_logging,
    configure_middleware,
]


# def call_api():
#     response = requests.get("https://vyapar-drishti-previews.onrender.com/health")
#     print(f"API called: {response}")

# # Schedule the job (e.g., every 5 minutes)
# scheduler.add_job(call_api, 'cron', minute='*/5', )
# scheduler.start()

@app.get(
    "/health",
    response_class=ORJSONResponse,
    response_model=Health_Schema,
    status_code=status.HTTP_200_OK,
    tags=["Health Route"],
)


async def check_health(request: Request, response: Response):
    """
    Health Route : Returns App details.

    """
    try:
        await mongodb.client.admin.command("ping")
        database_connected = True
    except:
        database_connected = False
    return Health_Schema(
        success=True,
        status=status.HTTP_200_OK,
        app=ENV_PROJECT.APP_TITILE,
        version=ENV_PROJECT.APP_VERSION,
        ip_address=request.client.host,
        mode=ENV_PROJECT.ENV,
        uptime=getUptime(start_time),
        database_connected=database_connected,
    )


for app_configure in configs:
    app_configure(app)


app.include_router(routers)
app.add_exception_handler(HTTPException, http_error_handler)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "error": str(exc)},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "message": f"{exc.errors()[0]['msg']} : {', '.join(err['loc'][1] for err in exc.errors())}",
        },
    )
