# Distress-Detector

Collect Reddit posts (distress vs. control labels), store them in MongoDB, expose a **FastAPI** API, and browse them in a **React** dashboard.

For **how to run** the stack (Docker or local), see [Running the project](#running-the-project) at the end of this file.

---

## Folder reference

| Folder / file | Purpose |
|---------------|---------|
| **`api_main.py`** | FastAPI application entry: lifespan (Mongo client), CORS, router registration. |
| **`app/`** | Core Python package: API layer, domain models, data access, scrapers/collectors, CLI views. |
| **`app/api/`** | HTTP API: routers, Pydantic schemas, FastAPI dependencies, BSON→JSON serialization. |
| **`app/api/routers/`** | Route handlers grouped by resource (`posts`, `stats`). |
| **`app/controllers/`** | Orchestration for long-running jobs: Selenium Reddit scrape, PullPush bulk collection. |
| **`app/models/`** | Dataclasses / types for posts and PullPush payloads. |
| **`app/repositories/`** | MongoDB access: synchronous collection helpers and `MongoPostsRepository`. |
| **`app/services/`** | Infrastructure: Chrome driver factory, PullPush HTTP client, Reddit DOM parser. |
| **`app/views/`** | Small CLI “views” (logging/print) used by scrapers and collectors. |
| **`docker/`** | `backend.Dockerfile` — multi-stage Python image running Uvicorn. |
| **`frontend/`** | Vite + React + TypeScript SPA; production image uses nginx. |
| **`frontend/public/`** | Static assets (favicon, icons). |
| **`frontend/src/`** | App source: routes, pages, layout, API client. |
| **`notebooks/`** | Jupyter notebooks (e.g. EDA); not required for the web app. |
| **`scripts/`** | One-off utilities (CSV export from MongoDB). |
| **Root config** | `docker-compose.yml`, `requirements.txt` / `requirements-api.txt`, `.env.example`, `.dockerignore`. |

---

## Backend: modules, classes, and functions

### `api_main.py`

| Name | Role |
|------|------|
| `lifespan` | Async context manager: opens `AsyncIOMotorClient` on startup, closes on shutdown. |
| `app` | `FastAPI` instance with CORS and included routers. |

### `app/mongo_config.py`

| Name | Role |
|------|------|
| `_load_env` | Loads `.env` via `python-dotenv`. |
| `load_mongo_uri` | Returns `MONGO_URI` or raises if missing. |
| `resolve_db_name` | Returns `MONGO_DB_NAME` env or default `reddit_distress_db`. |
| `COLLECTION_NAME` | Collection name for posts (`"posts"`). |
| `DB_NAME` | Resolved database name at import time. |

### `app/api/config.py`

Re-exports `COLLECTION_NAME`, `DB_NAME`, `load_mongo_uri` for the API package.

### `app/api/deps.py`

| Name | Role |
|------|------|
| `get_mongo_client` | Returns `request.app.state.mongo_client`. |
| `get_posts_collection` | Returns Motor collection `db[DB_NAME][COLLECTION_NAME]`. |

### `app/api/schemas.py` (Pydantic)

| Name | Role |
|------|------|
| `RedditPost` | API shape for one post (`post_id`, optional `title`, `body`, `subreddit`, `label`, `created_utc`, `timestamp`). |
| `PostsListResponse` | `total` + `items: list[RedditPost]`. |
| `StatsResponse` | `total_records`, `counts_by_label`, `posts_per_subreddit`. |

### `app/api/serialization.py`

| Name | Role |
|------|------|
| `serialize_mongo_doc` | Makes a Mongo document JSON-safe: stringifies `_id`, fills `body`/`post_id` from legacy fields (`selftext`, `id`, `reddit_id`). |

### `app/api/routers/posts.py`

| Name | Role |
|------|------|
| `list_posts` | `GET /posts` — filter by optional `label`, `subreddit`; paginate with `limit`/`offset`; sort by `created_utc` then `_id`. |
| `search_posts` | `GET /posts/search` — case-insensitive regex on `title`, `body`, `selftext`; optional `label`. |
| `get_post` | `GET /posts/{post_id}` — lookup by `post_id`, `id`, or `reddit_id`. |

### `app/api/routers/stats.py`

| Name | Role |
|------|------|
| `stats_summary` | `GET /stats/summary` — total documents, aggregation counts by `label`, counts per `subreddit`. |

### `app/models/post.py`

| Name | Role |
|------|------|
| `Post` | Canonical stored post: `post_id`, `title`, `body`, `subreddit`, `label`, `timestamp`, `scraped_at`. |
| `Post.to_mongo` | Dict suitable for `insert_one` in the scraper path. |

### `app/models/pullpush.py`

| Name | Role |
|------|------|
| `PullPushSubmission` | Typed subset of a PullPush API submission (`post_id`, `subreddit`, `title`, `selftext`, `created_utc`). |

### `app/repositories/mongo_connection.py`

| Name | Role |
|------|------|
| `get_posts_collection` | Sync PyMongo `Collection` for `posts` (used by scripts / non-async code paths). |

### `app/repositories/mongo_posts.py`

| Name | Role |
|------|------|
| `MongoPostsRepository` | Repository wrapping a PyMongo collection. |
| `ensure_indexes` | Unique sparse/indexes on `post_id` and `reddit_id`. |
| `count_posts_for_subreddit` | Count docs for one subreddit. |
| `exists_any_id` | True if `reddit_id`, `post_id`, or legacy `id` already exists. |
| `insert_post` | Inserts a `Post` dataclass; returns `False` on duplicate key. |
| `insert_raw` | Inserts an arbitrary dict; `False` on duplicate. |
| `insert_many_raw` | Bulk insert with `ordered=False`; returns inserted count (handles partial duplicates). |

### `app/services/chrome_driver.py`

| Name | Role |
|------|------|
| `ChromeDriverConfig` | Dataclass: headless, optional profile dir, Chrome `version_main`, timeouts. |
| `ChromeDriverFactory.create` | Builds `undetected_chromedriver.Chrome`, applies options, opens reddit.com, returns driver. |

### `app/services/shreddit_parser.py`

| Name | Role |
|------|------|
| `ShredditPostParser.parse_post_element` | Parses a `shreddit-post` Selenium element into `Post` or `None` (skips short bodies, handles stale DOM). |

### `app/services/pullpush_client.py`

| Name | Role |
|------|------|
| `_sleep_seconds_after_429` | Parses `Retry-After` (or fallback) after HTTP429. |
| `PullPushClient` | Session with User-Agent; calls PullPush submission search API. |
| `PullPushClient.fetch_submissions` | GET paginated submissions for a subreddit before a given `created_utc` epoch; retries on 429 with backoff. |

### `app/views/scraper_view.py`

| Name | Role |
|------|------|
| `ScraperCLIView` | Logging hooks: subreddit start/skip/timeout/progress/finished, cooldown. |

### `app/views/cli_progress.py`

| Name | Role |
|------|------|
| `CLIProgressView.final_stretch` | Prints one-line progress for the legacy PullPush stretch loop. |

### `app/controllers/reddit_scraper_controller.py`

| Name | Role |
|------|------|
| `RedditScrapeConfig` | Dataclass: subreddit→label map, caps, sleeps, scroll limits, Chrome version, etc. |
| `RedditScraperController` | Drives Selenium over `/r/{sub}/`, scrolls, parses posts, inserts via `MongoPostsRepository`. |
| `RedditScraperController.run` | Iterates configured subreddits, creates driver, calls `_scrape_subreddit` each, quits driver in `finally`. |
| `RedditScraperController._scrape_subreddit` | (Private) Loads subreddit page, waits for `shreddit-post`, scroll loop, dedup + insert until cap. |
| `RedditScraperController._sleep` | Random sleep between min/max seconds. |

There is no separate `__main__` CLI in-repo for the Selenium scraper; you instantiate `RedditScraperController` from your own script or REPL if you use this path.

### `app/controllers/pullpush_final_stretch_controller.py`

Module-level **constants** (not exhaustive): targets per label, page size, sleep, min words, bulk flush size, backoff, and tuples `TURBO_LABEL_1_SUBREDDITS` / `TURBO_LABEL_0_SUBREDDITS`.

| Name | Role |
|------|------|
| `utc_iso_from_epoch_seconds` | Epoch seconds → UTC ISO string. |
| `word_count` | Whitespace-separated word count. |
| `normalize_subreddit` | Strip `r/`, lowercase. |
| `subreddit_quotas_for_total` | Splits an integer quota evenly across subreddit names (larger shares first). |
| `is_self_post` | Whether a raw PullPush dict represents a self post. |
| `load_dedup_ids` | Loads existing `reddit_id`/`post_id`/`id` from Mongo into a set for turbo dedup. |
| `raw_to_turbo_doc` | Maps raw PullPush JSON + label to a Mongo document dict (or `None` if filtered). |
| `PullPushTurboCollector` | Main bulk collector: per-label targets, round-robin or capped-per-sub fetches, buffered `insert_many_raw`, tqdm. |
| `PullPushTurboCollector._remaining_for_label` | How many docs still needed for a label vs target. |
| `PullPushTurboCollector._collect_single_label` | Inner loop for one label (private). |
| `PullPushTurboCollector.delete_posts_with_label` | `delete_many` by label (e.g. reset label 0). |
| `PullPushTurboCollector.run` | Ensures indexes, loads dedup set, runs label 1 then label 0 (or subset via `labels=`). |
| `PullPushFinalStretchController` | Legacy single-label stretch: paginates PullPush, min selftext words, inserts until target. |
| `PullPushFinalStretchController._resume_before_epoch` | Starting `before` cursor from oldest doc or “now”. |
| `PullPushFinalStretchController._parse_submission` | Raw dict → `PullPushSubmission` or `None`. |
| `PullPushFinalStretchController._to_mongo_doc` | Submission → Mongo document with `source: "pullpush"`. |
| `PullPushFinalStretchController.run` | Main legacy loop with date floor (Jan 1, 2026) and backoff. |
| `main` | Argparse: default turbo run, `--reset-label0`, `--label0-only`; wires Mongo + `PullPushTurboCollector`. |

Run: `python -m app.controllers.pullpush_final_stretch_controller` (see module docstring).

### `scripts/export_posts_to_csv.py`

| Name | Role |
|------|------|
| `_cell_value` | Normalizes a single CSV cell (ObjectId, dict/list JSON, datetime, bool, etc.). |
| `export_posts_to_csv` | Streams all `posts` documents to a CSV file; returns row count. |
| `main` | CLI (`-o` output path). |

---

## Frontend: files and functions

Routing is defined in `frontend/src/main.tsx` (`createBrowserRouter`). Layout wraps all routes.

### `frontend/src/lib/api.ts`

| Name | Role |
|------|------|
| Types `RedditPost`, `PostsListResponse`, `StatsResponse` | Mirror backend JSON. |
| `buildUrl` | Builds absolute URL with query params from `VITE_API_BASE_URL`. |
| `fetchJson` | `fetch` + error handling. |
| `api.getSummary` | `GET /stats/summary`. |
| `api.listPosts` | `GET /posts` with pagination and filters. |
| `api.searchPosts` | `GET /posts/search`. |
| `api.getPost` | `GET /posts/{id}`. |

### `frontend/src/components/Layout.tsx`

| Name | Role |
|------|------|
| `Layout` | Shell: header, nav (`NavLink` to `/`, `/posts`, `/search`), `Outlet`, footer. |
| `navLinkClass` | Active/inactive link classes. |

### `frontend/src/pages/SummaryPage.tsx`

| Name | Role |
|------|------|
| `SummaryPage` | Loads `api.getSummary()`, shows totals, label breakdown, top subreddits. |

### `frontend/src/pages/PostsPage.tsx`

| Name | Role |
|------|------|
| `clamp` | Clamps a number to `[min, max]`. |
| `PostsPage` | Reads `label`, `subreddit`, `offset`, `limit` from URL; lists posts with pagination links. |

### `frontend/src/pages/SearchPage.tsx`

| Name | Role |
|------|------|
| `SearchPage` | Keyword search form + results from `api.searchPosts`, URL-driven `q`/`label`/pagination. |

### `frontend/src/pages/PostDetailsPage.tsx`

| Name | Role |
|------|------|
| `PostDetailsPage` | Loads one post by `postId` route param via `api.getPost`. |

### `frontend/src/App.tsx`

Default export currently returns `null`; the real app is mounted via `RouterProvider` in `main.tsx`.

### `frontend/src/main.tsx`

Bootstraps React root and `RouterProvider` with child routes for Summary, Posts, Post detail, Search.

### Other frontend files

- **`index.html`** — Vite HTML entry.
- **`vite.config.ts`** — Vite + React plugin; dev server port 3000.
- **`nginx.conf`** — SPA fallback + static serving in Docker runtime stage.
- **`Dockerfile`** — Build with Node, serve with nginx.
- **`.env.example`** — Documents `VITE_API_BASE_URL` for builds.

---

## Docker and config files

| File | Role |
|------|------|
| `docker-compose.yml` | Services: `mongo` (volume + healthcheck), `backend` (port 8001→8000), `frontend` (3000→80). |
| `docker/backend.Dockerfile` | Installs `requirements-api.txt`, non-root user, `uvicorn api_main:app`. |
| `.env.example` | Sample `MONGO_URI` / `MONGO_DB_NAME` for Compose and local dev. |
| `.dockerignore` | Excludes junk from backend build context. |
| `requirements.txt` | Full Python deps (scraper + API + scripts). |
| `requirements-api.txt` | Slim deps for API-only Docker image. |

---

## Running the project

### Docker Compose (full stack)

```bash
docker compose up --build
```

- UI: http://localhost:3000  
- API: http://localhost:8001 — OpenAPI: http://localhost:8001/docs  

Set `MONGO_URI` / `VITE_API_BASE_URL` in `.env` next to `docker-compose.yml` if defaults are wrong for your setup.

### Local development

**Backend** (from repo root, with `.env` containing `MONGO_URI`):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-api.txt
uvicorn api_main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**:

```bash
cd frontend && npm ci
export VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

**PullPush collector** (needs `requirements.txt` and Mongo):

```bash
python -m app.controllers.pullpush_final_stretch_controller
```

---

## Notebooks and data exports

- **`notebooks/`** — Exploratory analysis; not wired into the API.
- **`scripts/export_posts_to_csv.py`** — Dump the `posts` collection to CSV.
- Large CSV/exports in the repo root may be local artifacts; keep them out of version control if they contain sensitive data.
