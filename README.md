# ClauseGuard

**AI-powered employment dispute analyser for Singapore employees.**

ClauseGuard reads your employment contracts and dispute communications, checks them against live MOM regulations, identifies every red flag, and delivers a neutral verdict on who is responsible — along with a ready-to-send MOM complaint draft.

Built in under 8 hours at **Agent Forge Hackathon 2026**.

---

## The Problem

Singapore employees facing employment disputes are at a structural disadvantage. Most do not have legal training, cannot afford a lawyer for an initial assessment, and do not know where to start. Common scenarios include:

- An employer demanding bond repayment when a fixed-term contract simply expires — not realising that contract expiry is not resignation and the bond trigger never fired
- A training bond imposed via an internal HR form the employee never signed — and being told it is legally enforceable
- An ambiguous contract clause written as "6 or 12 months" with no specification — and the employer choosing the interpretation that costs the employee the most
- A meeting with five HR staff called without notice to present financial demands — with no written record of what was actually said

Each of these scenarios has a clear answer in Singapore employment law. But without access to that knowledge, employees either capitulate, pay money they do not owe, or spend weeks navigating MOM and TADM without knowing whether their case is strong.

ClauseGuard closes that gap.

---

## What ClauseGuard Does

Upload your employment documents and dispute communications. ClauseGuard does the rest:

1. **Validates and extracts** text from every uploaded PDF, TXT, or EML file
2. **Scrapes and caches** current regulations from `mom.gov.sg/employment-practices` via Bright Data — so the analysis reflects actual MOM rules, not training data that may be months old
3. **Redacts your PII** (NRIC, addresses, phone numbers) before sending anything to the LLM — then re-injects real values into the final MOM draft only
4. **Runs a combined AI analysis** producing both a red-flag report and a dispute judgment in a single pass
5. **Renders a structured report** with severity-coded red flags, MOM citations, legal arguments, recommended actions, and an exit documentation checklist
6. **Delivers a dispute verdict** — Employer At Fault / Employee At Fault / Both / Insufficient Information — with confidence rating and full reasoning
7. **Generates a draft complaint letter** addressed to MOM or TADM, ready to copy and send

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Claude-like dark UI)               │
│                                                                     │
│  ┌──────────────────────────┐  ┌──────────────────────────────────┐ │
│  │  Panel A                 │  │  Panel B                         │ │
│  │  Employment Documents    │  │  Dispute Context (optional)      │ │
│  │  PDF only                │  │  PDF · TXT · EML                 │ │
│  │  LOA, contracts,         │  │  Emails, WhatsApp exports,       │ │
│  │  training forms          │  │  dispute records                 │ │
│  └────────────┬─────────────┘  └──────────────┬───────────────────┘ │
│               └──────────────┬─────────────────┘                    │
│                        [ Analyse Everything ]                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │  POST /api/analyze
                             │  FormData: contract_files + context_files
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND                              │
│                                                                     │
│  ① Security Layer (security.py)                                     │
│     • File count: max 10 total (Panel A + Panel B combined)         │
│     • File size: max 15MB per file                                  │
│     • Magic bytes: %PDF- for PDFs, UTF-8 decode for TXT/EML        │
│     • Rate limit: 5 requests/minute per IP (slowapi)               │
│     • Path traversal: filenames used as display strings only        │
│                                                                     │
│  ② Extraction Layer (extractor.py)                                  │
│     • PDF → pdfplumber → structured text per page                  │
│     • TXT/EML → UTF-8 decode → stripped plain text                 │
│     • Empty/scanned documents → 422 with clear message             │
│                                                                     │
│  ③ PII Redaction (redactor.py)                                      │
│     • Regex patterns: NRIC, SG phone numbers, addresses, emails    │
│     • Replaced with typed placeholders: [NRIC], [PHONE], [ADDRESS] │
│     • Restoration map stored for re-injection into MOM draft only  │
│                                                                     │
│  ④ Regulation Cache (scraper.py → data/data.db)                    │
│     • Bright Data CLI: bdata scrape <url> --format text            │
│     • Fallback: requests + BeautifulSoup                           │
│     • Fallback: hardcoded Singapore employment law KB              │
│     • Cache duration: 7 days — never returns 0 regulations        │
│                                                                     │
│  ⑤ Combined Analysis (analyzer.py)                                  │
│     • Single LLM call — returns analysis + judgment in one JSON    │
│     • System prompt: Singapore law rules + injection defence       │
│     • UNTRUSTED_DOCUMENT wrapping on all user content              │
│     • Enum normalisation: all values uppercased before storage     │
│     • Timeout: 90 seconds                                          │
│                                                                     │
│  ⑥ Session Storage (db.py → data/data.db)                          │
│     • Tables: regulations · sessions · scrape_log                  │
│     • Sessions: analysis JSON + judgment JSON + verdict + severity  │
│     • Safe migration: migrate_db() catches only duplicate-column   │
│                                                                     │
└────────────────────┬─────────────────────────────────────────────── ┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SINGLE LLM CALL                              │
│                   Anthropic claude-sonnet-4-6                       │
│              (fallback: TokenRouter / Kimi K2.6)                    │
│                                                                     │
│  Input:  MOM regulations + [REDACTED] employment docs              │
│          + [REDACTED] dispute context (if provided)                │
│                                                                     │
│  Output: {                                                          │
│    "analysis": {                                                    │
│       executive_summary, overall_severity,                          │
│       documents_analyzed, red_flags[],                              │
│       legal_arguments[], recommended_actions[],                     │
│       exit_checklist[], mom_report_draft                            │
│    },                                                               │
│    "judgment": {                                                    │
│       verdict, confidence, dispute_summary,                         │
│       verdict_reasoning, employer_conduct,                          │
│       employee_conduct, key_evidence,                               │
│       recommended_forum, forum_reasoning                            │
│    }                                                                │
│  }                                                                  │
└─────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PII RESTORATION (redactor.py)                    │
│  Real NRIC/address re-injected into MOM draft letter ONLY          │
│  All other sections stay redacted                                   │
└─────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RENDERED OUTPUT (UI)                           │
│                                                                     │
│  ① Dispute Judgment (top — headline finding)                        │
│     EMPLOYER AT FAULT ●●● HIGH CONFIDENCE (green)                  │
│     OR EMPLOYEE AT FAULT ●●● HIGH (red)                            │
│     OR BOTH AT FAULT ●●○ MEDIUM (yellow)                           │
│     OR INSUFFICIENT INFORMATION ●○○ LOW (grey)                     │
│     + Employer conduct breakdown / Employee conduct breakdown       │
│     + Key evidence / Recommended forum                             │
│                                                                     │
│  ② Documents Analysed                                               │
│     Filename · Type · Signed/Unsigned · Key facts                  │
│                                                                     │
│  ③ Red Flags (expandable cards, severity-coded)                     │
│     CRITICAL (red) · SERIOUS (orange) · MODERATE (yellow)          │
│     Each: clause reference · issue · MOM regulation · impact       │
│                                                                     │
│  ④ Legal Arguments                                                  │
│     STRONG / MODERATE / WEAK strength badges                       │
│                                                                     │
│  ⑤ Recommended Actions                                              │
│     Priority-ordered · Channel tags: MOM/TADM/TAFEP/Pro Bono      │
│                                                                     │
│  ⑥ Exit Documentation Checklist                                     │
│                                                                     │
│  ⑦ MOM/TADM Draft Letter                                            │
│     ⚠ PII warning banner · Copy button · Real NRIC restored        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Workflows

