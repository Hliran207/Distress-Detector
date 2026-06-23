import os
import joblib
import torch
from transformers import (
    DistilBertForSequenceClassification,
    DistilBertTokenizerFast,
)

from ml.escalation import should_escalate
from ml.preprocess import preprocess

HF_REPO = os.getenv("HF_REPO", "Hliran2/distilbert-distress-detector")


class DistressEnsemble:
    """
    Two-stage distress classification.

    Stage 1 — Fast (TF-IDF + Logistic Regression): every request.
              If p(distress) < fast_escalation_threshold (default 50%), return
              immediately as low distress using the fast score only.

    Stage 2 — Transformer (DistilBERT): only when the fast score is at or above
              the threshold. The transformer probability is the final confidence
              (no blending), reducing false positives on mild negative language.
    """

    def __init__(
        self,
        weights: tuple[float, float] = (0.35, 0.65),
        uncertainty_band: float = 0.25,
        audit_rate: float = 0.10,
        distress_threshold: float = 0.45,
        fast_escalation_threshold: float = 0.5,
    ):
        # Legacy kwargs (weights, uncertainty_band, audit_rate) kept for compatibility.
        self.weights = weights
        self.uncertainty_band = uncertainty_band
        self.audit_rate = audit_rate
        self.distress_threshold = distress_threshold
        self.fast_escalation_threshold = fast_escalation_threshold
        self.device = torch.device("cpu")

        self._tfidf_model = None
        self._bert_model = None
        self._bert_tokenizer = None

    def load(self) -> None:
        """
        Load both models from HuggingFace Hub.
        Called once at FastAPI startup via lifespan.
        Models are cached in HF_HOME volume — subsequent startups are instant.
        """
        print(f"Loading TF-IDF model from HuggingFace: {HF_REPO}")
        from huggingface_hub import hf_hub_download

        pkl_path = hf_hub_download(
            repo_id=HF_REPO,
            filename="tfidf_logreg.pkl",
            repo_type="model",
        )
        self._tfidf_model = joblib.load(pkl_path)
        print("✓ TF-IDF model loaded")

        print(f"Loading DistilBERT from HuggingFace: {HF_REPO}")
        self._bert_tokenizer = DistilBertTokenizerFast.from_pretrained(HF_REPO)
        self._bert_model = DistilBertForSequenceClassification.from_pretrained(HF_REPO)
        self._bert_model.eval()
        self._bert_model.to(self.device)
        print("✓ DistilBERT loaded")

    def _predict_tfidf(self, text_clean: str) -> float:
        """Run TF-IDF pipeline on preprocessed text. Returns p(distress)."""
        return float(self._tfidf_model.predict_proba([text_clean])[0][1])

    def _predict_bert(self, raw_text: str) -> float:
        """Run DistilBERT on raw text. Returns p(distress)."""
        inputs = self._bert_tokenizer(
            raw_text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=256,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = self._bert_model(**inputs).logits
        return float(torch.softmax(logits, dim=1)[0][1])

    def predict(self, raw_text: str) -> dict:
        """
        Two-stage prediction for a single post.

        Returns a dict with:
            label               : 'distress' | 'not_distress'
            confidence          : final probability score (0–1)
            method              : 'fast' | 'transformer' (which model set confidence)
            escalated           : whether transformer was invoked
            escalation_reason   : 'fast_threshold' | 'none'
            p_fast              : TF-IDF probability
            p_transformer       : DistilBERT probability (null if not escalated)
        """
        text_clean = preprocess(raw_text)
        p_fast = self._predict_tfidf(text_clean)

        escalate, reason = should_escalate(p_fast, self.fast_escalation_threshold)

        if not escalate:
            return {
                "label": "not_distress",
                "confidence": round(p_fast, 4),
                "method": "fast",
                "escalated": False,
                "escalation_reason": reason,
                "p_fast": round(p_fast, 4),
                "p_transformer": None,
            }

        p_bert = self._predict_bert(raw_text)
        return {
            "label": (
                "distress" if p_bert >= self.distress_threshold else "not_distress"
            ),
            "confidence": round(p_bert, 4),
            "method": "transformer",
            "escalated": True,
            "escalation_reason": reason,
            "p_fast": round(p_fast, 4),
            "p_transformer": round(p_bert, 4),
        }
