from fastapi import HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from config import COLLECTION_NAME, TELEGRAM_COLLECTION_NAME, get_db_name
from ml.ensemble import DistressEnsemble


def get_mongo_client(request: Request) -> AsyncIOMotorClient:
    return request.app.state.mongo_client


def get_posts_collection(request: Request) -> AsyncIOMotorCollection:
    client = get_mongo_client(request)
    return client[get_db_name()][COLLECTION_NAME]


def get_telegram_collection(request: Request) -> AsyncIOMotorCollection:
    client = get_mongo_client(request)
    return client[get_db_name()][TELEGRAM_COLLECTION_NAME]


def get_ensemble(request: Request) -> DistressEnsemble:
    ensemble = request.app.state.ensemble
    if ensemble is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    return ensemble