### Workflow 1 — First-time Regulation Load

```
App starts
    │
    ▼
init_db() + migrate_db()
    │
    ▼
GET /api/regulations
    │
    ├── data/data.db has fresh data (< 7 days old)? → return cached
    │
    ├── No/stale → try: bdata scrape mom.gov.sg/employment-practices
    │                       bdata scrape .../fixed-term-contract
    │                       bdata scrape .../employment-contract
    │                       bdata scrape .../salary
    │                       bdata scrape .../termination-of-employment
    │
    ├── bdata fails → try: requests + BeautifulSoup fallback
    │
    └── all fail → load hardcoded Singapore employment law KB
                   (5 regulation entries always guaranteed)
                   ← app NEVER returns 0 regulations
```

### Workflow 2 — Document Analysis

```
User uploads files
    │
    ├── Panel A: Employment Documents (PDF required)
    └── Panel B: Dispute Context (PDF / TXT / EML optional)
                         │
                         ▼
              Security validation
              ┌─────────────────────────────────────┐
              │ • Total file count ≤ 10              │
              │ • Panel A not empty (400 if empty)   │
              │ • Per-file size ≤ 15MB               │
              │ • PDF: magic bytes %PDF- check       │
              │ • TXT/EML: UTF-8 decode check        │
              │ • Filename: display-only, no FS use  │
              └──────────────┬──────────────────────┘
                             │
                             ▼
              Text extraction (pdfplumber / UTF-8 decode)
              Filter: empty-text files → logged as errors, excluded
              Deduplication: MD5 hash — same file in both panels → one copy
                             │
                             ▼
              PII Redaction
              ┌─────────────────────────────────────┐
              │ NRIC:    T0174455G → [NRIC]          │
              │ Phone:   9123 4567 → [PHONE]         │
              │ Address: Blk 318 … → [ADDRESS]       │
              │ Email:   user@x.com → [EMAIL]        │
              │ Restoration map stored for later     │
              └──────────────┬──────────────────────┘
                             │
                             ▼
              MOM regulations loaded from data/data.db
                             │
                             ▼
              Single LLM call (90s timeout)
              System prompt: SG law rules + injection defence
              User message:  redacted docs + regulations
                             │
                             ▼
              Parse + normalise JSON response
              ┌─────────────────────────────────────┐
              │ Uppercase all enum values            │
              │ Validate verdict ∈ valid set         │
              │ Validate severity ∈ valid set        │
              │ Check both "analysis" + "judgment"   │
              │ keys present                         │
              └──────────────┬──────────────────────┘
                             │
                             ▼
              PII restoration → MOM draft letter only
                             │
                             ▼
              Save session to data/data.db
              Return JSON response to browser
```

