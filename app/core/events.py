from typing import Callable
import asyncio
from fastapi import FastAPI
from loguru import logger
import sys
from playwright.async_api import async_playwright
from app.database import mongodb
import app.core.services as browser_module

def create_start_app_handler(app: FastAPI) -> Callable:  # type: ignore

    @logger.catch
    async def start_app() -> None:
        try:
            if sys.platform.startswith("win"):
                loop = asyncio.ProactorEventLoop()
                asyncio.set_event_loop(loop)
            # global shared_browser
            playwright = await async_playwright().start()
            browser_module.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-dev-shm-usage",
                    # "--use-gl=swiftshader",  # keep only if needed
                ],
            )
            if browser_module.browser is None:
                raise RuntimeError("Browser failed to launch")
            elif browser_module.browser.is_connected() is False:
                raise RuntimeError("Browser is not connected")
            elif browser_module.browser is not None and browser_module.browser.is_connected() is True:
                logger.info("Browser Launched")

            await mongodb.client.admin.command("ping")
            logger.info("MongoDB Connected.")
        except Exception as e:
            print("Error during startup:", e)
            logger.error("Error during startup:", e)
            raise e

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:  # type: ignore

    @logger.catch
    async def stop_app() -> None:
        try:
            if browser_module.browser is not None:
                await browser_module.browser.close()
                logger.info("Browser Closed")
            await mongodb.client.close()
            logger.info("Closed MongoDB Connection")
        except Exception as e:
            print("Error during shutdown:", e)
            logger.error("Error during shutdown:", e)
            raise e

    return stop_app
