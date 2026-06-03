# Kafka Microservices Migration Plan

## 1. Current Architecture Summary

The project is a **single-process monolith** built with FastAPI that does four things
simultaneously inside one Docker container:

| Responsibility | Where it lives today |
|---|---|
| Telegram polling (`getUpdates` every 15 s) | `app/controllers/telegram_auto_scan.py` — an `asyncio.Task` launched inside the FastAPI lifespan |
| Text preprocessing (NLTK clean + lemmatize) | `app/ml/preprocess.py` — called inline, synchronously, inside the request/task handler |
| ML inference (TF-IDF → DistilBERT two-stage) | `app/ml/ensemble.py` — models loaded into memory at startup, held in `app.state.ensemble` |
| REST API (read posts, stats, direct predict) | `app/api/routers/` — three routers served by the same Uvicorn process |

**Frontend** (React + Vite, served via Nginx) polls the backend REST API every 10 s
and also exposes a manual "Scan Now" button that calls `POST /posts/scan/telegram`.

**Infrastructure** (current `docker-compose.yml`):
```
mongo:7  ←─  backend (FastAPI + ML models + Telegram bot)  ←─  frontend (Nginx)
```

### Problems this creates
- The 700 MB+ ML models load in the same process as the HTTP server — slow cold start.
- Telegram polling and HTTP handlers share a single asyncio Lock because Telegram's
  Bot API allows only one `getUpdates` consumer per token.
- Preprocessing, inference, and API serving cannot be scaled independently.
- A crash in the background scan task can affect unrelated API routes.
- Adding a second message source (e.g. Reddit live stream) requires touching the monolith.

---

## 2. Target Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                       DISTRESS DETECTOR — MICROSERVICES                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  [Telegram Bot API]                                                          ║
║         │                                                                    ║
║         ▼  getUpdates (HTTP long-poll)                                       ║
║  ┌──────────────────────┐                                                    ║
║  │  telegram-bot        │  Polls every 15 s; one consumer per token.        ║
║  │  service             │  Publishes raw message JSON.                       ║
║  └──────────┬───────────┘                                                    ║
║             │                                                                ║
║             │  Kafka topic: raw_messages                                     ║
║             ▼                                                                ║
║  ┌──────────────────────┐                                                    ║
║  │  preprocessing       │  Cleans text, strips URLs/markdown, lemmatizes.   ║
║  │  service             │  Stateless; scale horizontally (consumer group).  ║
║  └──────────┬───────────┘                                                    ║
║             │                                                                ║
║             │  Kafka topic: clean_messages                                   ║
║             ▼                                                                ║
║  ┌──────────────────────┐                                                    ║
║  │  model               │  Two-stage inference: TF-IDF fast → DistilBERT.  ║
║  │  service             │  Writes result to MongoDB AND produces to Kafka.  ║
║  └──────────┬───────────┘                                                    ║
║             │                                                                ║
║             │  Kafka topic: results                                          ║
║             │                                                                ║
║             ▼  (also written directly to MongoDB)                            ║
║  ┌──────────────────────┐                                                    ║
║  │  api                 │  Read-only REST (posts, stats, health).           ║
║  │  service             │  No ML models loaded. Direct MongoDB reads.       ║
║  └──────────┬───────────┘                                                    ║
║             │  HTTP polling every 10 s                                       ║
║             ▼                                                                ║
║  ┌──────────────────────┐                                                    ║
║  │  frontend            │  React dashboard — no change needed to behavior.  ║
║  │  (Nginx)             │                                                    ║
║  └──────────────────────┘                                                    ║
║                                                                              ║
║  ┌───────────────────────────────────────┐                                   ║
║  │  Infrastructure                       │                                   ║
║  │  • Zookeeper                          │                                   ║
║  │  • Kafka broker                       │                                   ║
║  │  • MongoDB 7                          │                                   ║
║  └───────────────────────────────────────┘                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 3. Kafka Topics — Payload Contracts

### `raw_messages`
Produced by: `telegram-bot-service`
Consumed by: `preprocessing-service`

