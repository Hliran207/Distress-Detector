from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from config import load_mongo_uri
from ml.ensemble import DistressEnsemble
from routers.posts import router as posts_router
from routers.predict import router as predict_router
from routers.stats import router as stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(load_mongo_uri())
    app.state.mongo_client = client

    ensemble = DistressEnsemble()
    ensemble.load()
    app.state.ensemble = ensemble

    try:
        yield
    finally:
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
