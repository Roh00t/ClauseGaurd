# ClauseGuard

**Your AI employment rights officer — built for Singapore employees.**

Upload your employment contract. Get a plain-English explanation of what it
actually means, what's risky, and what to do next. Free for your first analysis.

---

## For Users

### What ClauseGuard does

- Reads your employment contract and explains it in plain English
- Flags risky clauses with clear severity ratings (Critical, Serious, Moderate)
- Drafts a ready-to-send dispute letter to MOM or TADM if you have a problem
- Answers follow-up questions after your analysis

### Three modes — pick what fits your situation

| Mode | When to use it |
|---|---|
| **Reviewing a contract before signing** | You've received a job offer and want to understand what you're agreeing to |
| **Leaving my job** | You're resigning or being let go and want to know your rights |
| **I have a dispute** | Something went wrong and you need help understanding your options |

### Step-by-step guide

1. **Go to the app** at [clauseguard.onrender.com](https://clauseguard.onrender.com)
2. **Pick your mode** — choose one of the three buttons at the top
3. **Upload your contract** — drag and drop your PDF into the first panel
4. **Add context (optional)** — if you have a dispute, upload any supporting
   documents (letters, forms) in the second panel
5. **Click "Analyse Everything"** — takes about 45-90 seconds
6. **Read your results** — you'll see a plain-English summary first.
   Click "See full analysis" for the detailed legal breakdown
7. **Ask follow-up questions** — type any question in the chat box below
   the results

### Privacy

Your contract is never stored on our servers. It's analysed and immediately
discarded. Your session history stays in your own browser only.

[Read our full Privacy Policy →](/tos)

### Accounts and pricing

| | Free | Pay-per-use | Pro |
|---|---|---|---|
| Analyses | 1 | S$2.99 / 3 analyses | Unlimited |
| Full report download | — | — | ✓ |
| Pricing | Free | Coming soon | Coming soon |

No account needed for your first free analysis. Create an account to save
your history and access paid features.

---

## For Developers

### What you need

- Python 3.13 (not 3.11 or 3.12 — must be exactly 3.13)
- Git

### Clone and set up

```bash
git clone https://github.com//agentforgehackathon.git
cd agentforgehackathon
```

### Environment variables

Copy the example file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` and fill in:
TOKENROUTER_API_KEY=      # LLM provider — get from tokenrouter.ai

DAYTONA_API_KEY=          # PII redaction sandbox

TERMINAL3_API_KEY=        # Attestation service

TERMINAL3_DID=            # Your Terminal 3 DID

BRIGHTDATA_API_KEY=       # MOM regulation scraper
SUPABASE_URL=             # From Supabase project settings

SUPABASE_PUBLISHABLE_KEY= # Anon/public key (safe to expose)

SUPABASE_SECRET_KEY=      # Service role key (never expose publicly)

SUPABASE_JWKS_URL=        # From Supabase project settings
POSTHOG_PROJECT_TOKEN=    # From PostHog project settings

POSTHOG_HOST=             # https://us.i.posthog.com or EU equivalent

### Install dependencies

```bash
python3.13 -m pip install -r requirements.txt --break-system-packages
```

### Run locally

```bash
python3.13 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

### Run tests

```bash
CLAUSEGUARD_DISABLE_ANALYTICS=1 \
CLAUSEGUARD_TEST_BUDGET=180 \
python3.13 -m pytest tests/test_backend.py -v
```

Expected: 33-34/34 passing. One known intermittent failure
(`test_three_sequential_analyses`) is a latency threshold issue —
not a correctness bug.

### Project structure
backend/

main.py           — FastAPI routes, rate limiting, auth middleware

analyzer.py       — LLM prompt logic, mode-aware analysis, ELI5

entity_map.py     — PII redaction pipeline

report_generator.py — DOCX report generation

supabase_client.py  — Auth and metadata storage (Supabase)

scraper.py        — MOM regulation fetcher (Bright Data)
frontend/

index.html        — Main app (vanilla JS, no build step)

auth.js           — Supabase auth client

db.js             — IndexedDB session storage

i18n.js           — EN/MS/TL translations

tos.html          — Privacy Policy and Terms

about.html        — About page

pricing.html      — Pricing page

support.html      — Support page
tests/

test_backend.py   — 34 automated backend tests (real LLM calls)
sample_data/        — Synthetic test fixtures (no real PII)

### Architecture notes

- **No build step.** Frontend is vanilla JS, served directly by FastAPI.
  No React, no npm, no webpack.
- **Sessions stay in the browser.** User analysis data lives in IndexedDB —
  never stored server-side. Supabase stores only account metadata
  (email, tier, usage count).
- **Always use `python3.13` explicitly.** `python3` on this machine resolves
  to a different version.

### Deploy to Render

Connect your GitHub repo to [render.com](https://render.com). The
`render.yaml` in the root handles the rest automatically. After the first
deploy, set two things manually:

1. In **Render dashboard → Environment**: set `ALLOWED_ORIGINS` to your
   Render URL (e.g. `https://clauseguard.onrender.com`)
2. In **Supabase dashboard → Authentication → URL Configuration**: add
   your Render URL as both the Site URL and a Redirect URL

---

## Built with

FastAPI · Supabase · Bright Data · Daytona · TokenRouter · Terminal 3 · PostHog

Not legal advice. Always consult a qualified lawyer for your specific situation.