```json
{
  "post_id":       "tg:-1001234567890:42",
  "chat_id":       -1001234567890,
  "message_id":    42,
  "text":          "I feel completely hopeless and alone tonight",
  "sender_id":     987654321,
  "first_name":    "Alice",
  "username":      "alice_t",
  "created_utc":   1717430000.0,
  "timestamp_iso": "2024-06-03T18:13:20+00:00"
}
```

### `clean_messages`
Produced by: `preprocessing-service`
Consumed by: `model-service`

```json
{
  "post_id":       "tg:-1001234567890:42",
  "chat_id":       -1001234567890,
  "raw_text":      "I feel completely hopeless and alone tonight",
  "clean_text":    "feel hopeless alone tonight",
  "sender_id":     987654321,
  "first_name":    "Alice",
  "username":      "alice_t",
  "created_utc":   1717430000.0,
  "timestamp_iso": "2024-06-03T18:13:20+00:00"
}
```

### `results`
Produced by: `model-service`
Consumed by: optional downstream consumers (alerting, audit log, etc.)
Also written directly to MongoDB `telegram_messages` collection.

```json
{
  "post_id":            "tg:-1001234567890:42",
  "chat_id":            -1001234567890,
  "raw_text":           "I feel completely hopeless and alone tonight",
  "label":              "distress",
  "confidence":         0.8731,
  "method":             "transformer",
  "escalated":          true,
  "escalation_reason":  "fast_threshold",
  "p_fast":             0.6123,
  "p_transformer":      0.8731,
  "distress_score":     0.8731,
  "sender_id":          987654321,
  "first_name":         "Alice",
  "username":           "alice_t",
  "created_utc":        1717430000.0,
  "timestamp_iso":      "2024-06-03T18:13:20+00:00",
  "processed_at":       "2024-06-03T18:13:21.045+00:00"
}
```

---

## 4. New Folder Structure

```
Distress-Detector/
│
├── services/                         ← NEW: one sub-folder per microservice
│   │
│   ├── telegram-bot/
│   │   ├── Dockerfile
│   │   ├── requirements.txt          # python-telegram-bot, aiokafka, python-dotenv
│   │   └── main.py                   # Poll loop + AIOKafkaProducer → raw_messages
│   │
│   ├── preprocessing/
│   │   ├── Dockerfile
│   │   ├── requirements.txt          # aiokafka, nltk, python-dotenv
│   │   ├── preprocess.py             # Moved from app/ml/preprocess.py (unchanged)
│   │   └── main.py                   # AIOKafkaConsumer(raw_messages) → AIOKafkaProducer(clean_messages)
│   │
│   ├── model/
│   │   ├── Dockerfile
│   │   ├── requirements.txt          # aiokafka, torch, transformers, scikit-learn, motor, ...
│   │   ├── ensemble.py               # Moved from app/ml/ensemble.py (unchanged)
│   │   ├── escalation.py             # Moved from app/ml/escalation.py (unchanged)
│   │   └── main.py                   # AIOKafkaConsumer(clean_messages) → inference → MongoDB + AIOKafkaProducer(results)
│   │
│   └── api/
│       ├── Dockerfile
│       ├── requirements.txt          # fastapi, uvicorn, motor, pydantic, python-dotenv
│       ├── main.py                   # Slim FastAPI — no ML, no Telegram, read-only
│       └── routers/
│           ├── posts.py              # GET /posts, GET /posts/telegram, GET /posts/search
│           └── stats.py              # GET /stats/summary
│
├── docker-compose.yml                ← REPLACE with the new version (see Section 7)
│
├── app/                              ← KEEP during migration; delete after cutover
├── api_main.py                       ← KEEP during migration; delete after cutover
├── frontend/                         ← NO CHANGES NEEDED
└── README_MIGRATION.md               ← This file
```

---

## 5. Step-by-Step Migration Plan

### Phase 0 — Understand the current state (done)
- [x] Read all source files.
- [x] Document current coupling points: shared Lock, `app.state`, in-process ML load.

---

### Phase 1 — Add Kafka to Docker Compose (infrastructure only)

**Goal**: get a working Kafka broker alongside the existing services. Nothing changes
in the application code yet. This lets you verify connectivity before writing producers
and consumers.

