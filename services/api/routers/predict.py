from fastapi import APIRouter, Depends

from deps import get_ensemble
from ml.ensemble import DistressEnsemble
from schemas import PredictBatchRequest, PredictBatchResponse, PredictRequest, PredictResponse

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("/", response_model=PredictResponse)
async def predict_single(
    body: PredictRequest,
    ensemble: DistressEnsemble = Depends(get_ensemble),
) -> PredictResponse:
    """
    Classify a single post as distress or not_distress.
    Two-stage pipeline: fast model first; transformer only if fast score >= 50%.
    """
    return ensemble.predict(body.text)


@router.post("/batch", response_model=PredictBatchResponse)
async def predict_batch(
    body: PredictBatchRequest,
    ensemble: DistressEnsemble = Depends(get_ensemble),
) -> PredictBatchResponse:
    """Classify a batch of posts (max 32)."""
    results = [ensemble.predict(text) for text in body.texts]
    return PredictBatchResponse(results=results, total=len(results))


@router.get("/health")
async def predict_health(ensemble: DistressEnsemble = Depends(get_ensemble)) -> dict:
    """Check whether the ensemble model is loaded and ready."""
    loaded = ensemble._tfidf_model is not None
    return {
        "status": "ready" if loaded else "loading",
        "models": {
            "tfidf": "loaded" if loaded else "not_loaded",
            "distilbert": "loaded" if loaded else "not_loaded",
        },
    }
