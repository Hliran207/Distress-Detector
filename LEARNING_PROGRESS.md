# LEARNING_PROGRESS — Distress Detector (Salesforce Archive interview prep)

**Mode:** Understanding only. No code fixes. Issues go to `ISSUES.md` (one line each).

---

## Status

| Stage | Name | Status |
|-------|------|--------|
| 0 | Big picture + Phase 1 traces | Done |
| 1 | Core ML | In progress — `escalation.py` (awaiting your quiz answers) |
| 2 | Offline corpus (`app/`) | Not started |
| 3 | Kafka pipeline | Not started |
| 4 | API | Not started |
| 5 | Ops | Not started |
| 6 | Frontend (brief) | Not started |
| Later | Fix / refactor pass + mock interview | After learning |

**Current step:** Stage 1 file 4 — `services/api/ml/` layout (explain back + quiz)

---

## Stage 1 — Core ML

### Goal

Explain how a raw string becomes a distress / not_distress decision: cleaning, lemmatization, fast TF-IDF score, escalation gate, DistilBERT, and how the same logic is packaged under `services/api/ml/`. Describe responsibilities of each module without looking at the code.

### Concept primer (read before the files)

| Concept | Why you need it here |
|---------|----------------------|
| Pure functions vs stateful classes | `escalation` / `preprocess` are mostly functions; `DistressEnsemble` holds loaded models |
| Separation of concerns / modules | Why escalate / preprocess / ensemble are separate files |
| Cascade (two-stage) classifiers | Fast filter then expensive model |
| Probability thresholds | `fast_escalation_threshold` vs `distress_threshold` |
| Encapsulation (`_private` methods) | `_predict_tfidf`, `_predict_bert` |
| Composition over inheritance | Ensemble *calls* preprocess + should_escalate; does not subclass them |

*(Full primer text is delivered in chat before the first file.)*

### Files

| # | File | Why this order |
|---|------|----------------|
| 1 | `services/model/escalation.py` | Smallest leaf: only the escalate yes/no decision |
| 2 | `services/preprocessing/preprocess.py` | Text pipeline leaf (same content as model/api copies) |
| 3 | `services/model/ensemble.py` | Wires preprocess + escalation + two models |
| 4 | `services/api/ml/` (`__init__`, `escalation`, `preprocess`, `ensemble`) | How the API packages the same ML stack |

### Checkpoint (answer out loud before Stage 2)

1. What does `should_escalate` return, and when does the transformer run?
2. What does `preprocess` do to a string, step by step?
3. Walk through `DistressEnsemble.predict` for a high `p_fast` and a low `p_fast`.
4. Why do both the model service and the API carry an `ensemble` / `ml` package?

---

## Stage 2 — Offline corpus (`app/`)

### Goal

Explain the layered architecture (config → models → services → repositories → controllers → views), name each class’s responsibility, and describe how the Repository pattern isolates MongoDB from scrape/collect logic. Be ready for OOP / inheritance / composition questions.

### Concept primer (before files)

| Concept | Why |
|---------|-----|
| Dataclasses | Domain models (`Post`, configs) |
| Layered architecture | Controllers orchestrate; they don’t talk to Chrome/HTTP details directly |
| Repository pattern | Persist/query behind a collection-shaped API |
| Factory | e.g. Chrome driver creation |
| Composition | Controller holds repo + parser + driver factory |
| Sync PyMongo vs async Motor | Offline scripts vs API (contrast later) |

### Files

| # | File | Why |
|---|------|-----|
| 1 | `app/mongo_config.py` | Env/config leaf |
| 2 | `app/models/post.py`, `app/models/pullpush.py` | Domain types |
| 3 | `app/services/chrome_driver.py` | Driver factory |
| 4 | `app/services/shreddit_parser.py` | DOM → `Post` |
| 5 | `app/services/pullpush_client.py` | HTTP client |
| 6 | `app/repositories/mongo_connection.py` | Sync collection helper |
| 7 | `app/repositories/mongo_posts.py` | Sync repository (main pattern example) |
| 8 | `app/repositories/posts_repository.py` | Async Motor twin (contrast) |
| 9 | `app/controllers/reddit_scraper_controller.py` | Orchestration + Selenium loop |
| 10 | `app/controllers/pullpush_final_stretch_controller.py` | Bulk PullPush orchestration |
| 11 | `app/views/scraper_view.py`, `cli_progress.py` | CLI “view” layer |

