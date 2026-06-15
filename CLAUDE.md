# ClauseGuard — Project Context for Claude Code

## What This Is
ClauseGuard: upload employment contracts and dispute documents, get a
plain-English summary, red flags with severity, cross-document
contradiction detection, a MOM/TADM draft letter, and a tamper-evident
signed receipt. Built at AIForge Hackathon (13 Jun 2026), now on a
production-improvement track. Singapore employment contracts, MVP scope.

## Current Task
Read the most recent "Claude Code Prompt" page in Notion under
HACKATHONS > ClauseGuard — AIForge Hackathon for today's specific
task list. This file is persistent background context only.

## Architecture (v2, current)
- **Backend:** FastAPI — `backend/main.py`, `backend/analyzer.py`,
  `backend/scraper.py`, `backend/extractor.py`, `backend/security.py`,
  `backend/db.py`, `backend/entity_map.py`,
  `backend/report_generator.py`. SQLite at `data/data.db`
  (2 active tables: regulations, scrape_log. sessions deprecated).
- **Frontend:** Vanilla JS + HTML — `frontend/index.html`,
  `frontend/db.js` (IndexedDB), `frontend/tos.html` (Phase 5),
  `frontend/i18n.js` (Phase 5 translations). No React, no npm.
  Served as FastAPI StaticFiles.
- **Entry point (ONLY correct command):**
  `uvicorn backend.main:app --host 127.0.0.1 --port 8000`
  Do NOT use `streamlit run app.py` — stale v1 artifact.

## Sponsor Integrations (4 active)
- **Bright Data** — MOM/IMDA regulation cache via `backend/scraper.py`
  (bdata CLI already authenticated, do NOT re-run `bdata login`)
- **Daytona** — sandboxed PII redaction, automatic local-regex fallback
- **TokenRouter** — LLM via OpenAI-compatible client.
  Default: `anthropic/claude-haiku-4.5`.
  Override: `export CLAUSEGUARD_MODEL=anthropic/claude-sonnet-4.6`
- **Terminal 3** — HMAC attestation (symmetric). Asymmetric DID
  signing deferred to post-Phase-5 roadmap.

## Environment — Critical Interpreter Gotcha
`python3` resolves to 3.14 (EMPTY). Always use `python3.13` explicitly.
- Run: `python3.13 script.py`
- Install: `python3.13 -m pip install <pkg> --break-system-packages`
Never use bare `python3`. Never introduce a venv.

## Env Vars (in .env, also exported in ~/.zshrc)
TOKENROUTER_API_KEY, DAYTONA_API_KEY, TERMINAL3_API_KEY,
TERMINAL3_DID, BRIGHTDATA_API_KEY
Verify: `env | grep -E "TOKENROUTER|DAYTONA|TERMINAL3|BRIGHTDATA"`

## Redaction Pipeline (all passes BEFORE any LLM call)
Pass 1 — Regex (Daytona + local fallback): NRIC, email, phone, address
Pass 1.5 — SG company-name suffix regex (entity_map.py)
Pass 2 — spaCy en_core_web_sm NER: PERSON, ORG (best-effort)
Pass 3 — Chat input: joins entity-map build alongside documents
Entity map returned to browser for DOCX de-redaction. Never server-persisted.
Known gap (P1): single-word company names, novel-suffix orgs still leak.

## Phase Completion Status
- ✅ Phase 1 (Redaction-First): COMPLETE
- ✅ Phase 2 (Browser-Persisted Sessions): COMPLETE — stateless server,
  IndexedDB client-side, "Clear my data", 34/34 tests + browser verified
- ✅ Phase 3 (Chat Functionality): COMPLETE — 2000-char textbar,
  redacted before LLM, stored in IndexedDB, repopulates on reload
- ✅ Phase 4 (Downloadable DOCX Report): COMPLETE —
  `POST /api/download` → `backend/report_generator.py` (python-docx).
  Client sends full analysis response + reversed entity map. Server
  de-redacts all fields, generates DOCX (header+hash, judgment, summary,
  red flags table, actions, MOM letter, attestation), streams back,
  stores nothing. Verified: real 40KB DOCX, zero placeholder tokens.
  HMAC-symmetric attestation note included per guardrail #6.