### Workflow 3 — Dispute Judgment Logic

```
LLM receives:
    • Employment documents (what the contract says)
    • Dispute context (what actually happened)
    • MOM regulations (what the law says)
    • Red flags already identified (cross-reference check)

LLM applies:
    1. Fixed-term expiry ≠ resignation rule
    2. Unsigned document rule
    3. Contra proferentem (ambiguous = against drafter)
    4. Training delay equity principle
    5. IMDA CLT grant recovery trigger list
    6. Cross-validation: verdict must be consistent with red flags

Possible verdicts:
    EMPLOYER_AT_FAULT       → employer acted outside contractual rights
    EMPLOYEE_AT_FAULT       → employee breached clear, signed obligations
    BOTH_AT_FAULT           → both contributed to the dispute
    INSUFFICIENT_INFORMATION → not enough context to decide fairly

Output per verdict:
    • dispute_summary (what this is actually about)
    • verdict_reasoning (specific document citations)
    • employer_conduct: { problematic[], defensible[] }
    • employee_conduct: { problematic[], defensible[] }
    • key_evidence (3–5 decisive items)
    • contradictions_noted (if verdict tensions with red flags)
    • what_would_change_verdict
    • recommended_forum + forum_reasoning
```

---

## Tools & Technologies

| Layer | Tool | Purpose |
|-------|------|---------|
| **Backend framework** | FastAPI 0.115 | REST API, async file handling, automatic OpenAPI docs at `/docs` |
| **Primary LLM** | Anthropic claude-sonnet-4-6 | Combined analysis + judgment — single call |
| **Fallback LLM** | TokenRouter / Kimi K2.6 | OpenAI-compatible fallback if Anthropic unavailable |
| **Web scraper** | Bright Data CLI (`bdata scrape`) | Scrapes `mom.gov.sg` handling bot protection |
| **Scraper fallback** | requests + BeautifulSoup4 | Plain HTTP fallback if bdata unavailable |
| **PDF extraction** | pdfplumber 0.11.4 | Page-level text extraction from PDFs |
| **Database** | SQLite (`data/data.db`) | Regulations cache + session storage + scrape log |
| **Rate limiting** | slowapi | 5 requests/minute per IP on `/api/analyze` |
| **PII handling** | Custom regex redactor | Singapore-specific: NRIC, SG phone, addresses, emails |
| **Runtime** | Python 3.13 (Homebrew) | `python3` — not system Python |
| **Frontend** | Vanilla HTML/CSS/JS | Zero build toolchain. Single file. Claude-inspired dark UI |
| **Server** | uvicorn | ASGI server, serves both API and frontend |
| **Testing** | pytest + FastAPI TestClient | 19+ automated backend tests |

---

## Project Structure

