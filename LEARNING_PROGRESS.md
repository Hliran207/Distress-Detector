# LEARNING_PROGRESS — Distress Detector (Salesforce Archive interview prep)

## Context

I'm preparing for a **Salesforce interview (Archive team)**. One part is a **deep code walkthrough** of this project with the hiring manager, focused on **OOP, inheritance, design patterns, and design decisions** — not just “what the code does,” but why it is structured this way and what trade-offs were taken.

---

## Learning rules (follow in every session)

1. **Understanding first, fixes later.** During the learning phase, **never modify application code** (only this file and `ISSUES.md` for bookkeeping).
2. When a bug, design smell, or docs/code mismatch is found: **one line in `ISSUES.md`**, mention briefly in chat, **move on**.
3. **One file per step.** For each file:
   - Purpose → walkthrough (line-by-line for logic, block-by-block for boilerplate)
   - OOP and design → how it connects
   - I explain in my own words + **2–3 quiz questions** with honest feedback
4. Move to the next file **only when I say `"next"`**.
5. Each stage starts with a **concept primer** and ends with a **checkpoint** I answer **out loud** (no peeking at code).

---

## Overall status

| Stage | Name | Status |
|-------|------|--------|
| 0 | Big picture + end-to-end traces (Telegram Kafka + `/predict`) | Done |
| 1 | Core ML (`packages/distress_ml/`) | **All files covered; checkpoint NOT done yet** (skipped for now — rehearse before interview) |
| 2 | Offline corpus (`app/`) | **IN PROGRESS** — concept primer delivered; await `"next"` for file 1 |
| 3 | Kafka pipeline | Not started |
| 4 | API | Not started |
| 5 | Ops | Not started |
| 6 | Frontend (brief) | Not started |
| Later | Planned fixes (Option B, BaseKafkaService) + mock interview | After Stages 1–6 |

**Resume here:** Stage 2 file 7 — `app/repositories/mongo_connection.py` deep dive + quiz, then `"next"`.

---

## Stage 1 — Core ML

### Goal

Explain how raw text becomes a distress / not_distress decision: preprocess → fast TF-IDF → escalation gate → optional DistilBERT; where code lives after the shared-package refactor; how model service and API both use the same package.

### Concept primer (already delivered in prior chat)

Pure functions vs stateful class; cascade vs weighted ensemble; `fast_escalation_threshold` (routing) vs `distress_threshold` (label after BERT); composition over inheritance; encapsulation with `_predict_*`; module-level NLTK side effects.

### Files (paths verified on disk)

| # | File | Why this order | Deep dive |
|---|------|----------------|-----------|
| 1 | `packages/distress_ml/distress_ml/escalation.py` | Leaf: routing only | Done |
| 2 | `packages/distress_ml/distress_ml/preprocess.py` | Text pipeline leaf | Done |
| 3 | `packages/distress_ml/distress_ml/ensemble.py` | Loads models + `predict()` | Done (quiz skipped) |
| 4 | `packages/distress_ml/pyproject.toml` | Package deps + `[inference]` extra | Done (layout) |
| 5 | `packages/distress_ml/distress_ml/__init__.py` | Light package root (no torch) | Done (layout) |
| 6 | *Integration* — imports in `services/model/main.py`, `services/preprocessing/main.py`, `services/api/main.py`, `services/api/deps.py`, `services/api/routers/predict.py` | Who calls `distress_ml` | Done (layout) |

**Removed (do not reference in walkthrough):** `services/api/ml/`, `services/model/{ensemble,escalation,preprocess}.py`, `services/preprocessing/preprocess.py`.

### Checkpoint (NOT done — answer out loud before Stage 2)

1. What does `should_escalate` return, and when does DistilBERT run?
2. What does `preprocess` do step by step (including filters on tokens)?
3. Walk `DistressEnsemble.predict` for high vs low `p_fast` (label, method, thresholds used).
4. Why is ML in `packages/distress_ml` instead of copied into each service?

---

## Stage 2 — Offline corpus (`app/`)

### Goal

Layered architecture: config → models → services → repositories → controllers → views. Repository pattern, composition vs inheritance, sync PyMongo vs async Motor contrast.

