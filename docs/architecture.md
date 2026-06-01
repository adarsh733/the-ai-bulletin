# Architecture Deep-Dive

The AI Bulletin is a high-signal aggregator built entirely as a standalone Python orchestration pipeline and a vanilla JS frontend. It uses DuckDB as a lightweight local persistence layer to cache articles, avoiding rate limits on subsequent loads.

## System Components

### 1. The Scraping Orchestrator (`src/fetch_news.py`)
This is the main aggregation engine.
* **Concurrent Execution**: Uses Python's `ThreadPoolExecutor` initialized with `max_workers=35` to simultaneously fetch from 25+ RSS feeds, Reddit, and YouTube without serial blocking.
* **Local Persistence**: Uses an embedded **DuckDB** instance (`cache.duckdb`). If a valid cache exists, it outputs the stored payload directly. If the cache is stale or missing, it falls back to read-write mode and triggers the full parallel scrape.
* **Stream Safety**: Emits intermediate progress and log statements directly to `sys.stderr`, leaving `sys.stdout` perfectly clean for the single, final JSON dispatch payload.

### 2. Heuristics & Scoring (`src/scoring.py`)
To prevent PR fluff and clickbait from saturating the feed, the pipeline applies several heuristic layers before committing to the DB:
* **Hype Penalty**: Evaluates summaries against a dictionary of clickbait terms ("mind-blowing", "insane", "revolutionary"). Each match subtracts from the article's relevance score, up to a maximum penalty of `-3.0` points.
* **Impact Boosting**: Grants positive score adjustments if it detects numeric metrics (e.g., funding amounts, performance benchmarks like "50% faster") or specific terminology indicating a novel release.
* **Jaccard Token Deduplication**: Prevents the same PR announcement from appearing multiple times. If an incoming article shares a >70% token overlap (`>0.70` Jaccard similarity) in its title with an already-ingested article, it is discarded as a near-duplicate.

### 3. Sources & Data Definitions (`src/sources.py`)
Separates the configuration from the execution loop. It contains the feed lists, domain weights, and the `FALLBACK_RADAR_POSTS`.
* **The Voices Radar**: The application attempts live social scraping (e.g., via RSSHub for Twitter profiles). If those external feeds are rate-limited or unavailable, it gracefully loads the `FALLBACK_RADAR_POSTS`—a curated set of static profiles—ensuring the "Voices" tab never looks broken to the user.

### 4. The UI (`frontend/newspaper.html`)
A vanilla JS/HTML/CSS implementation.
* **Aesthetics**: Uses an "Editorial Palette" with warm-paper beige (`#FAF8F4`), strict zero-pixel border radii, and serif typography to emulate a premium print newspaper.
* **Offline-First Resilience**: If the frontend initializes and detects no active IDE event bus, it automatically reads `window.__SAMPLE_DATA__` directly from the inline script injected into the `<head>`, preventing the page from remaining stuck in a loading state.
