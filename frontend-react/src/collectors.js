/**
 * Mirrors backend app/scrapers/catalog.py — keep in sync with INDEXED_SOURCES.
 */

export const INDEXED_SOURCES = [
  {
    domain: 'en.wikipedia.org',
    scraper_name: 'wikipedia_ai',
    kind: 'encyclopedia',
    example_url: 'https://en.wikipedia.org/wiki/Artificial_intelligence',
    radarLabel: 'en.wikipedia.org',
  },
  {
    domain: 'fastapi.tiangolo.com',
    scraper_name: 'tiangolo',
    kind: 'docs',
    example_url: 'https://fastapi.tiangolo.com/tutorial/dependencies/',
    radarLabel: 'fastapi.tiangolo.com',
  },
  {
    domain: 'react.dev',
    scraper_name: 'react',
    kind: 'docs',
    example_url: 'https://react.dev/reference/rsc/server-components',
    radarLabel: 'react.dev',
  },
  {
    domain: 'docs.python.org',
    scraper_name: 'python_docs',
    kind: 'docs',
    example_url: 'https://docs.python.org/3/tutorial/introduction.html',
    radarLabel: 'docs.python.org',
  },
  {
    domain: 'openai.com',
    scraper_name: 'openai',
    kind: 'blog',
    example_url: 'https://openai.com/index/chatgpt/',
    radarLabel: 'openai.com',
  },
  {
    domain: 'devpost.com',
    scraper_name: 'devpost',
    kind: 'listings',
    example_url: 'https://devpost.com/software',
    radarLabel: 'devpost.com',
  },
  {
    domain: 'github.com',
    scraper_name: 'github_readme',
    kind: 'code',
    example_url: 'https://github.com/fastapi/fastapi',
    radarLabel: 'github.com',
  },
  {
    domain: 'developer.mozilla.org',
    scraper_name: 'mdn_web',
    kind: 'docs',
    example_url: 'https://developer.mozilla.org/en-US/docs/Web/JavaScript',
    radarLabel: 'developer.mozilla.org',
  },
  {
    domain: 'docs.docker.com',
    scraper_name: 'docker_intro',
    kind: 'docs',
    example_url:
      'https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-a-container/',
    radarLabel: 'docs.docker.com',
  },
  {
    domain: 'docs.stripe.com',
    scraper_name: 'stripe_docs',
    kind: 'docs',
    example_url: 'https://docs.stripe.com/api/charges',
    radarLabel: 'docs.stripe.com',
  },
  {
    domain: 'en.wikipedia.org',
    scraper_name: 'wiki_javascript',
    kind: 'encyclopedia',
    example_url: 'https://en.wikipedia.org/wiki/JavaScript',
    radarLabel: 'wiki · javascript',
  },
  {
    domain: 'www.anthropic.com',
    scraper_name: 'anthropic_news',
    kind: 'blog',
    example_url: 'https://www.anthropic.com/news/claude-3-family',
    radarLabel: 'anthropic.com',
  },
  {
    domain: 'www.sqlite.org',
    scraper_name: 'sqlite_docs',
    kind: 'docs',
    example_url: 'https://www.sqlite.org/lang_select.html',
    radarLabel: 'sqlite.org',
  },
]

export const INDEXED_DOMAINS = [
  ...new Set(INDEXED_SOURCES.map((s) => s.domain)),
]

/** Evenly spaced positions for the landing-page radar (13 nodes). */
const RADAR_POSITIONS = [
  { top: '10%', left: '50%' },
  { top: '14.6%', left: '68.6%' },
  { top: '27.3%', left: '82.9%' },
  { top: '45.2%', left: '89.7%' },
  { top: '64.2%', left: '87.4%' },
  { top: '80%', left: '76.5%' },
  { top: '88.8%', left: '59.6%' },
  { top: '88.8%', left: '40.4%' },
  { top: '80%', left: '23.5%' },
  { top: '64.2%', left: '12.6%' },
  { top: '45.2%', left: '10.3%' },
  { top: '27.3%', left: '17.1%' },
  { top: '14.6%', left: '31.4%' },
]

export const RADAR_SOURCES = INDEXED_SOURCES.map((source, index) => ({
  name: source.radarLabel || source.domain,
  scraper_name: source.scraper_name,
  ...RADAR_POSITIONS[index],
}))

export const IN_SCOPE_EXAMPLES = [
  'How does dependency injection work in FastAPI?',
  'What is Depends used for in FastAPI?',
  'What does the scraped Python docs say about the list type?',
  'What are React Server Components, according to the scraped react.dev pages?',
  'What is artificial intelligence, according to Wikipedia?',
  'What is JavaScript, according to the scraped Wikipedia article?',
  'What is a container, according to the scraped Docker docs?',
  'What does the scraped Stripe API docs say about charges?',
  'What does MDN say about JavaScript on the scraped page?',
  'What did the scraped OpenAI pages say about ChatGPT?',
]

export const OUT_OF_SCOPE_EXAMPLES = ['Who won the World Cup?']

export const SCRAPER_URL_HINTS = Object.fromEntries(
  INDEXED_SOURCES.map((s) => [s.scraper_name, s.example_url]),
)
