import asyncio
import json
import os
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient

from ensemble import DistressEnsemble

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.getenv("MONGO_DB_NAME", "reddit_distress_db")


async def run():
    ensemble = DistressEnsemble()
    ensemble.load()

    mongo = AsyncIOMotorClient(MONGO_URI)
    collection = mongo[DB_NAME]["telegram_messages"]
    await collection.create_index("post_id", unique=True)

    consumer = AIOKafkaConsumer(
        "clean_messages",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="model-group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await consumer.start()
    await producer.start()

    try:
        async for msg in consumer:
            item = msg.value
            prediction = ensemble.predict(item["raw_text"])
            result = {
                **item,
                "label": 1 if prediction["label"] == "distress" else 0,
                "distress_score": prediction["confidence"],
                "confidence": prediction["confidence"],
                "method": prediction["method"],
                "escalated": prediction["escalated"],
                "escalation_reason": prediction["escalation_reason"],
                "p_fast": prediction["p_fast"],
                "p_transformer": prediction["p_transformer"],
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "platform": "telegram",
                "source": "kafka_pipeline",
                "body": item.get("raw_text"),
                "subreddit": str(item.get("chat_id")),
                "timestamp": item.get("timestamp_iso"),
                "sender_info": {
                    "sender_id": item.get("sender_id"),
                    "first_name": item.get("first_name"),
                    "username": item.get("username"),
                },
                "title": item.get("first_name", "Telegram User"),
            }
            try:
                await collection.insert_one({**result})
            except Exception:
                pass
            await producer.send_and_wait("results", value=result)
    finally:
        await consumer.stop()
        await producer.stop()
        mongo.close()


if __name__ == "__main__":
    asyncio.run(run())
