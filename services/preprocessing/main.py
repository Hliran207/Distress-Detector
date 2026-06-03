import asyncio
import json
import os

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from preprocess import preprocess

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")


async def run():
    consumer = AIOKafkaConsumer(
        "raw_messages",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="preprocessing-group",
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
            raw = msg.value
            clean_text = preprocess(raw["text"])
            payload = {
                **raw,
                "raw_text": raw["text"],
                "clean_text": clean_text,
            }
            del payload["text"]
            await producer.send_and_wait("clean_messages", value=payload)
    finally:
        await consumer.stop()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
