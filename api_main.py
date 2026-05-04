import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.config import DB_NAME, TELEGRAM_COLLECTION_NAME, load_mongo_uri
from app.api.routers.posts import router as posts_router
from app.api.routers.stats import router as stats_router
from app.api.routers.predict import router as predict_router
from app.controllers.telegram_auto_scan import telegram_auto_scan_loop
from app.ml.ensemble import DistressEnsemble
from app.services.telegram_service import TelegramFetchService


logger = logging.getLogger("api_main")


_TRUTHY = {"1", "true", "yes", "on"}


def _parse_chat_id(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("DEFAULT_TELEGRAM_CHAT_ID=%r is not a valid integer; auto-scan disabled", raw)
        return None


def _parse_positive_int(raw: Optional[str], default: int, name: str) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r is not a valid integer; using default %s", name, raw, default)
        return default
    if value <= 0:
        logger.warning("%s=%s must be positive; using default %s", name, value, default)
        return default
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongo_uri = load_mongo_uri()
    client = AsyncIOMotorClient(mongo_uri)
    app.state.mongo_client = client

    # Telegram messages live in their own collection; ensure the dedup index
    # exists so re-scanning the same updates does not produce duplicates.
    await client[DB_NAME][TELEGRAM_COLLECTION_NAME].create_index(
        "post_id", unique=True
    )

    # ── ML Ensemble ───────────────────────────────────────────────────────────
    # Loads both models from HuggingFace Hub on first startup
    # Subsequent startups use the cached volume — instant load
    ensemble = DistressEnsemble()
    ensemble.load()
    app.state.ensemble = ensemble

    # ── Telegram (shared, lifespan-owned) ─────────────────────────────────────
    # A single Bot connector and a shared lock so the manual scan endpoint and
    # the background auto-scan loop never call `getUpdates` at the same time
    # (Telegram allows only one consumer per token).
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_service: Optional[TelegramFetchService] = None
    if token:
        telegram_service = TelegramFetchService(token=token)
    else:
        logger.warning("TELEGRAM_BOT_TOKEN is not set; Telegram features disabled")

    app.state.telegram_service = telegram_service
    app.state.telegram_lock = asyncio.Lock()
    app.state.telegram_auto_task = None

    auto_enabled_raw = os.getenv("TELEGRAM_AUTO_SCAN_ENABLED", "true").strip().lower()
    auto_enabled = auto_enabled_raw in _TRUTHY
    chat_id = _parse_chat_id(os.getenv("DEFAULT_TELEGRAM_CHAT_ID"))
    interval_s = _parse_positive_int(
        os.getenv("TELEGRAM_AUTO_SCAN_INTERVAL_S"), 60, "TELEGRAM_AUTO_SCAN_INTERVAL_S"
    )
    auto_limit = _parse_positive_int(
        os.getenv("TELEGRAM_AUTO_SCAN_LIMIT"), 100, "TELEGRAM_AUTO_SCAN_LIMIT"
    )

    if auto_enabled and chat_id is not None and telegram_service is not None:
        app.state.telegram_auto_task = asyncio.create_task(
            telegram_auto_scan_loop(app, chat_id, interval_s=interval_s, limit=auto_limit),
            name="telegram-auto-scan",
        )
    else:
        if not auto_enabled:
            logger.info("Telegram auto-scan disabled via TELEGRAM_AUTO_SCAN_ENABLED")
        elif chat_id is None:
            logger.info("Telegram auto-scan disabled: DEFAULT_TELEGRAM_CHAT_ID not set")
        else:
            logger.info("Telegram auto-scan disabled: TELEGRAM_BOT_TOKEN not set")

    try:
        yield
    finally:
        task: Optional[asyncio.Task] = app.state.telegram_auto_task
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        if telegram_service is not None:
            await telegram_service.shutdown()

        client.close()


app = FastAPI(title="Reddit Distress Detection API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(posts_router)
app.include_router(stats_router)
app.include_router(predict_router)