**What to do**:
1. Add `zookeeper` and `kafka` services to `docker-compose.yml` (see Section 7).
2. Define the three topics in Kafka startup config or via a one-time init container.
3. Start the stack and confirm Kafka is reachable:
   ```
   docker compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
   ```

**No application code changes in this phase.**

---

### Phase 2 — Create `telegram-bot-service`

**Goal**: extract Telegram polling out of the monolith into a dedicated process that
writes raw messages to the `raw_messages` Kafka topic.

**Files to create**: `services/telegram-bot/main.py`, `Dockerfile`, `requirements.txt`

**Key changes to existing code**:
- `app/services/telegram_service.py` is copied verbatim to
  `services/telegram-bot/telegram_service.py`. No logic changes.
- `app/controllers/telegram_auto_scan.py` becomes the scan loop in `main.py`
  but instead of calling `TelegramMonitorController.scan_chat`, it calls
  `producer.send_and_wait("raw_messages", value=raw_message_dict)`.
- Remove the `TelegramFetchService` and background task from `api_main.py` after
  this service is confirmed working.

**aiokafka producer pattern**:
```python
# services/telegram-bot/main.py
import asyncio, json, os
from aiokafka import AIOKafkaProducer
from telegram_service import TelegramFetchService

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TOPIC = "raw_messages"

async def run():
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = int(os.environ["DEFAULT_TELEGRAM_CHAT_ID"])
    service = TelegramFetchService(token=token)
    interval_s = int(os.getenv("TELEGRAM_AUTO_SCAN_INTERVAL_S", "15"))

    try:
        while True:
            messages = await service.fetch_recent_messages(chat_id, limit=100)
            for msg in messages:
                if not msg.text:
                    continue
                payload = {
                    "post_id":       f"tg:{msg.chat_id}:{msg.message_id}",
                    "chat_id":       msg.chat_id,
                    "message_id":    msg.message_id,
                    "text":          msg.text,
                    "sender_id":     msg.sender_id,
                    "first_name":    msg.first_name,
                    "username":      msg.username,
                    "created_utc":   msg.created_utc,
                    "timestamp_iso": msg.timestamp_iso,
                }
                await producer.send_and_wait(TOPIC, value=payload)
            await asyncio.sleep(interval_s)
    finally:
        await service.shutdown()
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(run())
```

**What moves out of `api_main.py`**:
- Delete the `TelegramFetchService` init block inside `lifespan`.
- Delete `telegram_auto_scan_loop` task creation.
- Delete `app.state.telegram_lock`, `app.state.telegram_service`, `app.state.telegram_auto_task`.
- Remove `POST /posts/scan/telegram` endpoint (no longer needed — auto-scan is always on
  in the new service).

---

### Phase 3 — Create `preprocessing-service`

**Goal**: consume `raw_messages`, apply the existing NLTK pipeline, and produce to
`clean_messages`. This is a stateless transformation — it holds no models in memory.

**Files to create**: `services/preprocessing/main.py`, `preprocess.py` (copy), `Dockerfile`, `requirements.txt`

**Key changes to existing code**:
- `app/ml/preprocess.py` is copied verbatim to `services/preprocessing/preprocess.py`.
  No logic changes — the function signature `preprocess(text: str) -> str` stays identical.

**aiokafka consumer + producer pattern**:
```python
# services/preprocessing/main.py
import asyncio, json, os
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from preprocess import preprocess

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

async def run():
    consumer = AIOKafkaConsumer(
        "raw_messages",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="preprocessing-group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await consumer.start()
    await producer.start()

    try:
        async for msg in consumer:
            raw = msg.value
            clean_text = preprocess(raw["text"])
            payload = {
                **raw,
                "raw_text":   raw["text"],
                "clean_text": clean_text,
            }
            del payload["text"]   # rename field to raw_text / clean_text
            await producer.send_and_wait("clean_messages", value=payload)
    finally:
        await consumer.stop()
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(run())
```

**Why a separate service for preprocessing**:
- NLTK downloads (~50 MB) and the `averaged_perceptron_tagger` model do not need to
  coexist with the 700 MB DistilBERT weights.
- The preprocessing container can be scaled to many replicas sharing a single consumer
  group — Kafka handles partition-level fan-out automatically.
