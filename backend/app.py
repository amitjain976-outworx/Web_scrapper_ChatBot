import sys
import asyncio

# =========================
# WINDOWS PLAYWRIGHT FIX
# =========================
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.database import engine, Base
from db import models

# Routers
from auth.routes import router as auth_router
from api.admin import router as admin_router
from api.customer import router as customer_router


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        version="1.0.0",
    )

    # =========================
    # CORS
    # =========================
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # =========================
    # ROUTERS
    # =========================
    app.include_router(auth_router, prefix="/auth", tags=["Auth"])
    app.include_router(admin_router, tags=["Admin"])
    app.include_router(customer_router, tags=["Customer"])

    return app


app = create_app()


# =========================
# STARTUP EVENT
# =========================

@app.on_event("startup")
async def on_startup():
    # Create DB tables (async-safe)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure screenshot base path exists
    settings.SCREENSHOT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)


# =========================
# HEALTH CHECK
# =========================

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "env": settings.ENV,
    }
