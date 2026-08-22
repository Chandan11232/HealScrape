# SIGNAL — scrape with Scraper Studio, then a local RAG pipeline

Hackathon path: **useful public data → Scraper Studio CLI → pipeline** (this repo). Do not start in the Bright Data website UI.

---

## For judges

**Live API:** https://healscrape-production.up.railway.app  
**Swagger UI:** https://healscrape-production.up.railway.app/docs  
**Demo video (full scrape → ingest → query → heal):** _[add your link here]_

### What this project does

Custom **Bright Data Scraper Studio** collectors (`c_*` IDs) feed a closed-corpus RAG pipeline: scrape → normalize → embed (Chroma, local CPU) → cited answers (Groq). When a collector’s extraction breaks, **Heal Lab** triggers Bright Data’s AI refactor on the **same collector ID**, then re-scrapes to measure before/after health.

### Quick health check (no API keys needed)

```bash
curl https://healscrape-production.up.railway.app/health
# → {"status":"ok"}
```

### What works live right now (no Bright Data credits required)

These paths do **not** call Scraper Studio and work even when the Bright Data wallet is empty:

| Try this | Where | Expected result |
|----------|--------|-----------------|
| Wikipedia question | `POST /query` or **Console** | Live answer via Wikipedia API |
| Weather question | `POST /query` or **Console** | Live forecast via Open-Meteo |
| API explorer | `/docs` | All endpoints documented |

**Console — copy/paste these:**

- `What is artificial intelligence, according to Wikipedia?`
- `What is the weather in London?`

**curl:**

```bash
curl -X POST https://healscrape-production.up.railway.app/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is artificial intelligence, according to Wikipedia?"}'
```

### RAG on scraped corpus (pre-ingested data)

Questions about **TechCrunch, FastAPI, React, The Verge**, etc. need chunks in Chroma (`chunk_count > 0`).

```bash
curl https://healscrape-production.up.railway.app/knowledge
```

If `chunk_count` is 0, run ingest first (or see the demo video). Example after data is loaded:

```bash
curl -X POST https://healscrape-production.up.railway.app/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "How does dependency injection work in FastAPI?"}'
```

**Console examples that need ingested data:**

- `How does dependency injection work in FastAPI?`
- `What did the scraped TechCrunch or The Verge articles say about AI?`

### Bright Data scrape & heal (requires active credits)

`POST /scrape` (source `brightdata`) and `POST /heal` call Scraper Studio. Bright Data’s free tier is **5,000 credits/month** (resets on the **1st**). If credits are exhausted, the API returns:

```json
{"detail": "Trigger failed: 403 {\"error\":\"customer is inactive\"}"}
```

**This is a billing/credit limit, not a deployment bug.** The integration is implemented end-to-end; see the demo video for a full live run including before/after heal metrics.

| Endpoint | Needs Bright Data credits? | If credits = 0 |
|----------|---------------------------|----------------|
| `POST /scrape` | Yes | 502 with `customer is inactive` |
| `POST /heal` | Yes | Job completes with “trigger failed” + placeholder before-metrics |

### Heal Lab (`/heal`) — please watch the demo video first

Self-heal is the core differentiator but takes **5–12 minutes** per collector and **requires Bright Data credits**. Without credits, Heal Lab will show `0%` placeholder “before” metrics and end with *“Bright Data trigger failed… collector left unchanged.”*

**Recommended:** watch the demo video for authentic before/after heal on The Verge / Devpost / FastAPI collectors, then use `/docs` to inspect the `HealRequest` / `HealResponse` schema.

### Suggested 5-minute judging flow

1. `GET /health` — confirm deploy is up  
2. `GET /knowledge` — see configured collectors and `chunk_count`  
3. `POST /query` — Wikipedia question (works without scrape)  
4. `POST /query` — FastAPI or TechCrunch question (if `chunk_count > 0`)  
5. Open **Heal Lab** or `POST /heal` — only if credits are active; otherwise use the demo video  
6. Skim `/docs` for scrape → ingest → query → heal → export flow  

### Architecture (one glance)