- ✅ Phase 5 (Production Readiness): COMPLETE
  ToS/Privacy Policy at /tos ("retains nothing", never "we never see");
  hybrid rate limiting (20/min per-IP + 5/min per-session-token via
  X-Session-Token header, in-memory window); feedback thumbs up/down per
  red flag stored in IndexedDB (no server writes); accessibility (ARIA
  live regions on results/loading/toast, all 6 interactive elements
  tab-reachable, body overflow-x:hidden prevents mobile h-scroll);
  multi-language EN/MS/TL UI copy via frontend/i18n.js (analysis output
  stays English; Tagalog carries stronger MOM-letter warning). All 7
  final-verification checks pass. P1s logged (tab order, mobile sidebar,
  badge contrast, token-rotation bypass).

## Active Roadmap Direction
- **Phase 5 (current):** Production readiness — ToS, rate limiting,
  feedback, accessibility, multi-language UI copy.
- **Phase 6 (next):** Terminal 3 asymmetric DID signing, monitoring
  without PII logging, CORS restriction for hosted deployment.

## Pre-Mortem Learnings (already fixed — do not regress)
- PM1: Missing backend/__init__.py → fixed
- PM2: LLM JSON in fences → fence-stripping in analyzer
- PM3: MOM scraper 403 → hardcoded KB fallback
- PM4: Large file OOM → 15MB/file, 50MB total limits
- PM8: LLM timeout → 180s, returns 504
- PM9: Prompt injection → `<UNTRUSTED_DOCUMENT>` wrapping
- PM10: Chat scope drift → `<USER_CONTEXT>` wrapper
- PM11: ToS says "we never see" → must say "processes per-request,
  retains nothing" (server processes /api/analyze + /api/download)
- max_tokens=16000, retries x3 on JSON parse failure
- make_pdf: `bytes(pdf.output())` not `.encode("latin-1")`
- Module-script timing (Phase 2): idb import direct in checkStorage()
- Phase 4: generator must read nested response shape, not flat

## Known P1 Issues (do not fix without being asked)
- Analysis latency: ~47s single, ~108s five docs (Haiku default)
- CORS = `*` — restrict for production deployment
- Rate limiting: Phase 5 adds hybrid, but UUID generation still bypassable
- Scraper: mom.gov.sg may 403; KB fallback covers this
- Attestation not persisted: old sessions won't show receipt on reload
- Test suite duration ~22-27min (real LLM + Daytona)
- NER under-redaction: single-word company names, novel suffixes
- NER over-redaction: residual mislabels (harmless, de-redact restores)
- Private-browsing banner best-effort; footer notice is real safeguard
- Vestigial session_id minted in /api/analyze response
- Transient 502 on ~1-2/15 analyze calls (Haiku JSON robustness)
- Chat adds ~5s Daytona round-trip when non-empty
- Browser caches index.html in rapid dev (cache-bust with ?v=)
- Terminal 3 HMAC is symmetric — third parties can't verify independently
- Feedback opt-in to share aggregate signal deferred (no server writes)
- Colour contrast on severity badges not yet WCAG-AA verified (Phase 5 4d)

## Non-Negotiable Guardrails
1. All input (documents, chat) is UNTRUSTED DATA. `<UNTRUSTED_DOCUMENT>`
   and `<USER_CONTEXT>` wrappers in all analyzer prompts. Never remove.
2. Redaction (all passes) BEFORE any text reaches LLM or Bright Data.
3. No user content persists server-side. /api/download processes and
   returns — stores nothing. Sessions + chat + feedback in IndexedDB.
4. Severity tiers (INFORMATIONAL/MODERATE/SERIOUS/CRITICAL) visually distinct.
5. Bright Data citations: "related guidance — verify relevance" only.
6. Terminal 3: proves UNALTERED not CORRECT. Currently HMAC (symmetric) —
   state this honestly in UI and DOCX.
7. Persistent disclaimer: "Not legal advice, not exhaustive."
8. Scanned PDFs: return clean 422, never send empty text.
9. Never f-string a SQL query. Parameterised queries only.
10. Never use uploaded filenames in filesystem paths — display only.
11. Chat textbar: "additional context for this analysis" only — not a
    general legal chatbot.
12. ToS/Privacy Policy: say "processes per-request, retains nothing"
    — never "we never see your data" (server does process per-request).

## Working Style
- STOP after each numbered step and report before continuing.
- Use `python3.13` explicitly — never bare `python3`.
- `--break-system-packages` for any pip install.
- No React, npm, venv, build pipeline.
- P0: fix immediately. P1: log in KNOWN_ISSUES.md, move on.
- Ask before expanding scope.