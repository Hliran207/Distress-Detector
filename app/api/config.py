"""API-facing re-exports for Mongo settings (see `app.mongo_config`)."""

from app.mongo_config import COLLECTION_NAME, DB_NAME, load_mongo_uri

__all__ = ["COLLECTION_NAME", "DB_NAME", "load_mongo_uri"]