### Checkpoint

1. What belongs in a repository vs a controller vs a service in this project?
2. How does `MongoPostsRepository` hide Mongo details from the scraper?
3. Trace one Reddit post from Selenium element to `insert_one`.
4. Where is composition used instead of inheritance in `app/`?

---

## Stage 3 — Kafka pipeline

### Goal

Trace a Telegram message through producers, topics, consumer groups, and the model service write path. Explain offset/ack behavior in the Telegram fetcher and why services are separate processes.

### Concept primer (before files)

| Concept | Why |
|---------|-----|
| async/await + event loop | All four `main.py` loops |
| Kafka topics, producers, consumers | Message bus |
| Consumer groups + offsets | `preprocessing-group`, `model-group` |
| At-least-once / idempotency | Unique `post_id` index |
| JSON serialize/deserialize | Kafka value codecs |

### Files

| # | File | Why |
|---|------|-----|
| 1 | `services/telegram-bot/telegram_service.py` | Fetch + offset + domain dataclass |
| 2 | `services/telegram-bot/main.py` | Producer to `raw_messages` |
| 3 | `services/preprocessing/main.py` | Consume → transform → `clean_messages` |
| 4 | `services/model/main.py` | Consume → predict → Mongo + `results` |

### Checkpoint

1. Name the three topics and which service produces/consumes each.
2. How does `TelegramFetchService` avoid re-processing the same Telegram updates forever?
3. What does the model service write to Mongo vs Kafka?
4. Why is preprocessing a separate service from the model service?

---

## Stage 4 — API

### Goal

Explain FastAPI lifespan, dependency injection, Pydantic schemas, BSON serialization, and how routers read Mongo or call the ensemble. Connect WebSocket broadcast to the `results` topic.

### Concept primer (before files)

| Concept | Why |
|---------|-----|
| Pydantic models | Request/response contracts |
| FastAPI `Depends` | Inject collection / ensemble |
| Lifespan / startup-shutdown | Mongo + model + Kafka consumer task |
| WebSockets | Live results fan-out |
| CORS | Frontend on another origin |

### Files

| # | File | Why |
|---|------|-----|
| 1 | `services/api/config.py` | Env + collection names |
| 2 | `services/api/schemas.py` | API contracts |
| 3 | `services/api/serialization.py` | Mongo doc → JSON-safe dict |
| 4 | `services/api/deps.py` | DI helpers |
| 5 | `services/api/routers/posts.py` | Posts + telegram list |
| 6 | `services/api/routers/stats.py` | Aggregations |
| 7 | `services/api/routers/predict.py` | Sync predict path |
| 8 | `services/api/main.py` | App wiring + WS |

### Checkpoint

1. Where is the ensemble stored, and how does a route get it?
2. Difference between `posts` and `telegram_messages` collections in the API.
3. What does the lifespan start and stop?
4. How does a Kafka `results` message reach a browser tab?

---

## Stage 5 — Ops

### Goal

Explain how Compose wires Zookeeper/Kafka/Mongo/services, what each Dockerfile copies and runs, and how dependencies differ per service.

### Concept primer (before files)

| Concept | Why |
|---------|-----|
| Docker layers + caching | `COPY requirements` before code |
| Multi-stage builds | Frontend Node → nginx |
| Compose services, depends_on, healthchecks | Startup order |
| Env vars / secrets | Tokens, `MONGO_URI`, `HF_REPO` |
| Volumes | `mongo_data`, `hf_cache` |

### Files

| # | File | Why |
|---|------|-----|
| 1 | `services/telegram-bot/Dockerfile` | Simplest service image |
| 2 | `services/preprocessing/Dockerfile` | Same pattern |
| 3 | `services/model/Dockerfile` | Includes `app/ml` shim — understand, don’t fix yet |
| 4 | `services/api/Dockerfile` | Uvicorn entry |
| 5 | `frontend/Dockerfile` | Multi-stage |
| 6 | `docker-compose.yml` | Full topology |
| 7 | `requirements*.txt` + each `services/*/requirements.txt` | Dep graphs |

