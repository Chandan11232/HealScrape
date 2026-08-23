# SIGNAL — Self-Healing Web Scraper with RAG-Powered Q&A

<div align="center">

**Stop fixing broken scrapers. Let AI do it.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Live API](https://healscrape-production.up.railway.app) • [Swagger UI](https://healscrape-production.up.railway.app/docs) • [Frontend](https://signal-sage.vercel.app) • [Demo Video](#-demo-video)

</div>

---

## What is SIGNAL?

SIGNAL is a **self-healing web scraper** with RAG-powered Q&A. It scrapes documentation sites, indexes them into a searchable knowledge base, and **automatically repairs itself** when scrapers break — no manual intervention needed.

### The Problem

Web scrapers break constantly. Sites update their HTML, selectors stop working, and someone has to manually debug and fix the extraction logic. It's tedious, time-consuming, and happens repeatedly.

### The Solution

SIGNAL closes the loop: **scrape → detect degradation → auto-fix → verify**. When a scraper's extraction quality drops, Bright Data's AI analyzes the site's HTML changes, proposes a collector fix, and applies it automatically.

---

## Live Demo

| Component | URL |
|-----------|-----|
| **Backend API** | https://healscrape-production.up.railway.app |
| **Swagger UI** | https://healscrape-production.up.railway.app/docs |
| **Frontend** | https://heal-scrape.vercel.app |

### Quick Test (No API Keys Required)

```bash
# Health check
curl https://healscrape-production.up.railway.app/health
# → {"status":"ok"}

# Ask a Wikipedia question (live, no scrape needed)
curl -X POST https://healscrape-production.up.railway.app/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is artificial intelligence?"}'

# Check indexed data
curl https://healscrape-production.up.railway.app/knowledge
```

---


## How Bright Data Scraper Studio Is Used

SIGNAL uses **Bright Data Scraper Studio** as its core scraping infrastructure. Here's exactly how:

### 1. Custom Collectors (13 configured)

Each documentation site has a dedicated Bright Data collector (`c_*` ID) built in Scraper Studio. These collectors handle:

- **Anti-bot protection** — bypasses Cloudflare, rate limiting, CAPTCHAs
- **JavaScript rendering** — executes client-side JS to get full page content
- **Proxy rotation** — uses residential IPs to avoid blocking
- **Structured extraction** — custom parsers extract title, content, metadata

```
react.dev          → c_mt44ac9619tp18jbbb
fastapi.tiangolo   → c_***
docs.python.org    → c_***
docs.docker.com    → c_***
docs.stripe.com    → c_***
developer.mozilla  → c_***
... (13 total)
```

### 2. Scraping Flow

```
POST /scrape
    │
    ├─► Trigger Bright Data collector
    │   POST https://api.brightdata.com/dca/trigger?collector={id}
    │   Body: [{"url": "https://react.dev/..."}]
    │
    ├─► Poll for results
    │   GET https://api.brightdata.com/dca/dataset?id={snapshot_id}
    │   Waits for {"status": "collecting"} → JSON array of extracted records
    │
    ├─► Normalize output
    │   Maps 8+ different collector schemas to uniform NormalizedDoc
    │   Extracts: url, title, content, metadata
    │
    └─► Score health
        Calculates: success_rate, empty_title_pct, empty_body_pct
```

### 3. Self-Healing Flow (The Core Innovation)

When extraction quality drops, SIGNAL triggers Bright Data's **AI Code Fixer** on the **same collector ID**:

```
POST /heal
    │
    ├─► DIAGNOSE — scrape with current collector, measure health
    │   "Success rate: 0%, Empty titles: 100%"
    │
    ├─► TRIGGER AI — send collector to Bright Data's refactor_template API
    │   POST /dca/resume_automation_job
    │   Body: {"message": "Title is empty. Fix h1 selector.", "auto_save": true}
    │
    ├─► AI ANALYZES — Bright Data's AI:
    │   • Reads the site's current HTML structure
    │   • Identifies broken CSS selectors
    │   • Rewrites extraction logic
    │   • Generates preview of fixed output
    │
    ├─► AUTO-APPROVE — validate preview looks reasonable
    │   • Has title-like field? ✓
    │   • Has body-like field? ✓
    │   • No junk values? ✓
    │
    ├─► SAVE TO PRODUCTION — publish fix to same collector ID
    │
    └─► RE-SCRAPE — measure "after" metrics
        "Success rate: 100%, Empty titles: 0%"
```

### 4. Why This Matters

| Without SIGNAL | With SIGNAL |
|----------------|-------------|
| Scraper breaks → manual debug → fix → test → deploy | Scraper breaks → auto-detect → AI fixes → verify |
| Takes hours/days | Takes 7-8 minutes |
| Requires human intervention | Fully automated |
| Same collector ID preserved | Same collector ID preserved |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│
│  │ Landing Page │  │   Console   │  │     Heal Dashboard      ││
│  │ Radar Viz    │  │ RAG Q&A     │  │ Before/After Metrics    ││
│  └─────────────┘  └─────────────┘  └─────────────────────────┘│
│                    React + Vite (Vercel)                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/REST
┌───────────────────────────▼─────────────────────────────────────┐
│                     BACKEND (FastAPI)                            │
│                  Railway Container                              │
│                                                                 │
│  /scrape ──► Bright Data trigger + poll                         │
│  /ingest ──► chunk (800c) + embed (MiniLM) + store (ChromaDB)  │
│  /query  ──► retrieve + generate (Groq) + cite                 │
│  /heal   ──► diagnose + AI fix + approve + re-scrape           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
    ┌───────────┬───────────┼───────────┬───────────┐
    ▼           ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Bright │ │  Groq  │ │ChromaDB│ │Sentence│ │External│
│  Data  │ │  (LLM) │ │(Vector)│ │Transform│ │  APIs  │
│        │ │        │ │        │ │  (CPU)  │ │        │
│ 13     │ │ openai/│ │ Cosine │ │MiniLM  │ │OpenMeteo│
│collect.│ │gpt-oss │ │ HNSW   │ │-L6-v2  │ │Wikipedia│
│ Free   │ │-120b   │ │ Local  │ │ ~80MB  │ │ Free   │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

---

## Example Structured Output

### Query Response

```json
{
  "answer": "Summary: Server Components are a new type of Component that renders on the server, separate from your client app or SSR server.\n\nKey points:\n- Server Components run in a separate environment from the client — the \"server\" in React Server Components\n- They can be run for each request using a web server\n- Server Components are separate from client components and SSR",
  "sources": [
    {
      "rank": 1,
      "url": "https://react.dev/reference/rsc/server-components",
      "title": "Server Components",
      "source": "react"
    }
  ],
  "in_scope": true,
  "reason": null,
  "indexed_domains": [
    "en.wikipedia.org",
    "fastapi.tiangolo.com",
    "react.dev",
    "docs.python.org",
    "openai.com",
    "developer.mozilla.org",
    "docs.docker.com",
    "docs.stripe.com"
  ],
  "chunk_count": 858
}
```

### Scrape Response

```json
{
  "job_tag": "demo_live_react",
  "source": "brightdata",
  "records_found": 1,
  "normalized_path": "data/processed/normalized_demo_live_react.json",
  "health": {
    "empty_title_pct": 0.0,
    "empty_body_pct": 0.0,
    "success_rate": 100.0
  },
  "needs_heal": false,
  "heal_started": false,
  "message": "Collector healthy (success 100%). No heal needed."
}
```

### Heal Response (Before/After)

```json
{
  "status": "completed",
  "job_tag": "react_heal_demo",
  "before": {
    "empty_title_pct": 100.0,
    "empty_body_pct": 100.0,
    "success_rate": 0.0
  },
  "after": {
    "empty_title_pct": 0.0,
    "empty_body_pct": 0.0,
    "success_rate": 100.0
  },
  "improved": true,
  "message": "Bright Data AI fixed the collector. Before: 0% success. After: 100% success.",
  "collector_url": "https://brightdata.com/cp/scrapers/c_***"
}
```

### Ingest Response

```json
{
  "documents_in": 36,
  "chunks_added": 521
}
```

### Knowledge Response

```json
{
  "chunk_count": 858,
  "indexed_domains": [
    "en.wikipedia.org",
    "fastapi.tiangolo.com",
    "react.dev",
    "docs.python.org",
    "openai.com",
    "developer.mozilla.org",
    "docs.docker.com",
    "docs.stripe.com",
    "www.anthropic.com",
    "www.sqlite.org"
  ],
  "sources": [
    {
      "domain": "react.dev",
      "scraper_name": "react",
      "kind": "docs",
      "covers": "React documentation",
      "example_url": "https://react.dev/reference/rsc/server-components"
    }
  ],
  "scraper_names": ["react", "tiangolo", "python_docs", "docker_intro", "stripe_docs", "mdn_web"]
}
```

---

## Tech Stack

| Component | Choice | Cost |
|-----------|--------|------|
| **Scraping** | Bright Data Scraper Studio | Free tier (5K credits/month) |
| **Embeddings** | sentence-transformers/all-MiniLM-L6-v2 | Free (local CPU) |
| **Vector DB** | ChromaDB (persistent) | Free (local disk) |
| **LLM** | Groq (openai/gpt-oss-120b) | Free tier |
| **Backend** | FastAPI + Uvicorn | Free (Railway) |
| **Frontend** | React 18 + Vite 8 | Free (Vercel) |
| **Weather** | Open-Meteo API | Free (no key) |
| **Wikipedia** | MediaWiki API | Free (no key) |

**Total cost: $0 per query.**

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/scrape` | Trigger Bright Data collector |
| `GET` | `/scrape/{job_tag}/status` | Poll scrape status |
| `POST` | `/ingest` | Chunk + embed + store in ChromaDB |
| `POST` | `/query` | RAG query with cited sources |
| `GET` | `/knowledge` | Show indexed domains and chunk count |
| `POST` | `/heal` | Start self-healing loop |
| `GET` | `/heal/{job_tag}` | Poll heal status |
| `POST` | `/heal/{job_tag}/review` | Approve/decline AI proposal |
| `POST` | `/heal/{job_tag}/save-production` | Publish fix to production |
| `GET` | `/export/{job_tag}` | Download scraped data |

---

## Project Structure

```
data_scraper/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entrypoint
│   │   ├── config.py                  # Environment config
│   │   ├── seed_data.py               # Auto-seed demo data
│   │   ├── api/
│   │   │   ├── routes_scrape.py       # POST /scrape (async trigger)
│   │   │   ├── routes_ingest.py       # POST /ingest
│   │   │   ├── routes_query.py        # POST /query (RAG)
│   │   │   ├── routes_heal.py         # POST /heal (self-healing)
│   │   │   └── routes_knowledge.py    # GET /knowledge
│   │   ├── scrapers/
│   │   │   ├── brightdata_client.py   # Bright Data API client
│   │   │   ├── self_heal.py           # Heal API (639 lines)
│   │   │   ├── scrape_runner.py       # Scrape + normalize + score
│   │   │   ├── normalizer.py          # 8+ schema normalizer
│   │   │   └── health.py              # Health metrics + thresholds
│   │   ├── rag/
│   │   │   ├── pipeline.py            # RAG orchestration
│   │   │   ├── chunker.py             # Sentence-aware chunking
│   │   │   ├── embedder.py            # Local embeddings (CPU)
│   │   │   ├── vectorstore.py         # ChromaDB persistent store
│   │   │   └── retriever.py           # Multi-query retrieval
│   │   └── llm/
│   │       └── client.py              # Groq API client
│   └── requirements.txt
├── frontend-react/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Console.jsx            # RAG query console
│   │   │   ├── HealDashboard.jsx      # Self-healing UI
│   │   │   └── Radar.jsx              # Source visualization
│   │   └── pages/
│   │       ├── LandingEnhanced.jsx    # Landing page
│   │       └── HealPage.jsx           # Heal Lab page
│   └── package.json
└── README.md
```

---

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 18+
- Bright Data account (free tier)
- Groq API key (free)

### Setup

```bash
# Clone the repo
git clone https://github.com/Chandan11232/HealScrape.git
cd HealScrape

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
# BRIGHTDATA_API_KEY=your_key
# BRIGHTDATA_SCRAPERS={"react": "c_***", "tiangolo": "c_***"}
# GROQ_API_KEY=your_key

# Start backend
uvicorn app.main:app --reload

# Frontend (second terminal)
cd frontend-react
npm install
npm run dev
```

### API Keys

| Key | Where to get | Cost |
|-----|--------------|------|
| `BRIGHTDATA_API_KEY` | [Bright Data Dashboard](https://brightdata.com/cp/setting) | Free tier |
| `GROQ_API_KEY` | [Groq Console](https://console.groq.com/keys) | Free tier |

---

## Self-Healing: Step-by-Step

### 1. Diagnose

The system runs a scrape and calculates health metrics:

```json
{
  "success_rate": 0.0,
  "empty_title_pct": 100.0,
  "empty_body_pct": 100.0
}
```

### 2. Trigger Bright Data AI

Sends the broken collector to Bright Data's AI Code Fixer:

```json
{
  "prompt": "Extraction quality is low. Success rate 0%, empty titles 100%. Fix the CSS selectors.",
  "custom_input": [{"url": "https://react.dev/reference/rsc/server-components"}]
}
```

### 3. AI Proposes Fix

Bright Data's AI:
- Analyzes the site's current HTML structure
- Identifies broken selectors (e.g., `.old-class` → `.new-class`)
- Rewrites extraction logic
- Generates a preview of fixed output

### 4. Auto-Approve

The system validates the preview:
- ✓ Has title-like field
- ✓ Has body-like field
- ✓ No junk values ("", "none", "404")

### 5. Save to Production

Publishes the fix to the **same collector ID** — no new collector needed.

### 6. Re-Scrape & Verify

Runs a fresh scrape to measure improvement:

```json
{
  "before": {"success_rate": 0.0},
  "after": {"success_rate": 100.0}
}
```

---

## 13 Indexed Sources

| Scraper Name | Domain | Kind |
|--------------|--------|------|
| `react` | react.dev | docs |
| `tiangolo` | fastapi.tiangolo.com | docs |
| `python_docs` | docs.python.org | docs |
| `docker_intro` | docs.docker.com | docs |
| `stripe_docs` | docs.stripe.com | docs |
| `mdn_web` | developer.mozilla.org | docs |
| `sqlite_docs` | www.sqlite.org | docs |
| `openai` | openai.com | blog |
| `anthropic_news` | www.anthropic.com | blog |
| `wikipedia_ai` | en.wikipedia.org | encyclopedia |
| `wiki_javascript` | en.wikipedia.org | encyclopedia |
| `github_readme` | github.com | code |
| `devpost` | devpost.com | listings |

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [Bright Data](https://brightdata.com) for Scraper Studio and AI Code Fixer
- [Groq](https://groq.com) for fast LLM inference
- [ChromaDB](https://www.trychroma.com) for local vector storage
- [sentence-transformers](https://www.sbert.net) for local embeddings
- Built with [Cursor AI](https://cursor.sh) as a pair programmer