### Concept primer (delivered 2026-10-05)

Dataclasses; layered architecture; Repository pattern; Factory (Chrome); composition in controllers; sync vs async data access.

### Files (paths verified)

| # | File | Why | Deep dive |
|---|------|-----|-----------|
| 1 | `app/mongo_config.py` | Config leaf | Done |
| 2 | `app/models/post.py` | Domain `Post` | Done (quiz skipped) |
| 3 | `app/models/pullpush.py` | PullPush types | Done (quiz skipped) |
| 4 | `app/services/chrome_driver.py` | Driver factory | Done (quiz skipped) |
| 5 | `app/services/shreddit_parser.py` | DOM → `Post` | Done (quiz skipped) |
| 6 | `app/services/pullpush_client.py` | HTTP client | Done (quiz skipped) |
| 7 | `app/repositories/mongo_connection.py` | Sync collection helper | In progress |
| 8 | `app/repositories/mongo_posts.py` | Sync repository (main pattern) | |
| 9 | `app/repositories/posts_repository.py` | Motor async twin | |
| 10 | `app/controllers/reddit_scraper_controller.py` | Selenium orchestration | |
| 11 | `app/controllers/pullpush_final_stretch_controller.py` | Bulk PullPush | |
| 12 | `app/views/scraper_view.py` | CLI view | |
| 13 | `app/views/cli_progress.py` | CLI progress | |

### Checkpoint

1. Repository vs controller vs service in this project?
2. How does `MongoPostsRepository` hide Mongo from the scraper?
3. Trace one post: Selenium element → `insert_one`.
4. Where is composition used instead of inheritance in `app/`?

---

## Stage 3 — Kafka pipeline

### Goal

Telegram → topics → consumer groups → model write path; offset ack in `TelegramFetchService`.

### Concept primer

async/await; Kafka topics/producers/consumers/groups/offsets; idempotency via `post_id` index.

### Files (verified)

| # | File | Why |
|---|------|-----|
| 1 | `services/telegram-bot/telegram_service.py` | Fetch + offset + dataclass |
| 2 | `services/telegram-bot/main.py` | Producer `raw_messages` |
| 3 | `services/preprocessing/main.py` | `raw_messages` → `clean_messages` |
| 4 | `services/model/main.py` | predict → Mongo + `results` |

### Checkpoint

1. Three topics and who produces/consumes each?
2. How does `TelegramFetchService` advance offset?
3. Model service: Mongo vs Kafka writes?
4. Why separate preprocessing and model processes?

---

## Stage 4 — API

### Goal

FastAPI lifespan, DI, Pydantic, serialization, routers, WebSocket fan-out from `results`.

### Files (verified)

| # | File | Why |
|---|------|-----|
| 1 | `services/api/config.py` | Env + collection names |
| 2 | `services/api/schemas.py` | Contracts |
| 3 | `services/api/serialization.py` | BSON → JSON-safe |
| 4 | `services/api/deps.py` | DI |
| 5 | `services/api/routers/posts.py` | Posts + `/posts/telegram` |
| 6 | `services/api/routers/stats.py` | Stats |
| 7 | `services/api/routers/predict.py` | `/predict` |
| 8 | `services/api/main.py` | App + WS |

### Checkpoint

1. Where is `DistressEnsemble` stored and injected?
2. `posts` vs `telegram_messages` collections?
3. Lifespan start/stop?
4. Kafka `results` → browser tab?

---

## Stage 5 — Ops

### Goal

Compose topology, Dockerfiles (root context), `.dockerignore`, per-service requirements.

### Files (verified)

| # | File | Why |
|---|------|-----|
| 1 | `services/telegram-bot/Dockerfile` | Unchanged context |
| 2 | `services/preprocessing/Dockerfile` | Root context + `distress_ml` |
| 3 | `services/model/Dockerfile` | Root context + `[inference]` |
| 4 | `services/api/Dockerfile` | Root context + `[inference]` |
| 5 | `frontend/Dockerfile` | Multi-stage nginx |
| 6 | `docker-compose.yml` | Full stack |
| 7 | `packages/distress_ml/pyproject.toml` + `services/*/requirements.txt` | Dependency split |

