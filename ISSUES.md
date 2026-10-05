# ISSUES — logged for review (learning phase + post-refactor)

Format: `path:line — short description`

During **learning**: log only; do not fix unless explicitly in a fix phase.  
**Resolved** items include commit hash on `main`.

---

## Resolved (refactor)

| ID | Item | Resolution |
|----|------|------------|
| R1 | Triplicated `preprocess.py` / `escalation.py` / `ensemble.py` under `services/` | **RESOLVED** `10f9be9` — single `packages/distress_ml/distress_ml/` |
| R2 | `services/model/Dockerfile` `app/ml` copy shim | **RESOLVED** `10f9be9` — `distress_ml` package + consistent imports |
| R3 | Inconsistent import paths (`app.ml` vs `ml` vs flat `ensemble`) | **RESOLVED** `10f9be9` — all `from distress_ml...` |
| R4 | `/opt/distress_ml/distress_ml.egg-info` left in image layer | **RESOLVED** `c7718f2` — `pip install && rm -rf /opt/distress_ml` in same RUN |

---

## Open — documentation & product

1. `README.md` — Describes old monolith (`api_main.py`, `app/api/`); live stack is `docker-compose.yml` + `services/` + `packages/distress_ml/`.
2. `README_MIGRATION.md` vs `services/api/main.py` — Migration plan said API has no ML; API still loads `DistressEnsemble` in lifespan for `/predict`.
3. Escalation **code** (one threshold via `packages/distress_ml/distress_ml/escalation.py`) vs **project documentation** (three triggers, 0.35/0.65 weighting in older narrative / unused constructor params).
4. `services/api/routers/posts.py:77-79` — Docstring still references `POST /posts/scan/telegram`; population is Kafka model pipeline.
5. `frontend/src/lib/api.ts` / `frontend/src/pages/TelegramPage.tsx` — Still calls removed `POST /posts/scan/telegram`.

---

## Open — ML behavior & design (`packages/distress_ml/`)

6. `packages/distress_ml/distress_ml/ensemble.py:28-39` — Legacy unused constructor params: `weights`, `uncertainty_band`, `audit_rate` (stored, not used in `predict()`).
7. `packages/distress_ml/distress_ml/ensemble.py` — **Inconsistent threshold band:** if `0.45 <= p_fast < 0.5`, path returns **`not_distress`** without BERT and without applying `distress_threshold` to fast score.
8. `packages/distress_ml/distress_ml/ensemble.py` — Field named **`confidence`** holds **p(distress)**, not calibrated confidence in the assigned label.
9. `packages/distress_ml/distress_ml/preprocess.py:97` — Token **`"no"`** is in `words_to_keep` but dropped by **`len(token) >= 3`** filter (negation weakened for TF-IDF).
10. `packages/distress_ml/distress_ml/ensemble.py` `load()` — **No HF revision pin** (`HF_REPO` only); reproducibility / drift risk.
11. `packages/distress_ml/distress_ml/ensemble.py` `predict()` — If called before `load()`, failure mode is unclear (NoneType on models).
12. `packages/distress_ml/distress_ml/ensemble.py` — Uses **`print`** for load progress instead of logging.
13. `packages/distress_ml/distress_ml/preprocess.py:7-11` — `nltk.download(...)` at **import time** (cold start / network side effect).
14. `packages/distress_ml/distress_ml/ensemble.py:48-52` — `load()` docstring says “FastAPI startup”; also used by `services/model/main.py`.

---

## Open — pipeline & data contract

15. `services/model/main.py:41` — `ensemble.predict(item["raw_text"])`; Kafka **`clean_text` not used** for inference (NLTK runs again inside ensemble). **Planned fix:** Option B in `LEARNING_PROGRESS.md` (optional `clean_text` param) after Stage 3.
16. `services/model/main.py:67-68` — `except Exception: pass` on Mongo `insert_one` swallows **all** errors, not only `DuplicateKeyError`.
17. `services/api/serialization.py` — **`created_utc` float→int on READ** (fix `055e219`); cleaner contract is **normalize on WRITE** in `services/model/main.py` and/or `services/telegram-bot/main.py` so all docs store int epoch.
18. `docker-compose.yml` + `.env` — Local **`mongo` service runs** but **`MONGO_URI` points to Atlas**; model/api **do not** connect to local mongo; **`depends_on: mongo`** still on model/api.
22. `services/telegram-bot/telegram_service.py` — Telegram update **`offset` kept only in memory** (`self._offset`). After crash/restart: Telegram may re-deliver unacked updates → **at-least-once** from Bot API; duplicates absorbed by unique `post_id` index (Mongo) / consumer-side dedup. Clarify: messages are not silently lost if Telegram still has them; risk is **re-processing**, not permanent drop of still-pending updates.
23. `services/model/main.py` — `insert_one` to Mongo and Kafka `send` to **`results` are not atomic**. Crash between them leaves Mongo and `results` out of sync. End-to-end delivery is **at-least-once** (Kafka consumers + unique `post_id`), **not exactly-once**.

---

## Open — API / runtime

19. `services/api/routers/predict.py:19` — Async route calls blocking `ensemble.predict` (event loop blocked during inference).

---

## Open — offline `app/` config

24. `app/mongo_config.py` vs `services/api/config.py` — Near-duplicate Mongo env helpers (`COLLECTION_NAME`, `TELEGRAM_COLLECTION_NAME`, `load_mongo_uri`, db name); drift risk if one changes.
25. `app/mongo_config.py:6` — `TELEGRAM_COLLECTION_NAME` defined but unused by any `app/` import (only API `config.py` is consumed).
26. `app/repositories/mongo_connection.py:11` — Hardcodes `db["posts"]` instead of `COLLECTION_NAME` from `mongo_config`.
27. `app/services/chrome_driver.py:23-28` — If `user_data_dir` is set, `--headless=new` is never applied even when `config.headless=True` (only a log line); config flag and actual browser mode can disagree.
28. `app/services/shreddit_parser.py:50-53` — Broad `except Exception: return None` hides real parse bugs; only `StaleElementReferenceException` is named.
29. `app/repositories/mongo_connection.py` — `get_posts_collection()` appears unused (no imports); PullPush/`main` wires `MongoClient` inline. Also hardcodes `db["posts"]` vs `COLLECTION_NAME` (see #26).

---

## From learning quizzes (weak spots, not code bugs)

20. Interview prep — Name **`DistressEnsemble.fast_escalation_threshold`** when explaining who sets escalation cutoff.
21. Interview prep — **`ensemble.py` checkpoint** skipped; rehearse high/low `p_fast` paths and soccer homework false-positive story.
