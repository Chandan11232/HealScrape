import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Radar from '../components/Radar'
import Navbar from '../components/Navbar'
import {
  Zap, GitBranch, Shield, ArrowRight,
  Wrench, BarChart3, BookOpen, Home,
} from 'lucide-react'

const DOMAINS = [
  'en.wikipedia.org', 'weather.com', 'docs.python.org', 'fastapi.tiangolo.com',
  'react.dev', 'techcrunch.com', 'theverge.com', 'venturebeat.com', 'openai.com',
  'devpost.com', 'remoteok.com', 'github.com', 'huggingface.co',
]

const STATS = [
  { value: '13', label: 'Studio collectors' },
  { value: '100%', label: 'Runs locally' },
  { value: '$0', label: 'Per query' },
  { value: '<8s', label: 'Avg response' },
]

const STEPS = [
  {
    num: '01 / INTERCEPT',
    icon: Zap,
    title: 'Scrape',
    desc: 'Custom collectors built in Bright Data Scraper Studio pull structured data from each target site — no generic library scrapers.',
  },
  {
    num: '02 / DECODE',
    icon: GitBranch,
    title: 'Embed',
    desc: 'Content is chunked and embedded locally with sentence-transformers, then stored in a persistent Chroma vector index.',
  },
  {
    num: '03 / TRANSMIT',
    icon: Shield,
    title: 'Answer',
    desc: 'Questions retrieve chunks from your Bright Data collectors (and live Open-Meteo for named-city weather). Off-topic prompts are refused.',
  },
]

const FEATURES = [
  {
    title: 'Self-Healing Collectors',
    desc: 'Unhealthy scrapes trigger Bright Data heal on the same collector ID, then re-scrape so downstream RAG keeps the same shape.',
    icon: Wrench,
    link: '/heal',
  },
  {
    title: 'Real-Time Monitoring',
    desc: 'Watch scraper health metrics before and after AI-powered fixes. Instant feedback on improvements.',
    icon: BarChart3,
  },
  {
    title: 'Citation-Based Answers',
    desc: 'Every answer includes sources so you know exactly where the data came from.',
    icon: BookOpen,
  },
  {
    title: 'Zero Cloud Dependency',
    desc: 'Everything runs locally. Your data stays on your machine. No recurring cloud bills.',
    icon: Home,
  },
]

const STACK = ['Bright Data', 'Ollama', 'ChromaDB', 'FastAPI', 'React']

