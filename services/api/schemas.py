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


class PredictRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Raw post text to classify",
    )


class PredictResponse(BaseModel):
    label: str
    confidence: float
    method: str
    escalated: bool
    escalation_reason: str
    p_fast: float
    p_transformer: float | None


class PredictBatchRequest(BaseModel):
    texts: list[str] = Field(
        ...,
        min_length=1,
        max_length=32,
        description="List of raw post texts (max 32 per batch)",
    )


class PredictBatchResponse(BaseModel):
    results: list[PredictResponse]
    total: int