- If the tokenizer or stopword list changes, only this container needs to be redeployed.

---

### Phase 4 — Create `model-service`

**Goal**: consume `clean_messages`, run the two-stage ensemble, write the result to
MongoDB, and produce it to `results`.

**Files to create**: `services/model/main.py`, `ensemble.py`, `escalation.py`, `Dockerfile`, `requirements.txt`

**Key changes to existing code**:
- `app/ml/ensemble.py` and `app/ml/escalation.py` are copied verbatim. No logic
  changes — `DistressEnsemble.predict(raw_text)` stays the same public API.
- The model is loaded once at startup (before entering the consume loop), not inside a
  FastAPI lifespan.
- The consumer runs the two-stage predict on the `raw_text` field (not `clean_text` —
  DistilBERT needs unprocessed text; TF-IDF uses `clean_text`). You will need to expose
  both to the ensemble. The simplest fix is to add a `predict_with_clean` method that
  accepts both the raw and preprocessed text directly, avoiding double-preprocessing.

**aiokafka consumer + MongoDB writer + producer pattern**:
```python
# services/model/main.py
import asyncio, json, os
from datetime import datetime, timezone
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient
from ensemble import DistressEnsemble

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.getenv("MONGO_DB_NAME", "reddit_distress_db")

async def run():
    # Load ML models before entering the loop
    ensemble = DistressEnsemble()
    ensemble.load()

    mongo = AsyncIOMotorClient(MONGO_URI)
    collection = mongo[DB_NAME]["telegram_messages"]
    await collection.create_index("post_id", unique=True)

    consumer = AIOKafkaConsumer(
        "clean_messages",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="model-group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await consumer.start()
    await producer.start()

    try:
        async for msg in consumer:
            item = msg.value
            prediction = ensemble.predict(item["raw_text"])  # raw text for BERT
            result = {
                **item,
                "label":             1 if prediction["label"] == "distress" else 0,
                "distress_score":    prediction["confidence"],
                "confidence":        prediction["confidence"],
                "method":            prediction["method"],
                "escalated":         prediction["escalated"],
                "escalation_reason": prediction["escalation_reason"],
                "p_fast":            prediction["p_fast"],
                "p_transformer":     prediction["p_transformer"],
                "processed_at":      datetime.now(timezone.utc).isoformat(),
                "platform":          "telegram",
                "source":            "kafka_pipeline",
            }
            # Write to MongoDB (idempotent — duplicate post_id silently ignored)
            try:
                await collection.insert_one({**result})
            except Exception:
                pass  # DuplicateKeyError means already processed
            # Produce to results topic for downstream consumers
            await producer.send_and_wait("results", value=result)
    finally:
        await consumer.stop()
        await producer.stop()
        mongo.close()

if __name__ == "__main__":
    asyncio.run(run())
```

**What moves out of `api_main.py`**:
- Delete `DistressEnsemble()` loading from `lifespan`.
- Delete `app.state.ensemble`.
- Remove `POST /predict` and `POST /predict/batch` endpoints from the API service
  (or keep them in a separate lightweight predict service that loads only the models).

---

### Phase 5 — Slim Down `api-service`

**Goal**: the API service becomes a pure read-only REST gateway — no ML, no Telegram,
no background tasks. It reads from MongoDB (already populated by `model-service`) and
serves the frontend.

**Files to create**: `services/api/main.py`, `routers/posts.py`, `routers/stats.py`, `Dockerfile`, `requirements.txt`

**What stays (unchanged)**:
- `GET /posts` — list Reddit posts
- `GET /posts/telegram` — list analyzed Telegram messages
- `GET /posts/search` — full-text search
- `GET /posts/{post_id}` — single post
- `GET /stats/summary` — label counts, subreddit breakdown

**What gets removed**:
- `POST /posts/scan/telegram` — no longer needed; telegram-bot-service polls continuously.
- `POST /predict` and `POST /predict/batch` — can be a separate `predict-api` service
  that loads only the ensemble and exposes a synchronous HTTP endpoint (no Kafka), or
  dropped if the UI's Detect page is not needed.

