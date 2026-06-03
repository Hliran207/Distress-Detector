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