```
Scraper Studio collector (c_*)
    → POST /scrape → normalize + health score
    → POST /ingest → Chroma (local embeddings)
    → POST /query  → retrieve + Groq answer + sources
    → POST /heal   → Bright Data AI refactor → re-scrape → before/after metrics
```

### Repo map

| Path | What to look at |
|------|-----------------|
| `backend/app/scrapers/brightdata_client.py` | Scraper Studio trigger + poll |
| `backend/app/scrapers/self_heal.py` | Bright Data AI heal API |
| `backend/app/api/routes_heal.py` | Heal loop (diagnose → heal → re-scrape) |
| `backend/app/rag/pipeline.py` | RAG + Wikipedia/weather shortcuts |
| `frontend-react/src/components/HealDashboard.jsx` | Heal Lab UI |
| `frontend-react/src/components/Console.jsx` | RAG console |

---

## 1. Quick start with Scraper Studio (CLI)

Needs Bright Data **free-tier credits** (they reset on the 1st of the month). If the balance is 0, `create` / `run` will fail until then or until you add funds.

```bash
npx -p @brightdata/cli bdata login
```

A browser window opens; finish login. The CLI creates unlocker/browser zones if needed.

Pick a **real article or forecast page** (not a site homepage). Create one collector per site:

```bash
# Wikipedia — short article so generation does not time out
npx -p @brightdata/cli bdata scraper create \
  "https://en.wikipedia.org/wiki/Dog" \
  "Extract article title, lead summary, and main article text"

# Weather
npx -p @brightdata/cli bdata scraper create \
  "https://weather.com/" \
  "Extract location, current temperature, condition, and forecast text"
```

Wait until it prints `Template created: c_...` and status `done` (often 5–15 minutes). Then:

```bash
npx -p @brightdata/cli bdata scraper run c_WIKI_ID "https://en.wikipedia.org/wiki/Dog" --pretty
npx -p @brightdata/cli bdata scraper run c_WEATHER_ID "https://weather.com/" --pretty
```

If a site layout breaks later, heal **in place** (same `c_*`):

```bash
npx -p @brightdata/cli bdata scraper heal c_WIKI_ID \
  "Title or article text is empty. Re-capture h1 and main content." \
  --url "https://en.wikipedia.org/wiki/Dog"
```

## 2. Turn that data into this pipeline

This app is the “dashboard / agent / API”: scrape → normalize → embed (Chroma) → ask (local Ollama) → optional self-heal on the same collector id.

Weather questions use [Open-Meteo](https://open-meteo.com/) (free, no key). Wikipedia-style questions (`what is…`, or any query mentioning Wikipedia) use the live [Wikipedia API](https://www.mediawiki.org/wiki/API:Main_page) — no scrape/ingest needed for those.

```bash
cp backend/.env.example backend/.env
```

Put the CLI collector ids in `.env` (one JSON line). Copy the API key from login or [account settings](https://brightdata.com/cp/setting):

```
BRIGHTDATA_API_KEY=your_key
BRIGHTDATA_SCRAPERS={"wikipedia_ai": "c_WIKI_ID", "weather": "c_WEATHER_ID"}
```

You can add more keys anytime (`tiangolo`, `theverge`, …) — `scraper_name` on `/scrape` and Heal Lab is any key in that JSON.

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# needs: GROQ_API_KEY in .env (https://console.groq.com/keys)
uvicorn app.main:app --reload

# Frontend (second terminal)
cd frontend-react
npm install
npm run dev
```

Trigger via API (uses the same `c_*` as `bdata scraper run`):

```bash
curl -X POST http://localhost:8000/scrape \
  -H 'Content-Type: application/json' \
  -d '{
    "job_tag": "wiki_dog",
    "source": "brightdata",
    "scraper_name": "wikipedia_ai",
    "urls": ["https://en.wikipedia.org/wiki/Dog"],
    "auto_heal": false
  }'

curl -X POST http://localhost:8000/ingest \
  -H 'Content-Type: application/json' \
  -d '{"job_tag": "wiki_dog"}'
```

Console: http://localhost:5173/console  
API docs: http://localhost:8000/docs
