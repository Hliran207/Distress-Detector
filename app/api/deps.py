from typing import AsyncIterator

from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.api.config import COLLECTION_NAME, DB_NAME


def get_mongo_client(request: Request) -> AsyncIOMotorClient:
    return request.app.state.mongo_client


def get_posts_collection(request: Request) -> AsyncIOMotorCollection:
    client = get_mongo_client(request)
    return client[DB_NAME][COLLECTION_NAME]

