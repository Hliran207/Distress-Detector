import os
import joblib
import numpy as np
import torch
from transformers import (
    DistilBertForSequenceClassification,
    DistilBertTokenizerFast,
)

from app.ml.preprocess import preprocess
from app.ml.escalation import should_escalate

HF_REPO = os.getenv("HF_REPO", "Hliran2/distilbert-distress-detector")


class DistressEnsemble:
    """
    Dual-model ensemble with dual-trigger escalation.

    Fast path  : TF-IDF + Logistic Regression (every request)
    Slow path  : DistilBERT (only when a trigger fires)

    Weights    : 35% fast model + 65% transformer
    Triggers   : uncertainty band | negation cues | random audit (10%)
    """

    def __init__(
        self,
        weights: tuple[float, float] = (0.35, 0.65),
        uncertainty_band: float = 0.25,
        audit_rate: float = 0.10,
        distress_threshold: float = 0.45,
    ):
        self.weights = weights
        self.uncertainty_band = uncertainty_band
        self.audit_rate = audit_rate
        self.distress_threshold = distress_threshold
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

    # ── Internal inference ────────────────────────────────────────────────────

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

    # ── Public predict ────────────────────────────────────────────────────────

    def predict(self, raw_text: str) -> dict:
        """
        Full ensemble prediction for a single post.

        Returns a dict with:
            label               : 'distress' | 'not_distress'
            confidence          : final probability score (0–1)
            escalated           : whether transformer was invoked
            escalation_reason   : 'uncertainty' | 'negation' | 'audit' | 'none'
            p_fast              : TF-IDF probability
            p_transformer       : DistilBERT probability (null if not escalated)
        """
        # Step 1 — preprocess for TF-IDF
        text_clean = preprocess(raw_text)

        # Step 2 — fast model
        p_fast = self._predict_tfidf(text_clean)

        # Step 3 — check escalation triggers
        escalate, reason = should_escalate(
            raw_text,
            p_fast,
            self.uncertainty_band,
            self.audit_rate,
        )

        # Step 4 — transformer if triggered
        if escalate:
            p_bert = self._predict_bert(raw_text)
            w1, w2 = self.weights
            p_final = w1 * p_fast + w2 * p_bert
        else:
            p_bert = None
            p_final = p_fast

        return {
            "label": (
                "distress" if p_final >= self.distress_threshold else "not_distress"
            ),
            "confidence": round(p_final, 4),
            "escalated": escalate,
            "escalation_reason": reason,
            "p_fast": round(p_fast, 4),
            "p_transformer": round(p_bert, 4) if p_bert is not None else None,
        }
