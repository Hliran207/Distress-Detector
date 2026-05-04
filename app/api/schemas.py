from typing import Optional

from pydantic import BaseModel, Field


class TelegramSenderInfo(BaseModel):
    sender_id: Optional[int] = None
    first_name: Optional[str] = None
    username: Optional[str] = None


class RedditPost(BaseModel):
    post_id: str
    title: Optional[str] = None
    body: Optional[str] = None
    subreddit: Optional[str] = None
    label: Optional[int] = Field(default=None, ge=0, le=1)
    created_utc: Optional[int] = None
    timestamp: Optional[str] = None
    platform: Optional[str] = None
    distress_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    sender_info: Optional[TelegramSenderInfo] = None


class PostsListResponse(BaseModel):
    total: int
    items: list[RedditPost]


class StatsResponse(BaseModel):
    total_records: int
    counts_by_label: dict[str, int]
    posts_per_subreddit: dict[str, int]


class TelegramScanRequest(BaseModel):
    chat_id: int = Field(..., description="Telegram chat id to scan")
    limit: int = Field(default=50, ge=1, le=500)


class TelegramScanItemModel(BaseModel):
    post_id: str
    label: int = Field(..., ge=0, le=1)
    distress_score: float = Field(..., ge=0.0, le=1.0)
    preview: str


class TelegramScanResponse(BaseModel):
    chat_id: int
    fetched: int
    processed: int
    inserted: int
    skipped_duplicates: int
    skipped_empty: int
    items: list[TelegramScanItemModel]