**Note:** Model Dockerfile no longer uses `app/ml` shim (removed in refactor).

### Checkpoint

1. Which services wait on Kafka / Mongo healthy?
2. How is `distress_ml` installed in images?
3. Why shared `hf_cache` volume?
4. What does root `.dockerignore` exclude to keep context small?

---

## Stage 6 — Frontend (brief)

### Files (verified)

| # | File | Why |
|---|------|-----|
| 1 | `frontend/src/lib/api.ts` | REST + WS URLs |
| 2 | `frontend/src/pages/DetectPage.tsx` | `/predict` |
| 3 | `frontend/src/pages/TelegramPage.tsx` | List + WebSocket |

### Checkpoint

1. Function for `/predict/`?
2. WS merge into list?
3. Dead `scanTelegram` reference?

---

## Key concepts learned — Stage 1

- **Cascade vs ensemble name:** runtime is a **two-stage cascade** (fast then optional BERT), not 0.35/0.65 score blending.
- **Routing threshold vs decision threshold:** `fast_escalation_threshold` (0.5) gates BERT; `distress_threshold` (0.45) labels after BERT; low path always `not_distress` without comparing fast score to 0.45.
- **Pure functions vs stateful class:** `should_escalate` / `preprocess` vs `DistressEnsemble` holding loaded models.
- **Composition over inheritance:** ensemble calls preprocess + escalation; no model subclass tree.
- **Encapsulation:** `_predict_tfidf`, `_predict_bert`; public `load()` + `predict()`.
- **Facade:** `DistressEnsemble` hides HF + sklearn details from Kafka/API callers.
- **Serialization:** TF-IDF pipeline loaded via **joblib** pickle from Hub (`tfidf_logreg.pkl`).
- **HF Hub:** `hf_hub_download` + `from_pretrained(HF_REPO)`; **`HF_HOME` / `hf_cache` volume** for warm starts.
- **Inference mode:** `model.eval()` + `torch.no_grad()` for BERT forward pass.
- **Preprocess:** clean (regex) vs lemmatize (NLTK + POS); BERT uses **raw** text, TF-IDF uses **preprocessed** text.
- **Training–serving skew risk:** Kafka `clean_text` not used by model today; NLTK runs again inside `predict()` (see Option B in Decisions).
- **Stemming vs lemmatization:** project uses **lemmatization** with WordNet POS, not Porter stemmer.

---

## Refactor summary (shared `distress_ml` package)

### What changed

- **Added** `packages/distress_ml/` (single source: `preprocess`, `escalation`, `ensemble`).
- **Deleted** triplicated ML files under `services/model/`, `services/preprocessing/preprocess.py`, and entire `services/api/ml/`.
- **Imports** everywhere: `from distress_ml...` (model, preprocessing, API).
- **Docker:** build `context: .` for preprocessing, model, api; copy package → `pip install` → **`rm -rf /opt/distress_ml`** in same RUN; code only in **site-packages**.
- **Root `.dockerignore`:** excludes `models/`, `notebooks/`, `posts.csv`, `app/`, etc., so context stays **KB not GB**.
- **Bugfix (post-refactor):** `services/api/serialization.py` coerces float `created_utc` → int for `/posts/telegram` (commit `055e219`).

### Why

- One place to change ML logic; no `app/ml` Docker hack; preprocessing image installs package **without** `[inference]` (no torch).

### Evidence (measured)

| Check | Result |
|-------|--------|
| Build context (no-cache) | `#6 236B`, `#7 1.04kB`, `#8 3.41kB`, `#9 1.85kB` (not ~3.5GB) |
| Image sizes | preprocessing **280MB**, model **1.53GB**, api **1.58GB** (old preprocessing on main before refactor: **277MB**) |
| `/predict` vs baseline | **IDENTICAL** (three test strings, `/tmp/baseline_predictions.json`) |
| preprocessing + torch | `ModuleNotFoundError: No module named 'torch'` |
| `/opt/distress_ml` after build | **absent**; imports from `/usr/local/lib/python3.11/site-packages/distress_ml/` |
| Git diff stat (since pre-refactor base `f66ed7b`) | **389 lines deleted, 84 added** (27 files) |

