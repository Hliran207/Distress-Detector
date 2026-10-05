# ISSUES — logged for review after the learning phase

Format: `file:line — short description`

Do not fix these during the understanding phase. We will triage together later.

---

## From Phase 0 / Phase 1

1. `README.md` — Documents old monolith (`api_main.py`, `app/api/`); live stack is `docker-compose.yml` + `services/`.
2. `README_MIGRATION.md` vs `services/api/main.py` — Migration plan said API has no ML; API still loads `DistressEnsemble` in lifespan for `/predict`.
3. ~~`services/model/Dockerfile` — Build-time `cp` into `app/ml/` so `ensemble.py` can import `app.ml.*`~~ — **RESOLVED** on branch `refactor/shared-ml-package` (shared `packages/distress_ml`, no shim).
4. ~~Triplicated `preprocess.py` across preprocessing / model / api~~ — **RESOLVED** on branch `refactor/shared-ml-package` (single `distress_ml.preprocess`).
5. ~~Duplicate `ensemble.py` / inconsistent `app.ml` vs `ml` imports~~ — **RESOLVED** on branch `refactor/shared-ml-package` (single `distress_ml.ensemble`).
6. `services/model/main.py:41` — Calls `ensemble.predict(item["raw_text"])`; ignores `clean_text` produced by the preprocessing service (NLTK effectively runs again inside ensemble).
7. `services/model/main.py:67-68` — Bare `except Exception: pass` on Mongo `insert_one` (swallows all errors, not only duplicates).
8. `services/api/routers/predict.py:19` — Async route calls blocking `ensemble.predict` (CPU/GPU-bound work on the event loop).
9. `frontend/src/lib/api.ts:145` / `TelegramPage.tsx` — Still calls `POST /posts/scan/telegram`; route removed from `services/api/routers/posts.py`.
10. `services/api/routers/posts.py:77-79` — Docstring still says telegram collection is populated by `POST /posts/scan/telegram` (now Kafka model service).
11. `packages/distress_ml/distress_ml/ensemble.py` (was `services/model/ensemble.py:30-39`) — Constructor accepts `weights=(0.35, 0.65)`, `uncertainty_band`, `audit_rate` but `predict()` does not use them (legacy / docs mismatch with cascade design).
12. Escalation docs vs older project narrative — Runtime gate is only `p_fast >= 0.5` via `should_escalate`; no multi-trigger / blending path in current `predict()`.

---

## From Stage deep-dives

13. `packages/distress_ml/distress_ml/preprocess.py:7-11` (was under services) — `nltk.download(...)` runs at import time (side effect on every process start / cold start).
14. `packages/distress_ml/distress_ml/ensemble.py` `load()` docstring — says “FastAPI startup”; also used by Kafka model service `main.py`.
15. `docker-compose.yml` + `.env` — Compose runs a local `mongo` service, but the configured `MONGO_URI` points to Atlas (`mongodb+srv://…`); model/api do not connect to the local container at runtime.
16. Docker image `/opt/distress_ml/distress_ml.egg-info` — even with `**/*.egg-info` in root `.dockerignore`, `pip install /opt/distress_ml` regenerates egg-info in the copied source tree (not only under site-packages).