**Why FastAPI is still used** (not WebSocket or SSE from Kafka):
The frontend already polls `/posts/telegram` every 10 s. No frontend change is needed.
If real-time push is desired in the future, add a WebSocket endpoint to the API service
that subscribes to the `results` Kafka topic and forwards each message to connected
browser clients.

---

### Phase 6 — Frontend (no code changes needed)

The React frontend continues to call the same REST endpoints on the API service. The
only runtime change is that the Docker Compose `VITE_API_BASE_URL` environment variable
points to the new `api-service` container. The `TelegramPage` polling behavior, the
`DetectPage` predict call, and all other pages remain unchanged.

If real-time streaming is desired later, add a `useEffect` with an `EventSource` or
`WebSocket` connection to a new `/ws/results` endpoint on the api-service.

---

### Phase 7 — Remove the Monolith

Once all five new services are running and confirmed stable:
1. Remove `api_main.py`, `app/controllers/telegram_auto_scan.py`,
   `app/controllers/telegram_monitor.py`, `app/services/telegram_service.py`.
2. Remove the old `backend` service from `docker-compose.yml`.
3. Remove `docker/backend.Dockerfile`.

---

## 6. Libraries Needed

### All Python services
| Library | Version | Purpose |
|---|---|---|
| `aiokafka` | `>=0.11` | Async Kafka producer/consumer |
| `python-dotenv` | `>=1.0` | Load `.env` at startup |

### `telegram-bot-service`
| Library | Version | Purpose |
|---|---|---|
| `python-telegram-bot` | `21.6` | `Bot.get_updates()` — already in project |

### `preprocessing-service`
| Library | Version | Purpose |
|---|---|---|
| `nltk` | `3.8.1` | Tokenization, POS tagging, lemmatization — already in project |

### `model-service`
| Library | Version | Purpose |
|---|---|---|
| `torch` (CPU) | `2.6.0+cpu` | DistilBERT inference — already in project |
| `transformers` | `4.41.0` | DistilBertForSequenceClassification — already in project |
| `scikit-learn` | `1.6.1` | TF-IDF + LogisticRegression pipeline — already in project |
| `joblib` | `1.4.2` | Load `.pkl` model file — already in project |
| `huggingface_hub` | `0.23.0` | Download models from HF Hub — already in project |
| `motor` | `3.6.0` | Async MongoDB writes — already in project |
| `nltk` | `3.8.1` | Preprocessing reused here for TF-IDF input — already in project |

### `api-service`
| Library | Version | Purpose |
|---|---|---|
| `fastapi` | `0.115.0` | REST framework — already in project |
| `uvicorn[standard]` | `0.30.6` | ASGI server — already in project |
| `motor` | `3.6.0` | Async MongoDB reads — already in project |
| `pydantic` | `2.9.2` | Request/response schemas — already in project |

### Infrastructure (Docker images)
| Image | Purpose |
|---|---|
| `confluentinc/cp-zookeeper:7.6.0` | Kafka coordination |
| `confluentinc/cp-kafka:7.6.0` | Message broker |
| `mongo:7` | Persistent storage (unchanged) |

---

## 7. New Docker Compose Structure

The full `docker-compose.yml` should be replaced with the following structure.
Comments explain which parts are new.