### Checkpoint

1. Which services depend on Kafka healthy? On Mongo healthy?
2. What does the model Dockerfile do with `app/ml`?
3. Why share an `hf_cache` volume between api and model?
4. How would you start only infra + API for a UI demo?

---

## Stage 6 — Frontend (brief)

### Goal

Explain how the SPA calls REST and WebSocket, and which pages use which endpoints. Light OOP; focus on data flow.

### Concept primer (before files)

| Concept | Why |
|---------|-----|
| SPA + API base URL | `VITE_API_BASE_URL` |
| `fetch` + typed responses | `api.ts` |
| WebSocket client lifecycle | Telegram live updates |
| React state / effects (high level) | Load vs live merge |

### Files

| # | File | Why |
|---|------|-----|
| 1 | `frontend/src/lib/api.ts` | Client surface |
| 2 | `frontend/src/pages/DetectPage.tsx` | `/predict` path |
| 3 | `frontend/src/pages/TelegramPage.tsx` | List + WS path |

### Checkpoint

1. Which function hits `/predict/`?
2. How does TelegramPage merge a WS message into the list?
3. What still references the removed scan endpoint?

---

## Files covered (deep dive)

| File | Stage | Done? |
|------|-------|-------|
| `services/model/escalation.py` | 1 | Done |
| `services/preprocessing/preprocess.py` | 1 | Done |
| `services/model/ensemble.py` | 1 | Done (quiz skipped by user) |
| `services/api/ml/` | 1 | Walkthrough done; quiz pending |

---

## Key concepts retained from Phase 0/1

- Dual architecture: offline `app/` corpus vs online Kafka `services/`
- Topics: `raw_messages` → `clean_messages` → `results`
- Two inference paths: model service vs API `/predict`
- Model Docker `app/ml` shim works in container; design smell logged in `ISSUES.md`
- **Shared package:** ML lives in `packages/distress_ml` (`distress_ml`); services import from there (branch `refactor/shared-ml-package`)


---

## Questions I struggled with

- `escalation.py` Q2: knew caller decides threshold, but did not name `DistressEnsemble.fast_escalation_threshold` on first try.
- `escalation.py`: skipped part A (own-words purpose) on first reply.
- `preprocess.py`: strong overall; lemmatize description missed stopword/`len>=3` filtering (POS role slightly imprecise).
- `ensemble.py`: quiz skipped — review answer key in chat before interview.

---

## Session log

- **2026-10-05:** Phase 0 map + Phase 1 traces; Dockerfile `app/ml` correction.
- **2026-10-05:** Reorganized into Stages 1–6; created `ISSUES.md`; understanding-first rules; Stage 1 primer next.
- **2026-10-05:** Stage 1 file 1 — `services/model/escalation.py` walkthrough; waiting on user explanation + quiz.
- **2026-10-05:** User quiz on `escalation.py`: Q1 solid; Q2/Q3 correct in substance; filled gaps (attribute name, DistilBERT runs on True).
- **2026-10-05:** Stage 1 file 2 — `services/preprocessing/preprocess.py` walkthrough; quiz pending.
- **2026-10-05:** User quiz on `preprocess.py`: solid; clarified lemmatize filters + POS maps for WordNet (not “adds state to output”).
- **2026-10-05:** Stage 1 file 3 — `services/model/ensemble.py` walkthrough; quiz pending.
- **2026-10-05:** User skipped `ensemble.py` quiz; started `services/api/ml/` layout.
- **2026-10-05:** Refactor `refactor/shared-ml-package`: extracted `packages/distress_ml`, removed triplicated ML modules, root Docker build context; baseline `/predict` identical; ISSUES #3–5 marked resolved.
- **2026-10-05:** Pre-merge verification (raw): predict baseline IDENTICAL after EOF normalize; preprocessing has no torch; no-cache transferring context 236B / 1.04kB / 3.41kB / 1.85kB; image sizes api 1.58GB, model 1.53GB, preprocessing 280MB vs main-tagged `distress-preprocessing:before` 277MB (+~3MB); MONGO_URI from `.env` → Atlas (local mongo unused); `**/*.egg-info` added to `.dockerignore` but `/opt/distress_ml/distress_ml.egg-info` still appears after pip install (logged ISSUES #16).
