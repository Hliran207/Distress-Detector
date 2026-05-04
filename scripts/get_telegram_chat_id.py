"""
Temporary helper: print chat_id of the most recent message update for this bot.

Usage (from repo root):
    python scripts/get_telegram_chat_id.py

Requires TELEGRAM_BOT_TOKEN in .env. Send any message in the group while the
script waits if the update queue is empty (Bot API only delivers new activity).

This script does not advance `offset`, so it does not consume/delete updates.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN is missing from .env", file=sys.stderr)
        sys.exit(1)

    bot = Bot(token=token)
    try:
        print("Polling for updates (up to 45s). Send a message in the group if needed…")
        updates = await bot.get_updates(
            limit=100,
            timeout=45,
            allowed_updates=["message", "channel_post"],
        )
    except TelegramError as e:
        print(f"Telegram error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await bot.shutdown()

    last_chat_id = None
    last_title = None
    last_type = None
    last_text_preview = None

    for u in updates:
        msg = u.message or u.channel_post
        if msg is None or msg.chat is None:
            continue
        last_chat_id = msg.chat.id
        last_title = msg.chat.title
        last_type = msg.chat.type
        text = msg.text or msg.caption
        last_text_preview = (text or "")[:80]

    if last_chat_id is None:
        print(
            "No message updates received. Add the bot to the group, make sure it can read "
            "messages, then run again and post something while this script is waiting.",
            file=sys.stderr,
        )
        sys.exit(2)

    print()
    print("chat_id:", last_chat_id)
    if last_title:
        print("title:  ", last_title)
    print("type:   ", last_type)
    if last_text_preview:
        print("preview:", repr(last_text_preview))


if __name__ == "__main__":
    asyncio.run(main())
