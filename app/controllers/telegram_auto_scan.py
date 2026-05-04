"""
Background Telegram auto-scan loop.

Started from `api_main.lifespan` when `DEFAULT_TELEGRAM_CHAT_ID` is configured.
Each tick acquires `app.state.telegram_lock` so the manual scan endpoint and
the loop never call Telegram's `getUpdates` concurrently (the Bot API allows
only one consumer per token).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.api.config import DB_NAME, TELEGRAM_COLLECTION_NAME
from app.controllers.telegram_monitor import TelegramMonitorController
from app.repositories.posts_repository import PostsRepository
from app.services.telegram_service import TelegramFetchError

if TYPE_CHECKING:
    from fastapi import FastAPI


logger = logging.getLogger("telegram.auto_scan")


async def telegram_auto_scan_loop(
    app: "FastAPI",
    chat_id: int,
    *,
    interval_s: int,
    limit: int,
) -> None:
    """Run `TelegramMonitorController.scan_chat` in a loop until cancelled."""
    logger.info(
        "Starting Telegram auto-scan loop chat_id=%s interval=%ss limit=%s",
        chat_id,
        interval_s,
        limit,
    )

    while True:
        try:
            async with app.state.telegram_lock:
                controller = TelegramMonitorController(
                    telegram_service=app.state.telegram_service,
                    repository=PostsRepository(
                        app.state.mongo_client[DB_NAME][TELEGRAM_COLLECTION_NAME]
                    ),
                    ensemble=app.state.ensemble,
                )
                summary = await controller.scan_chat(chat_id, limit=limit)

            logger.info(
                "auto-scan chat=%s fetched=%d inserted=%d duplicates=%d empty=%d",
                chat_id,
                summary.fetched,
                summary.inserted,
                summary.skipped_duplicates,
                summary.skipped_empty,
            )
        except asyncio.CancelledError:
            logger.info("Telegram auto-scan loop cancelled; exiting")
            raise
        except TelegramFetchError as exc:
            logger.warning("Telegram fetch failed: %s", exc)
        except Exception:
            logger.exception("Unexpected error in Telegram auto-scan tick")

        try:
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            logger.info("Telegram auto-scan loop cancelled while sleeping; exiting")
            raise