```
clauseguard-v2/
│
├── backend/
│   ├── __init__.py          # Module marker — required for imports to work
│   ├── main.py              # FastAPI app, all routes, request/response handling
│   ├── db.py                # SQLite connection, init_db(), migrate_db()
│   ├── scraper.py           # MOM regulation scraper + SQLite cache
│   ├── extractor.py         # PDF + TXT/EML text extraction router
│   ├── analyzer.py          # Single combined LLM call, JSON parsing, enum normalisation
│   ├── security.py          # File validation, size limits, sanitise_for_llm()
│   └── redactor.py          # PII scrubbing + restoration for MOM draft
│
├── frontend/
│   └── index.html           # Complete UI — dark theme, dual panels, judgment renderer
│
├── data/
│   ├── data.db              # SQLite — regulations + sessions + scrape_log
│   └── .gitkeep
│
├── tests/
│   └── test_backend.py      # Automated stress tests (health, validation, security, perf)
│
├── .env.example             # API key template
├── .gitignore
├── requirements.txt
├── start.sh                 # One-command startup
├── CLAUDE_CODE_PROMPT.md    # Build brief (Pre-Mortem / Steelman / Red Team applied)
├── AMENDMENT_PROMPT.md      # Hardened amendment brief for dual-panel + judgment
└── STRESS_TEST.md           # Full test plan — automated + Cowork UI prompts
```

---

## Database Schema

All data in a single `data/data.db` file.

```sql
-- MOM regulations (scraped from mom.gov.sg, cached 7 days)
CREATE TABLE regulations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT NOT NULL UNIQUE,
    title       TEXT,
    content     TEXT,      -- max 12,000 chars per entry
    category    TEXT,      -- 'Fixed-Term Contracts', 'Salary', etc.
    scraped_at  TEXT       -- ISO 8601 timestamp
);

-- Analysis sessions
CREATE TABLE sessions (
    id                  TEXT PRIMARY KEY,   -- 8-char hex
    created_at          TEXT,
    filenames           TEXT,               -- JSON array (Panel A)
    context_filenames   TEXT,               -- JSON array (Panel B)
    doc_count           INTEGER,
    context_doc_count   INTEGER,
    overall_severity    TEXT,               -- CRITICAL|SERIOUS|MODERATE
    verdict             TEXT,               -- EMPLOYER_AT_FAULT|...
    analysis            TEXT,               -- full analysis JSON
    judgment            TEXT,               -- full judgment JSON
    regulation_source   TEXT                -- scraped|cache|fallback_kb
);

-- Scrape audit log
CREATE TABLE scrape_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT,
    status      TEXT,    -- ok|failed|cached
    method      TEXT,    -- bdata|requests|fallback
    chars       INTEGER,
    scraped_at  TEXT
);
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves `frontend/index.html` |
| `GET` | `/health` | `{"status": "ok", "ts": "..."}` |
| `GET` | `/api/regulations` | Returns cached MOM regulations (scrapes if stale) |
| `POST` | `/api/analyze` | Main endpoint — accepts `contract_files` + `context_files` |
| `GET` | `/api/sessions` | Returns last 30 sessions (id, date, files, verdict, severity) |
| `GET` | `/api/session/{id}` | Returns full session including analysis + judgment JSON |

### POST /api/analyze

**Request:** `multipart/form-data`
- `contract_files` — one or more PDF files (required, min 1)
- `context_files` — zero or more PDF/TXT/EML files (optional)

**Validation rules:**
- Total file count ≤ 10
- Per-file size ≤ 15MB
- PDF files: magic bytes `%PDF-` required
- TXT/EML files: UTF-8 or latin-1 decodable

**Response:**
```json
{
  "session_id": "a3f9c821",
  "docs_processed": 3,
  "context_docs_processed": 2,
  "extraction_errors": [],
  "regulation_source": "cache",
  "analysis": {
    "executive_summary": "...",
    "overall_severity": "CRITICAL",
    "documents_analyzed": [...],
    "red_flags": [...],
    "legal_arguments": [...],
    "recommended_actions": [...],
    "exit_checklist": [...],
    "mom_report_draft": {
      "subject": "...",
      "to": "MOM Contact Centre",
      "body": "..."
    }
  },
  "judgment": {
    "verdict": "EMPLOYER_AT_FAULT",
    "confidence": "HIGH",
    "dispute_summary": "...",
    "verdict_reasoning": "...",
    "employer_conduct": {
      "problematic": [...],
      "defensible": [...]
    },
    "employee_conduct": {
      "problematic": [...],
      "defensible": [...]
    },
    "key_evidence": [...],
    "contradictions_noted": null,
    "what_would_change_verdict": "...",
    "recommended_forum": "TADM",
    "forum_reasoning": "..."
  }
}
```

---

## Security

| Control | Implementation |
|---------|----------------|
| File type validation | Extension check + magic bytes (`%PDF-` for PDF, UTF-8 decode for TXT) |
| File size limit | 15MB per file, 50MB total — rejected before reading |
| File count limit | Max 10 files total across both panels |
| Prompt injection defence | All user content wrapped in `<UNTRUSTED_DOCUMENT>` tags. System prompt explicitly instructs LLM to ignore instructions inside those tags. Injections flagged as red flags. |
| PII protection | NRIC, phone, address, email regex-scrubbed before LLM. Placeholders `[NRIC]` etc. used during analysis. Real values restored only in final MOM draft. |
| Path traversal | `file.filename` used only as display string. Never used in any filesystem path. |
| SQL injection | Parameterised queries throughout. No f-string SQL anywhere. |
| Rate limiting | 5 requests/minute per IP via slowapi on `/api/analyze` |
| LLM timeout | 90-second hard timeout. Returns HTTP 504 with message. |
| XSS | All user-provided strings passed through `esc()` before DOM insertion |
| CORS | Configurable — set to `*` for hackathon, restrict to specific origin in production |

---

## Setup & Installation

### Prerequisites

- Python 3.11+ (`python3 --version`)
- Bright Data CLI authenticated (`bdata login`) — optional, falls back gracefully
- At least one of: `ANTHROPIC_API_KEY` or `TOKENROUTER_API_KEY`

### Install

```bash
git clone https://github.com/yourusername/clauseguard-v2.git
cd clauseguard-v2