export default function LandingEnhanced() {
  const [navSolid, setNavSolid] = useState(false)

  useEffect(() => {
    const onScroll = () => setNavSolid(window.scrollY > 40)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="landing">
      <Navbar variant={navSolid ? 'solid' : 'default'} />

      <section className="hero">
        <Radar />
        <div className="hero-content">
          <div className="eyebrow mono fade-up">13 sources · live · zero cost</div>
          <h1 className="mono fade-up fade-up-delay-1">
            THE WEB<br />
            IS <span className="glitch">TALKING.</span><br />
            WE&apos;RE LISTENING.
          </h1>
          <p className="hero-sub fade-up fade-up-delay-2">
            A RAG pipeline that scrapes real pages with Bright Data Scraper Studio,
            embeds them locally, and answers your questions with cited sources —
            no cloud LLM, no bill.
          </p>
          <div className="cta-row fade-up fade-up-delay-3">
            <Link to="/console" className="btn btn-primary">
              Launch console <ArrowRight size={16} />
            </Link>
            <a href="#how" className="btn btn-ghost">How it works</a>
          </div>

          <div className="hero-stats fade-up fade-up-delay-3">
            {STATS.map((s) => (
              <div className="stat-item" key={s.label}>
                <div className="stat-value mono">{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="strip">
        <div className="strip-track mono">
          {[...DOMAINS, ...DOMAINS].map((d, i) => (
            <span className="strip-item" key={i}>{d}</span>
          ))}
        </div>
      </div>

      <section className="section" id="how">
        <div className="section-eyebrow mono">Pipeline</div>
        <div className="section-title mono">From raw page to cited answer</div>
        <div className="steps">
          {STEPS.map((s) => {
            const Icon = s.icon
            return (
              <div className="step" key={s.num}>
                <div className="step-icon"><Icon size={22} /></div>
                <div className="step-num mono">{s.num}</div>
                <div className="step-title">{s.title}</div>
                <div className="step-desc">{s.desc}</div>
              </div>
            )
          })}
        </div>
      </section>

      <section className="section features-section">
        <div className="section-eyebrow mono">Capabilities</div>
        <div className="section-title mono">What makes this different</div>
        <div className="features-grid">
          {FEATURES.map((f, i) => {
            const Icon = f.icon
            const inner = (
              <>
                <div className="feature-icon"><Icon size={24} /></div>
                <div className="feature-title">{f.title}</div>
                <div className="feature-desc">{f.desc}</div>
                {f.link && (
                  <div className="feature-arrow"><ArrowRight size={16} /></div>
                )}
              </>
            )
            return f.link ? (
              <Link key={i} to={f.link} className="feature-card clickable">
                {inner}
              </Link>
            ) : (
              <div key={i} className="feature-card">
                {inner}
              </div>
            )
          })}
        </div>
      </section>

      <section className="heal-spotlight">
        <div className="heal-content">
          <div className="heal-badge mono">Featured · Hackathon Demo</div>
          <h2 className="mono">Scraper Self-Heal Lab</h2>
          <p className="heal-desc">
            Watch a collector scrape, get scored, and — if extraction is empty —
            Bright Data heals the same <code>c_*</code> ID and we re-scrape. Nothing
            downstream changes except the data quality.
          </p>
          <div className="heal-benefits">
            {['Same collector ID after heal', 'Real before/after scrape metrics', 'Auto-heal when extraction fails', 'Job tracking & history'].map((b) => (
              <div className="benefit" key={b}>
                <span className="benefit-check">✓</span>
                <span>{b}</span>
              </div>
            ))}
          </div>
          <Link to="/heal" className="btn btn-primary">
            Go to Heal Lab <ArrowRight size={16} />
          </Link>
        </div>
        <div className="heal-visual">
          <div className="heal-card">
            <div className="heal-card-header mono">Live metrics preview</div>
            <div className="heal-stat">
              <div className="heal-label">Empty Titles</div>
              <div className="heal-before">100%</div>
              <div className="heal-arrow">↓</div>
              <div className="heal-after">24%</div>
            </div>
            <div className="heal-stat">
              <div className="heal-label">Success Rate</div>
              <div className="heal-before">45%</div>
              <div className="heal-arrow">↑</div>
              <div className="heal-after">89%</div>
            </div>
            <div className="heal-card-footer mono">AI-healed in 12s</div>
          </div>
        </div>
      </section>

      <section className="footer-cta">
        <h2 className="mono">Ready to ask?</h2>
        <p>Launch the console and ask the collectors — not the open web.</p>
        <Link to="/console" className="btn btn-primary">
          Launch console <ArrowRight size={16} />
        </Link>
      </section>

      <footer className="site-footer">
        <div className="footer-stack">
          {STACK.map((s) => (
            <span className="stack-pill" key={s}>{s}</span>
          ))}
        </div>
        <p className="footer-copy mono">SIGNAL — Built for the Bright Data hackathon</p>
      </footer>

      <style>{`
        .landing { position: relative; }

        .hero {
          position: relative;
          min-height: 100vh;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 100px 20px 60px;
          text-align: center;
          overflow: hidden;
        }
        .hero-content { position: relative; z-index: 2; max-width: 760px; }
        .eyebrow {
          font-size: 12px;
          letter-spacing: 0.2em;
          color: var(--signal);
          text-transform: uppercase;
          margin-bottom: 20px;
        }
        .eyebrow::before { content: '● '; }
        h1 {
          font-weight: 700;
          font-size: clamp(40px, 8vw, 84px);
          line-height: 0.98;
          letter-spacing: -0.02em;
          margin-bottom: 22px;
        }
        .hero-sub {
          font-size: 17px;
          color: var(--text-dim);
          max-width: 520px;
          margin: 0 auto 36px;
          line-height: 1.6;
        }
        .cta-row { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; margin-bottom: 48px; }

        .hero-stats {
          display: flex;
          gap: 1px;
          background: var(--border);
          border: 1px solid var(--border);
          border-radius: 10px;
          overflow: hidden;
          max-width: 520px;
          margin: 0 auto;
        }
        .stat-item {
          flex: 1;
          background: var(--panel);
          padding: 16px 12px;
          text-align: center;
        }
        .stat-value {
          font-size: 22px;
          font-weight: 700;
          color: var(--signal);
          margin-bottom: 4px;
        }
        .stat-label {
          font-size: 11px;
          color: var(--text-dim);
          text-transform: uppercase;
          letter-spacing: 0.06em;
        }

        .strip {
          border-top: 1px solid var(--border);
          border-bottom: 1px solid var(--border);
          padding: 18px 0;
          overflow: hidden;
        }
        .strip-track {
          display: flex;
          gap: 48px;
          white-space: nowrap;
          animation: scroll 22s linear infinite;
          width: max-content;
        }
        @keyframes scroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
        .strip-item { font-size: 13px; color: var(--text-dim); }
        .strip-item::before { content: '// '; color: var(--signal); }

        .section { max-width: 920px; margin: 0 auto; padding: 100px 24px; }
        .section-eyebrow {
          font-size: 12px;
          color: var(--signal);
          letter-spacing: 0.15em;
          text-transform: uppercase;
          margin-bottom: 12px;
        }
        .section-title {
          font-size: clamp(28px, 4vw, 42px);
          font-weight: 600;
          margin-bottom: 60px;
          letter-spacing: -0.01em;
        }

        .steps {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 1px;
          background: var(--border);
          border: 1px solid var(--border);
          border-radius: 10px;
          overflow: hidden;
        }
        .step {
          background: var(--void);
          padding: 32px 28px;
          transition: background 0.2s;
        }
        .step:hover { background: var(--panel); }
        .step-icon {
          width: 44px;
          height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--signal-glow);
          border: 1px solid rgba(57, 255, 158, 0.2);
          border-radius: 8px;
          color: var(--signal);
          margin-bottom: 16px;
        }
        .step-num { font-size: 13px; color: var(--alert); margin-bottom: 12px; }
        .step-title { font-size: 17px; font-weight: 600; margin-bottom: 10px; }
        .step-desc { font-size: 14px; color: var(--text-dim); line-height: 1.6; }

        .features-section { padding: 80px 24px; }
        .features-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 16px;
        }
        .feature-card {
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 28px;
          text-decoration: none;
          transition: all 0.25s;
          position: relative;
          color: inherit;
        }
        .feature-card:hover {
          transform: translateY(-3px);
          border-color: rgba(57, 255, 158, 0.4);
          box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
        }
        .feature-card.clickable { cursor: pointer; }
        .feature-icon {
          width: 44px;
          height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--signal-glow);
          border-radius: 8px;
          color: var(--signal);
          margin-bottom: 16px;
        }
        .feature-title { font-size: 17px; font-weight: 600; margin-bottom: 10px; }
        .feature-desc { font-size: 14px; color: var(--text-dim); line-height: 1.6; }
        .feature-arrow {
          position: absolute;
          top: 20px;
          right: 20px;
          color: var(--signal);
          opacity: 0;
          transition: opacity 0.2s, transform 0.2s;
        }
        .feature-card:hover .feature-arrow { opacity: 1; transform: translateX(3px); }

        .heal-spotlight {
          max-width: 1200px;
          margin: 0 auto;
          padding: 80px 24px;
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 60px;
          align-items: center;
          border-top: 1px solid var(--border);
        }
        .heal-badge {
          display: inline-block;
          background: var(--signal-glow);
          color: var(--signal);
          padding: 6px 12px;
          border-radius: 4px;
          font-size: 11px;
          margin-bottom: 16px;
          border: 1px solid rgba(57, 255, 158, 0.2);
        }
        .heal-content h2 {
          font-size: clamp(28px, 4vw, 42px);
          margin-bottom: 20px;
          letter-spacing: -0.01em;
        }
        .heal-desc {
          font-size: 15px;
          color: var(--text-dim);
          line-height: 1.7;
          margin-bottom: 24px;
        }
        .heal-benefits { display: flex; flex-direction: column; gap: 12px; margin-bottom: 32px; }
        .benefit { display: flex; align-items: center; gap: 10px; font-size: 14px; }
        .benefit-check { color: var(--signal); font-weight: 700; }
        .heal-visual { display: flex; align-items: center; justify-content: center; }
        .heal-card {
          background: var(--panel);
          border: 1px solid var(--border);
          border-left: 3px solid var(--signal);
          border-radius: 12px;
          padding: 28px;
          width: 100%;
          max-width: 340px;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
        }
        .heal-card-header {
          font-size: 11px;
          color: var(--text-dim);
          letter-spacing: 0.08em;
          text-transform: uppercase;
          margin-bottom: 20px;
          padding-bottom: 12px;
          border-bottom: 1px solid var(--border);
        }
        .heal-stat {
          display: grid;
          grid-template-columns: 1fr auto 1fr;
          align-items: center;
          gap: 12px;
          margin-bottom: 20px;
        }
        .heal-label {
          font-size: 12px;
          color: var(--text-dim);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          grid-column: 1 / -1;
          margin-bottom: 4px;
        }
        .heal-before { text-align: center; font-size: 22px; font-weight: 700; color: #EF4444; }
        .heal-arrow { text-align: center; color: var(--signal); font-weight: 600; font-size: 18px; }
        .heal-after { text-align: center; font-size: 22px; font-weight: 700; color: var(--signal); }
        .heal-card-footer {
          font-size: 11px;
          color: var(--signal);
          text-align: center;
          margin-top: 8px;
          padding-top: 12px;
          border-top: 1px solid var(--border);
        }

        .footer-cta {
          text-align: center;
          padding: 100px 24px;
          border-top: 1px solid var(--border);
        }
        .footer-cta h2 {
          font-size: clamp(28px, 5vw, 48px);
          margin-bottom: 12px;
          letter-spacing: -0.01em;
        }
        .footer-cta p { font-size: 15px; color: var(--text-dim); margin-bottom: 28px; }

        @media (max-width: 900px) {
          .heal-spotlight { grid-template-columns: 1fr; gap: 40px; }
        }
        @media (max-width: 720px) {
          .steps { grid-template-columns: 1fr; }
          .section { padding: 60px 20px; }
          .hero-stats { flex-wrap: wrap; }
          .stat-item { min-width: 45%; }
        }
      `}</style>
    </div>
  )
}
