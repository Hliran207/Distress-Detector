import asyncio
import json
import os
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from config import load_mongo_uri
from ml.ensemble import DistressEnsemble
from routers.posts import router as posts_router
from routers.predict import router as predict_router
from routers.stats import router as stats_router

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

active_connections: list[WebSocket] = []


async def broadcast_results(consumer: AIOKafkaConsumer) -> None:
    async for msg in consumer:
        payload = json.dumps(msg.value)
        dead: list[WebSocket] = []
        for ws in active_connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in active_connections:
                active_connections.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(load_mongo_uri())
    app.state.mongo_client = client

    ensemble = DistressEnsemble()
    ensemble.load()
    app.state.ensemble = ensemble

    consumer = AIOKafkaConsumer(
        "results",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="api-websocket-group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
    )
    await consumer.start()
    broadcast_task = asyncio.create_task(broadcast_results(consumer))

    try:
        yield
    finally:
        broadcast_task.cancel()
        try:
            await broadcast_task
        except asyncio.CancelledError:
            pass
        await consumer.stop()
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


@app.websocket("/ws/results")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