### Commits (on `main`)

| Hash | Message |
|------|---------|
| `10f9be9` | refactor: extract shared distress_ml package, remove triplicated ML code |
| `6221ada` | chore: ignore distress_ml egg-info from editable installs |
| `0a142aa` | chore: ignore egg-info in Docker context; document Atlas mongo finding |
| `c7718f2` | chore: remove /opt/distress_ml after pip install in Docker images |
| `055e219` | fix some problem (`created_utc` float → int in serialization) |

Local dev: `pip install -e "packages/distress_ml[inference]"` from repo root.

---

## Planned decisions (fixes after learning — not done yet)

### Option B — preprocessing service keeps a real role

- **After Stage 3** (and verified with same `/predict` baseline as refactor):
  - Add optional parameter to `predict()` (e.g. precomputed `clean_text`) so **NLTK runs once** in preprocessing service; model passes Kafka `clean_text`.
  - Introduce **`BaseKafkaService`** (Template Method) shared by `services/preprocessing/main.py` and `services/model/main.py` (consumer/producer loop boilerplate).

### Counter-argument (YAGNI)

- If there is only one consumer and one transform, **delete preprocessing service** and call `distress_ml.preprocess` inside model — simpler ops, fewer moving parts.
- **Trade-off to articulate:** Option B = operational separation + horizontal scale of stateless preprocess vs YAGNI = fewer services and less duplicate Kafka plumbing.

---

## Interview talking points collected

1. **Refactor story:** triplication → `packages/distress_ml`, root Docker context, `[inference]` extra, no torch in preprocessing, baseline-identical predictions.
2. **Escalation trade-off:** code has **one trigger** (`p_fast >= 0.5`); docs/old narrative described **three triggers + 0.35/0.65 blending** — system recall **capped by fast model recall** on the no-escalate path.
3. **Soccer/homework example:** `p_fast ≈ 0.62` escalates; DistilBERT raised to **~0.93 distress** — interview example of **false positive** on casual negative text (model behavior, not a code bug).
4. **Pickle security:** joblib/sklearn pickle from Hub — trust repo, pin revision, supply-chain awareness.
5. **Model version pinning:** `HF_REPO` without pinned revision — reproducibility risk.
6. **"no" dropped:** `words_to_keep` includes `"no"` but `len(token) >= 3` filter removes it — negation handling gap for TF-IDF path.

---

## Architecture reminder (Phase 0)

- **Online:** `telegram-bot` → `raw_messages` → `preprocessing` → `clean_messages` → `model` → Mongo `telegram_messages` + `results` → `api` (REST + `/ws/results`) → `frontend`.
- **Direct detect:** `DetectPage` → `POST /predict/` → API in-process `DistressEnsemble` (no Kafka).
- **Offline:** `app/` collectors → Mongo `posts` (training corpus; not in Kafka path).

---

## Questions I struggled with

- `escalation.py`: caller owns threshold — name `fast_escalation_threshold`; skipped own-words once.
- `preprocess.py`: missed `len>=3` filter vs `words_to_keep`; POS maps for lemmatizer not “added to output string”.
- `ensemble.py`: quiz skipped — review checkpoint Q3 and soccer/homework threshold band before interview.

---

## Session log

- **2026-10-05:** Phase 0 map; Phase 1 traces; Stages 1–6 plan; Stage 1 files 1–3 deep dive.
- **2026-10-05:** Refactor + verification on `main`; Telegram 500 fix (`055e219`).
- **2026-10-05:** Handoff doc update for new Cursor chat (this file + `ISSUES.md`).
- **2026-10-05:** Stage 2 concept primer delivered; Stage 1 checkpoint deferred.

---

## How to resume in a new chat

1. Read **`LEARNING_PROGRESS.md`** (this file) and **`ISSUES.md`** in full.
2. Confirm branch/state: ML lives under **`packages/distress_ml/distress_ml/`**; **`services/api/ml/` does not exist**.
3. Stage 2: say **`next`** for current Stage 2 file (see status table). Rehearse Stage 1 checkpoint before interview.
4. During learning: **no code changes**; log smells in **`ISSUES.md`** only.
