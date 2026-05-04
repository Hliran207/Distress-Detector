"""
Telegram monitoring controller.

Orchestrates the full scan flow:

    Telegram (getUpdates) -> DistressEnsemble.predict -> MongoDB

Designed to be invoked from a FastAPI route via the dependency-injection
pattern in `app.api.deps`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.ml.ensemble import DistressEnsemble
from app.repositories.posts_repository import PostsRepository
from app.services.telegram_service import TelegramFetchService, TelegramMessage


@dataclass
class TelegramScanItem:
    post_id: str
    label: int
    distress_score: float
    preview: str


@dataclass
class TelegramScanSummary:
    chat_id: int
    fetched: int = 0
    processed: int = 0
    inserted: int = 0
    skipped_duplicates: int = 0
    skipped_empty: int = 0
    items: list[TelegramScanItem] = field(default_factory=list)


_PREVIEW_CHARS = 160
_ITEMS_CAP = 50


class TelegramMonitorController:
    """
    Fetches recent Telegram messages, scores each with the distress
    ensemble, and persists the analyzed records into the dedicated
    `telegram_messages` collection (see `app.api.deps.get_telegram_repository`).
    """

    def __init__(
        self,
        telegram_service: TelegramFetchService,
        repository: PostsRepository,
        ensemble: DistressEnsemble,
    ):
        self.telegram_service = telegram_service
        self.repository = repository
        self.ensemble = ensemble

    async def scan_chat(self, chat_id: int, *, limit: int = 100) -> TelegramScanSummary:
        summary = TelegramScanSummary(chat_id=chat_id)

        messages = await self.telegram_service.fetch_recent_messages(
            chat_id, limit=limit
        )
        summary.fetched = len(messages)

        for message in messages:
            text = (message.text or "").strip()
            if not text:
                summary.skipped_empty += 1
                continue

            prediction = self.ensemble.predict(text)
            label = 1 if prediction["label"] == "distress" else 0
            distress_score = float(prediction["confidence"])

            doc = self._build_document(message, text, label, distress_score)
            inserted = await self.repository.insert_raw(doc)
            summary.processed += 1

            if inserted:
                summary.inserted += 1
                if len(summary.items) < _ITEMS_CAP:
                    summary.items.append(
                        TelegramScanItem(
                            post_id=doc["post_id"],
                            label=label,
                            distress_score=distress_score,
                            preview=text[:_PREVIEW_CHARS],
                        )
                    )
            else:
                summary.skipped_duplicates += 1

        return summary

    @staticmethod
    def _build_document(
        message: TelegramMessage,
        text: str,
        label: int,
        distress_score: float,
    ) -> dict:
        post_id = f"tg:{message.chat_id}:{message.message_id}"

        sender_info: dict[str, object] = {}
        if message.sender_id is not None:
            sender_info["sender_id"] = message.sender_id
        if message.first_name:
            sender_info["first_name"] = message.first_name
        if message.username:
            sender_info["username"] = message.username

        return {
            "post_id": post_id,
            "title": None,
            "body": text,
            "subreddit": str(message.chat_id),
            "platform": "telegram",
            "label": label,
            "distress_score": distress_score,
            "created_utc": message.created_utc,
            "timestamp": message.timestamp_iso,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "source": "telegram_scan",
            "sender_info": sender_info,
        }
