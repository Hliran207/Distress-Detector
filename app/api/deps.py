from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.api.config import COLLECTION_NAME, DB_NAME, TELEGRAM_COLLECTION_NAME
from app.controllers.telegram_monitor import TelegramMonitorController
from app.ml.ensemble import DistressEnsemble
from app.repositories.posts_repository import PostsRepository
from app.services.telegram_service import TelegramFetchService


def get_mongo_client(request: Request) -> AsyncIOMotorClient:
    return request.app.state.mongo_client


def get_posts_collection(request: Request) -> AsyncIOMotorCollection:
    client = get_mongo_client(request)
    return client[DB_NAME][COLLECTION_NAME]


def get_posts_repository(
    collection: AsyncIOMotorCollection = Depends(get_posts_collection),
) -> PostsRepository:
    return PostsRepository(collection)


def get_telegram_collection(request: Request) -> AsyncIOMotorCollection:
    client = get_mongo_client(request)
    return client[DB_NAME][TELEGRAM_COLLECTION_NAME]


def get_telegram_repository(
    collection: AsyncIOMotorCollection = Depends(get_telegram_collection),
) -> PostsRepository:
    return PostsRepository(collection)


def get_distress_ensemble(request: Request) -> DistressEnsemble:
    ensemble = getattr(request.app.state, "ensemble", None)
    if ensemble is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    return ensemble


def get_telegram_fetch_service(request: Request) -> TelegramFetchService:
    """
    Return the lifespan-owned TelegramFetchService.

    The service is created once at startup (see `api_main.lifespan`) and shared
    by every consumer — request handlers and the background auto-scan loop —
    so they can serialize access to Telegram's `getUpdates` queue via
    `request.app.state.telegram_lock`.
    """
    service = getattr(request.app.state, "telegram_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="TELEGRAM_BOT_TOKEN is not configured on the server",
        )
    return service


def get_telegram_monitor_controller(
    telegram_service: TelegramFetchService = Depends(get_telegram_fetch_service),
    telegram_repository: PostsRepository = Depends(get_telegram_repository),
    ensemble: DistressEnsemble = Depends(get_distress_ensemble),
) -> TelegramMonitorController:
    return TelegramMonitorController(
        telegram_service=telegram_service,
        repository=telegram_repository,
        ensemble=ensemble,
    )
