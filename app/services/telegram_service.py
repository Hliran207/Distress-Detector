"""
Telegram Bot API client for draining the `getUpdates` queue.

Uses `python-telegram-bot` (async). A single `TelegramFetchService` instance
is shared for the app lifetime so `offset` advances correctly across manual
scans and the background auto-scan loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from telegram import Bot, Message
from telegram.error import TelegramError


class TelegramFetchError(Exception):
    """Raised when Telegram Bot API calls fail."""


@dataclass(frozen=True)
class TelegramMessage:
    chat_id: int
    message_id: int
    text: Optional[str]
    sender_id: Optional[int]
    first_name: Optional[str]
    username: Optional[str]
    created_utc: float
    timestamp_iso: str


def _message_datetime(msg: Message) -> datetime:
    """Normalize `Message.date` (unix int in raw API, datetime in python-telegram-bot)."""
    raw = msg.date
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    return datetime.fromtimestamp(float(raw), tz=timezone.utc)


def _message_to_telegram_message(msg: Message) -> Optional[TelegramMessage]:
    if msg.chat is None:
        return None

    text = msg.text or msg.caption
    user = msg.from_user
    created = _message_datetime(msg)

    return TelegramMessage(
        chat_id=msg.chat.id,
        message_id=msg.message_id,
        text=text,
        sender_id=user.id if user is not None else None,
        first_name=user.first_name if user is not None else None,
        username=user.username if user is not None else None,
        created_utc=created.timestamp(),
        timestamp_iso=created.isoformat(),
    )


class TelegramFetchService:
    def __init__(self, token: str):
        self._bot = Bot(token=token)
        self._offset: Optional[int] = None

    async def fetch_recent_messages(
        self,
        chat_id: int,
        *,
        limit: int = 100,
    ) -> list[TelegramMessage]:
        """
        Drain pending updates, acknowledge them, and return messages for `chat_id`.

        Only updates not yet acknowledged (`offset`) are returned by Telegram.
        Messages from other chats are still acknowledged so the queue does not stall.
        """
        try:
            updates = await self._bot.get_updates(
                offset=self._offset,
                limit=100,
                timeout=10,
                allowed_updates=["message", "channel_post"],
            )
        except TelegramError as exc:
            raise TelegramFetchError(str(exc)) from exc

        if not updates:
            return []

        matched: list[TelegramMessage] = []
        for update in updates:
            msg = update.message or update.channel_post
            if msg is None or msg.chat is None or msg.chat.id != chat_id:
                continue
            parsed = _message_to_telegram_message(msg)
            if parsed is not None:
                matched.append(parsed)
            if len(matched) >= limit:
                break

        # Acknowledge only after parsing so a failed scan can retry the same batch.
        self._offset = updates[-1].update_id + 1

        return matched

    async def shutdown(self) -> None:
        await self._bot.shutdown()