# Install dependencies (use python3 -m pip, not pip)
python3 -m pip install -r requirements.txt --break-system-packages

# Copy and fill in your API keys
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY or TOKENROUTER_API_KEY
```

### Run

```bash
bash start.sh
# or manually:
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000`

### Verify

```bash
# Health check
curl http://127.0.0.1:8000/health

# Regulation cache (should return ≥5 entries)
curl http://127.0.0.1:8000/api/regulations | python3 -m json.tool | head -10

# Run automated tests
python3 -m pip install pytest --break-system-packages
python3 -m pytest tests/test_backend.py -v
```

---

## Environment Variables

```env
# .env.example

# PRIMARY — Anthropic API (recommended)
ANTHROPIC_API_KEY=sk-ant-...

# FALLBACK — TokenRouter / Kimi K2.6 (OpenAI-compatible)
TOKENROUTER_API_KEY=sk-...

# Bright Data CLI: authenticate separately with `bdata login`
# No env var needed for the scraper CLI
```

---

## Hackathon Context

**Event:** Agent Forge Hackathon 2026

**Real-world case underpinning the build:**
ClauseGuard was built around a real Singapore employment dispute where an employee was summoned to a meeting with five HR staff without prior notice and presented with demands to pay S$5,725 or sign a one-year contract extension. The demands rested on:
- A training bond form that was processed internally and never sent to the employee to sign
- A bond trigger clause that referenced "resignation" — but the employee's contract was simply expiring on its stated end date
- A bond duration written as "6 or 12 months" with no specification of which applied
- A letter of appointment that the employer's own HR director never countersigned

All five arguments were confirmed by MOM in writing. The employer's full written concession came 24 hours after a formal email was sent. The entire dispute was resolved in 13 days without legal proceedings.

ClauseGuard was built so that any employee in that position could arrive at the same conclusions in under 3 minutes, rather than 13 days.

---

## Escalation Routes ClauseGuard References

| Authority | What for |
|-----------|----------|
| **MOM** (Ministry of Manpower) | Fixed-term contract disputes, CPF, salary non-payment |
| **TADM** (Tripartite Alliance for Dispute Management) | Mediation for monetary disputes, bond recovery claims |
| **TAFEP** (Tripartite Alliance for Fair Employment Practices) | Workplace intimidation, coercion, unfair practices |
| **IMDA** | CLT programme status disputes — ensuring record shows "contract concluded" not "withdrawn" |
| **Law Society Pro Bono** | Free legal advice at probono.sg — first consultation is free |

---

## Known Limitations

- Scanned / image-only PDFs return no text — use text-layer PDFs or run OCR first
- Session auth is by 8-char hex ID only — no user accounts (acceptable for local deployment)
- CORS set to `*` — restrict to specific origin before deploying publicly
- MOM scraper may return 403 from bot protection — hardcoded KB covers this automatically
- Analysis quality depends on the clarity and completeness of uploaded documents

---

## License

MIT — built for Agent Forge Hackathon 2026.