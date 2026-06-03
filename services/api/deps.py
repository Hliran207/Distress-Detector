from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from config import COLLECTION_NAME, TELEGRAM_COLLECTION_NAME, get_db_name


def get_mongo_client(request: Request) -> AsyncIOMotorClient:
    return request.app.state.mongo_client


def get_posts_collection(request: Request) -> AsyncIOMotorCollection:
    client = get_mongo_client(request)
    return client[get_db_name()][COLLECTION_NAME]


def get_telegram_collection(request: Request) -> AsyncIOMotorCollection:
    client = get_mongo_client(request)
    return client[get_db_name()][TELEGRAM_COLLECTION_NAME]
