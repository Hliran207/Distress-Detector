from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from app.mongo_config import load_mongo_uri
from app.api.routers.posts import router as posts_router
from app.api.routers.stats import router as stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_uri = load_mongo_uri()
    client = AsyncIOMotorClient(mongo_uri)
    app.state.mongo_client = client
    try:
        yield
    finally:
        client.close()


app = FastAPI(title="Reddit Distress Detection API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(posts_router)
app.include_router(stats_router)