```yaml
# docker-compose.yml  (target — post-migration)

services:

  # ── Infrastructure ────────────────────────────────────────────────────────

  zookeeper:                                  # NEW
    image: confluentinc/cp-zookeeper:7.6.0
    restart: unless-stopped
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  kafka:                                      # NEW
    image: confluentinc/cp-kafka:7.6.0
    restart: unless-stopped
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      # Pre-create the three pipeline topics with sensible retention
      KAFKA_CREATE_TOPICS: >
        raw_messages:1:1,
        clean_messages:1:1,
        results:1:1
    healthcheck:
      test: ["CMD", "kafka-topics", "--bootstrap-server", "localhost:9092", "--list"]
      interval: 10s
      timeout: 10s
      retries: 5
      start_period: 30s

  mongo:                                      # UNCHANGED
    image: mongo:7
    restart: unless-stopped
    volumes:
      - mongo_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--quiet", "--eval", "db.adminCommand('ping').ok"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

  # ── Application services ──────────────────────────────────────────────────

  telegram-bot:                               # NEW (replaces monolith's auto-scan task)
    build:
      context: ./services/telegram-bot
    restart: unless-stopped
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      DEFAULT_TELEGRAM_CHAT_ID: ${DEFAULT_TELEGRAM_CHAT_ID}
      TELEGRAM_AUTO_SCAN_INTERVAL_S: ${TELEGRAM_AUTO_SCAN_INTERVAL_S:-15}
    depends_on:
      kafka:
        condition: service_healthy

  preprocessing:                              # NEW
    build:
      context: ./services/preprocessing
    restart: unless-stopped
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    depends_on:
      kafka:
        condition: service_healthy

  model:                                      # NEW (replaces monolith's ML + Mongo writer)
    build:
      context: ./services/model
    restart: unless-stopped
    environment:
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      MONGO_URI: ${MONGO_URI:-mongodb://mongo:27017/reddit_distress_db}
      MONGO_DB_NAME: ${MONGO_DB_NAME:-reddit_distress_db}
      HF_REPO: ${HF_REPO:-Hliran2/distilbert-distress-detector}
      HF_HOME: /home/app/.cache/huggingface
    volumes:
      - hf_cache:/home/app/.cache/huggingface
    depends_on:
      kafka:
        condition: service_healthy
      mongo:
        condition: service_healthy

  api:                                        # REPLACEMENT for monolith backend
    build:
      context: ./services/api
    restart: unless-stopped
    ports:
      - "8001:8000"
    environment:
      MONGO_URI: ${MONGO_URI:-mongodb://mongo:27017/reddit_distress_db}
      MONGO_DB_NAME: ${MONGO_DB_NAME:-reddit_distress_db}
    depends_on:
      mongo:
        condition: service_healthy

  frontend:                                   # UNCHANGED
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_API_BASE_URL: ${VITE_API_BASE_URL:-http://localhost:8001}
    restart: unless-stopped
    ports:
      - "3000:80"
    depends_on:
      - api

volumes:
  mongo_data:
  hf_cache:
```

---

## 8. How aiokafka Fits with FastAPI

Each new Python microservice follows one of two patterns:

### Pattern A — Pure loop (no HTTP server)
`telegram-bot`, `preprocessing`, and `model` services have no HTTP endpoints. They are
standalone Python scripts with an `asyncio.run(main())` entry point. FastAPI is **not**
used here. The loop runs forever and crashes (and Docker restarts it) if Kafka is
unreachable.

```
asyncio event loop
  └── while True / async for msg in consumer
        ├── process message
        └── produce to next topic
```

### Pattern B — FastAPI with background consumer (optional for api-service)
If the `api-service` ever needs to subscribe to the `results` topic (e.g. to push
results to connected browsers via WebSocket), add a background consumer task in the
FastAPI lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer = AIOKafkaConsumer("results", bootstrap_servers=KAFKA_BOOTSTRAP, ...)
    await consumer.start()
    task = asyncio.create_task(forward_to_websockets(consumer, app))
    yield
    task.cancel()
    await consumer.stop()
```

This mirrors how `telegram_auto_scan_loop` was wired into the existing `api_main.py`
lifespan, but is now isolated to the api-service only.

---

## 9. Migration Phases at a Glance

| Phase | What changes | Risk | Rollback |
|---|---|---|---|
| 0 | Read & document | None | N/A |
| 1 | Add Kafka/ZK to compose, create topics | Low — no app code touched | Remove Kafka services |
| 2 | `telegram-bot-service` | Medium — stop monolith's auto-scan, start new service | Re-enable monolith task |
| 3 | `preprocessing-service` | Low — stateless, pure transform | Drop topic; route raw→model directly |
| 4 | `model-service` | High — must load models, write Mongo correctly | Re-enable monolith ensemble |
| 5 | Slim `api-service` | Low — read-only; same DB and schemas | Fall back to old backend |
| 6 | Frontend | None — no changes needed | N/A |
| 7 | Delete monolith | Low (after smoke-test) | Git revert |

**Recommended order**: complete and smoke-test each phase in a local Docker Compose
environment before moving to the next. Phases 2 and 4 are the highest-risk steps because
they own the bot token (only one consumer allowed) and the ML models (slow startup).
