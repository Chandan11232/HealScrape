import { useState, useEffect } from 'react'
import Navbar from './Navbar'
import { Search, ExternalLink, Sparkles } from 'lucide-react'

const API_BASE = 'http://localhost:8000'

const TAGS = [
  'docs.python.org',
  'fastapi.tiangolo.com',
  'react.dev',
  'techcrunch.com',
  'theverge.com',
  'venturebeat.com',
  'openai.com',
  'devpost.com',
  'remoteok.com',
]

const IN_SCOPE = [
  'How do I use dependency injection in FastAPI?',
  'What are React Server Components?',
  'What is the latest AI news from TechCrunch?',
]

const OUT_OF_SCOPE = [
  "What's the weather in Delhi?",
  'Who won the World Cup?',
]

const LOADING_STEPS = [
  'Embedding query vector',
  'Searching Chroma index',
  'Retrieving top-k chunks',
  'Generating cited answer',
]

export default function Console() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [chunkCount, setChunkCount] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/knowledge`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && typeof data.chunk_count === 'number') setChunkCount(data.chunk_count)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!loading) {
      setLoadingStep(0)
      return
    }
    const interval = setInterval(() => {
      setLoadingStep((s) => (s < LOADING_STEPS.length - 1 ? s + 1 : s))
    }, 800)
    return () => clearInterval(interval)
  }, [loading])

  async function handleSubmit(e) {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) return

    setLoading(true)
    setError(null)
    setResult(null)
    setLoadingStep(0)

    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: trimmed, top_k: 5 }),
      })
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function applySuggestion(s) {
    setQuery(s)
    setResult(null)
    setError(null)
  }

  return (
    <div className="page-shell">
      <Navbar variant="solid" />

      <div className="console-wrap">
        <header className="page-header">
          <div className="page-eyebrow mono">Web Intel Console</div>
          <h1 className="page-title mono">Ask the nine collectors</h1>
          <p className="page-sub">
            This is a closed corpus, not web search. Answers come only from pages
            already scraped by your Bright Data Scraper Studio collectors.
          </p>
        </header>

        <div className="sources-panel">
          <div className="sources-label mono">
            <Sparkles size={12} /> Indexed collectors
            {chunkCount !== null && (
              <span className="chunk-count">
                {chunkCount === 0 ? 'index empty — scrape + ingest first' : `${chunkCount} chunks`}
              </span>
            )}
          </div>
          <div className="sources-tags">
            {TAGS.map((t) => (
              <span className="tag tag-live" key={t}>{t}</span>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="query-form">
          <div className="input-wrap">
            <Search size={16} className="input-icon" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about FastAPI, React, Python docs, or a scraped news page…"
              autoComplete="off"
            />
          </div>
          <button type="submit" disabled={loading || !query.trim()} className="submit-btn mono">
            {loading ? 'Searching…' : 'Ask'}
          </button>
        </form>

        <div className="suggestions">
          <span className="suggestions-label mono">In scope:</span>
          {IN_SCOPE.map((s) => (
            <button
              key={s}
              type="button"
              className="suggestion-chip mono"
              onClick={() => applySuggestion(s)}
              disabled={loading}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="suggestions">
          <span className="suggestions-label mono">Out of scope:</span>
          {OUT_OF_SCOPE.map((s) => (
            <button
              key={s}
              type="button"
              className="suggestion-chip oos mono"
              onClick={() => applySuggestion(s)}
              disabled={loading}
            >
              {s}
            </button>
          ))}
        </div>

        {loading && (
          <div className="loading-pipeline">
            {LOADING_STEPS.map((step, i) => (
              <div
                key={step}
                className={`loading-step ${i < loadingStep ? 'done' : i === loadingStep ? 'active' : ''}`}
              >
                <span className="step-dot" />
                {step}
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="result-block fade-up">
            <div className="answer-card error-card">
              <div className="error-title mono">Connection failed</div>
              Couldn&apos;t reach the API. Make sure the backend is running at{' '}
              <code>{API_BASE}</code>. ({error})
            </div>
          </div>
        )}

        {result && (
          <div className="result-block fade-up">
            <div className={`answer-card ${result.in_scope === false ? 'oos-card' : ''}`}>
              <div className="answer-label mono">
                {result.in_scope === false ? 'Outside the knowledge base' : 'Answer'}
              </div>
              {result.answer}
            </div>
            {result.in_scope !== false && (
              <>
                <div className="sources-heading mono">Sources ({result.sources.length})</div>
                <div className="sources-list">
                  {result.sources.map((s) => (
                    <div className="source-item" key={`${s.rank}-${s.url}`}>
                      <span className="source-rank mono">{String(s.rank).padStart(2, '0')}</span>
                      <div className="source-body">
                        <div className="source-title">{s.title || s.source || 'Untitled'}</div>
                        <a
                          className="source-link"
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {s.url}
                          <ExternalLink size={11} />
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {!loading && !result && !error && (
          <div className="empty-console">
            <div className="empty-console-icon mono">&gt;_</div>
            <p>
              Ask something those nine sites can answer. Off-topic questions are
              refused on purpose so the model cannot invent coverage you never scraped.
            </p>
          </div>
        )}
      </div>

      <style>{`
        .console-wrap {
          width: 100%;
          max-width: 760px;
          margin: 0 auto;
          padding: 40px 20px 80px;
        }

        .sources-panel {
          margin-bottom: 24px;
          padding: 16px;
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 10px;
        }
        .sources-label {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          color: var(--text-dim);
          letter-spacing: 0.06em;
          text-transform: uppercase;
          margin-bottom: 12px;
          width: 100%;
        }
        .sources-tags { display: flex; flex-wrap: wrap; gap: 8px; }
        .chunk-count {
          margin-left: auto;
          text-transform: none;
          letter-spacing: 0;
          color: var(--signal);
        }

        .query-form {
          display: flex;
          gap: 10px;
          margin-bottom: 16px;
        }
        .input-wrap {
          flex: 1;
          position: relative;
        }
        .input-icon {
          position: absolute;
          left: 14px;
          top: 50%;
          transform: translateY(-50%);
          color: var(--text-dim);
          pointer-events: none;
        }
        .input-wrap input {
          width: 100%;
          background: var(--panel);
          border: 1px solid var(--border);
          color: var(--text);
          font-family: 'Inter', sans-serif;
          font-size: 14px;
          padding: 14px 14px 14px 40px;
          border-radius: 10px;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .input-wrap input:focus {
          border-color: var(--signal);
          box-shadow: 0 0 0 3px var(--signal-glow);
        }
        .input-wrap input::placeholder { color: #565B65; }

        .submit-btn {
          background: var(--signal);
          color: #04140B;
          border: none;
          font-weight: 600;
          font-size: 13px;
          padding: 0 24px;
          border-radius: 10px;
          cursor: pointer;
          transition: background 0.2s, transform 0.2s;
          white-space: nowrap;
        }
        .submit-btn:hover:not(:disabled) { background: #5FFFB4; transform: translateY(-1px); }
        .submit-btn:disabled {
          background: var(--signal-dim);
          color: #567;
          cursor: not-allowed;
        }

        .suggestions {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 8px;
          margin-bottom: 28px;
        }
        .suggestions-label {
          font-size: 11px;
          color: var(--text-dim);
          letter-spacing: 0.06em;
        }
        .suggestion-chip {
          background: transparent;
          border: 1px solid var(--border);
          color: var(--text-dim);
          font-size: 11px;
          padding: 6px 12px;
          border-radius: 20px;
          cursor: pointer;
          transition: all 0.2s;
          max-width: 100%;
          text-align: left;
        }
        .suggestion-chip:hover:not(:disabled) {
          border-color: var(--signal);
          color: var(--signal);
          background: var(--signal-glow);
        }
        .suggestion-chip:disabled { opacity: 0.5; cursor: not-allowed; }
        .suggestion-chip.oos { border-style: dashed; }

        .result-block { animation: fade-up 0.4s ease both; }

        .answer-card {
          background: var(--panel);
          border: 1px solid var(--border);
          border-left: 3px solid var(--signal);
          border-radius: 10px;
          padding: 20px 22px;
          margin-bottom: 20px;
          font-size: 15px;
          line-height: 1.7;
          white-space: pre-wrap;
        }
        .answer-label {
          font-size: 11px;
          color: var(--signal);
          letter-spacing: 0.08em;
          text-transform: uppercase;
          margin-bottom: 12px;
        }
        .error-card { border-left-color: #EF4444; }
        .oos-card { border-left-color: #F59E0B; }
        .oos-card .answer-label { color: #F59E0B; }
        .error-title {
          color: #EF4444;
          font-size: 12px;
          margin-bottom: 8px;
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }
        .error-card code {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 12px;
          color: var(--signal);
        }

        .sources-heading {
          font-size: 11px;
          color: var(--text-dim);
          letter-spacing: 0.08em;
          text-transform: uppercase;
          margin-bottom: 12px;
        }
        .sources-list {
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 10px;
          overflow: hidden;
        }
        .source-item {
          display: flex;
          align-items: flex-start;
          gap: 14px;
          padding: 14px 18px;
          border-bottom: 1px solid var(--border);
          font-size: 13px;
          transition: background 0.15s;
        }
        .source-item:last-child { border-bottom: none; }
        .source-item:hover { background: var(--panel-hover); }
        .source-rank {
          color: var(--signal);
          font-size: 12px;
          min-width: 24px;
          padding-top: 2px;
        }
        .source-title { color: var(--text); font-weight: 500; margin-bottom: 4px; }
        .source-link {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          color: var(--text-dim);
          text-decoration: none;
          font-size: 12px;
          word-break: break-all;
          transition: color 0.2s;
        }
        .source-link:hover { color: var(--signal); }

        .empty-console {
          text-align: center;
          padding: 60px 20px;
          color: var(--text-dim);
          font-size: 14px;
        }
        .empty-console-icon {
          font-size: 32px;
          color: var(--signal);
          margin-bottom: 12px;
          opacity: 0.6;
        }
      `}</style>
    </div>
  )
}
