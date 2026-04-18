from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/predict", tags=["predict"])


# ── Request / Response schemas ────────────────────────────────────────────────


class PredictRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Raw post text to classify",
        examples=["I feel so alone and hopeless, nothing seems to get better"],
    )


class PredictResponse(BaseModel):
    label: str
    confidence: float
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


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/", response_model=PredictResponse)
async def predict_single(request: Request, body: PredictRequest):
    """
    Classify a single post as distress or not_distress.
    Runs the full dual-trigger ensemble pipeline.
    """
    ensemble = request.app.state.ensemble
    if ensemble is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    return ensemble.predict(body.text)


@router.post("/batch", response_model=PredictBatchResponse)
async def predict_batch(request: Request, body: PredictBatchRequest):
    """
    Classify a batch of posts (max 32).
    Each post runs through the full ensemble independently.
    """
    ensemble = request.app.state.ensemble
    if ensemble is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    results = [ensemble.predict(text) for text in body.texts]
    return {"results": results, "total": len(results)}


@router.get("/health")
async def predict_health(request: Request):
    """Check whether the ensemble model is loaded and ready."""
    ensemble = request.app.state.ensemble
    loaded = ensemble is not None and ensemble._tfidf_model is not None
    return {
        "status": "ready" if loaded else "loading",
        "models": {
            "tfidf": "loaded" if loaded else "not_loaded",
            "distilbert": "loaded" if loaded else "not_loaded",
        },
    }
