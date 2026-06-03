import asyncio
import json
import os

from aiokafka import AIOKafkaProducer
from telegram_service import TelegramFetchService

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC = "raw_messages"


async def run():
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = int(os.environ["DEFAULT_TELEGRAM_CHAT_ID"])
    service = TelegramFetchService(token=token)
    interval_s = int(os.getenv("TELEGRAM_AUTO_SCAN_INTERVAL_S", "15"))

    try:
        while True:
            messages = await service.fetch_recent_messages(chat_id, limit=100)
            for msg in messages:
                if not msg.text:
                    continue
                payload = {
                    "post_id": f"tg:{msg.chat_id}:{msg.message_id}",
                    "chat_id": msg.chat_id,
                    "message_id": msg.message_id,
                    "text": msg.text,
                    "sender_id": msg.sender_id,
                    "first_name": msg.first_name,
                    "username": msg.username,
                    "created_utc": msg.created_utc,
                    "timestamp_iso": msg.timestamp_iso,
                }
                await producer.send_and_wait(TOPIC, value=payload)
            await asyncio.sleep(interval_s)
    finally:
        await service.shutdown()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
