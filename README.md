# SIGNAL — scrape with Scraper Studio, then a local RAG pipeline

Hackathon path: **useful public data → Scraper Studio CLI → pipeline** (this repo). Do not start in the Bright Data website UI.

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
# needs: ollama serve && ollama pull llama3.2
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
