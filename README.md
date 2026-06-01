# 📰 The AI Bulletin
> An automated, opinionated AI newspaper. Reads 25+ sources, filters the hype, prints what matters.

<img width="1529" height="1079" alt="image" src="https://github.com/user-attachments/assets/4bd440bf-9ef3-4d87-8032-3ba990c69144" />


[📐 Architecture](docs/architecture.md) 

## What it does
The AI Bulletin is a high-signal news aggregator designed like a premium print newspaper. Instead of showing you a noisy, chronological feed of every press release, it scrapes dozens of technical and community sources in parallel, mathematically penalizes clickbait headlines, and groups stories into an editorial layout. It separates engineering updates and research papers from PR announcements so you can quickly see what is actually being built.

## Quick start (see it in 10 seconds)
You can view the fully functioning dashboard instantly—no API keys or database setup required.
```bash
git clone https://github.com/adarsh733/the-ai-bulletin.git
cd the-ai-bulletin
open index.html
```
*(The UI will automatically fallback to reading an inlined JSON sample payload if it detects it's running locally outside the IDE).*

## Run the live scraper
To fetch fresh news, update the cache, and re-run the heuristic scoring pipeline, simply use the provided launcher scripts. This will run the Python scraper and instantly boot up a local server for you to view the live results:

**On Windows:**
```bash
pip install -r requirements.txt
run.bat
```

**On Mac/Linux:**
```bash
pip install -r requirements.txt
chmod +x run.sh
./run.sh
```

## How it works
```mermaid
graph TD
    A[Fetch: ThreadPool Scrapers] -->|JSON/RSS Data| B(Dedupe: Jaccard Similarity)
    B --> C{Score: Hype Penalty & Impact}
    C -->|High Signal| D[Classify: Column Routing]
    C -->|Low Signal / PR Fluff| X((Discard))
    D --> E[Render: Vanilla JS / HTML]
    
    style A fill:#f9f5f0,stroke:#d4c4b7,stroke-width:2px,color:#141414
    style B fill:#f9f5f0,stroke:#d4c4b7,stroke-width:2px,color:#141414
    style C fill:#f9f5f0,stroke:#d4c4b7,stroke-width:2px,color:#141414
    style D fill:#f9f5f0,stroke:#d4c4b7,stroke-width:2px,color:#141414
    style E fill:#f9f5f0,stroke:#d4c4b7,stroke-width:2px,color:#141414
    style X fill:#ffcccc,stroke:#cc0000,stroke-width:2px,color:#141414
```

The pipeline is split into five distinct stages:
1. **Fetch**: A `ThreadPoolExecutor` dispatches concurrent workers to scrape 25+ RSS feeds, subreddits, and curated social profiles. 
2. **Dedupe**: Titles are compared against the active database using a >0.70 Jaccard similarity threshold to filter out duplicate reporting of the same story.
3. **Score**: The script parses summaries for numeric metrics, funding signals, or novel releases to boost impact, and subtracts points for specific clickbait "hype words".
4. **Classify**: Based on the source and vocabulary, the story is sorted into one of three newspaper columns (e.g., *Built & Shipped* vs *The Big Picture*).
5. **Render**: The frontend Vanilla JS reads the emitted JSON payload and paints the aesthetic warm-beige layout without any virtual DOM overhead.

## 🤖 Built with Antigravity & Jetro AI Orchestration
This project wasn't built using a traditional monolithic stack (like React + Node.js). Instead, it was developed entirely through advanced agentic orchestration.

* **Antigravity IDE (Vibe Coding):** The core application logic—including the concurrent ThreadPool scraper and the Jaccard deduplication algorithm—was engineered via "vibe coding" inside Google's Antigravity IDE. Antigravity acts as the autonomous agent writing, refactoring, and debugging the codebase in real-time.
* **Jetro MCP Connector:** To give the AI agent advanced capabilities, Jetro AI is plugged into Antigravity as an MCP (Model Context Protocol) connector. This exposes a suite of specialized tools (`jet_render`, `jet_canvas`, `jet_data`) directly to the AI, allowing it to autonomously build, wire, and manage visual interfaces.
* **The Infinite Canvas:** Jetro provides an infinite visual workspace where outputs are rendered as dynamic HTML "frames". During development, there was no traditional web server. Instead, our UI (`index.html`) was rendered as a live, interactive frame directly on the Jetro project canvas, allowing for instant visual feedback.
* **The Orchestration Bridge (`jet:refresh`):** Rather than writing complex REST API endpoints, we used Jetro's refresh bindings to glue the backend to the frontend. The Python script was bound to the HTML frame on a timer. When the script executed, it printed a hermetically sealed JSON payload to standard output. Jetro instantly captured this stdout stream and piped it directly into the HTML UI via a custom `jet:refresh` DOM event, resulting in a zero-latency data bridge.
* **The Standalone Pivot:** To make this repository open-source and easily runnable for developers on GitHub, I orchestrated a "standalone pivot". I wrote a fallback `fetch()` mechanism in `index.html` to bypass the Jetro event bus when running locally, and bundled tiny local launcher scripts (`run.bat` / `run.sh`) so anyone can boot the architecture without needing the proprietary Jetro engine.
## What I learned
* **Stdout serialization requires strict discipline.** My IDE bindings expected a single JSON object. A single intermediate `print("loading...")` crashed the pipeline. I learned to hermetically seal `sys.stdout` for the final payload and route all progress tracking explicitly to `sys.stderr`.
* **CORS is ruthless on local files.** You cannot simply `fetch('data.json')` in Javascript if the user opens the HTML file via the `file:///` protocol. To ensure the repo was frictionlessly cloneable, I inlined the sample data payload directly into the HTML `<head>`.
* **Simple heuristics beat complex LLMs for routing.** You don't need a heavy language model to classify clickbait. Counting instances of words like "mind-blowing" and comparing token overlap (Jaccard similarity) between headlines filtered out noise significantly faster and cheaper than an LLM API call.
