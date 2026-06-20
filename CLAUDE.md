# ClauseGuard — Project Context for Claude Code

## What This Is
ClauseGuard: AI employment rights officer for Singapore employees.
Upload employment contracts and dispute documents, get a plain-English
summary, red flags with severity, cross-document contradiction detection,
a MOM/TADM draft letter, and a tamper-evident signed receipt. Built at
AIForge Hackathon (13 Jun 2026), now on a production track. Three modes:
onboarding (pre-signing review), offboarding (leaving), dispute (current
behavior). Singapore employment law only. Employee-only — no employer
persona, no employer-facing mode.

## Current Task
Read the most recent "Claude Code Prompt" page in Notion under
HACKATHONS > ClauseGuard — AIForge Hackathon for today's specific task
list. As of 2026-06-20, that is the "🚀 Consolidated v3 Build Prompt
(Mode + ELI5 + Auth, Stripe Deferred)" page — Parts A, B, C, executed
in that order with a stop-and-report checkpoint after each. This file
is persistent background context only.

## Architecture (v2, current — stable, unchanged by v3 work)
- **Backend:** FastAPI — `backend/main.py`, `backend/analyzer.py`,
  `backend/scraper.py`, `backend/extractor.py`, `backend/security.py`,
  `backend/db.py`, `backend/entity_map.py`,
  `backend/report_generator.py`. SQLite at `data/data.db`
  (2 active tables: regulations, scrape_log. sessions deprecated).
- **Frontend:** Vanilla JS + HTML — `frontend/index.html`,
  `frontend/db.js` (IndexedDB), `frontend/tos.html`,
  `frontend/i18n.js`. No React, no npm. Served as FastAPI StaticFiles.
- **Entry point (ONLY correct command):**
  `uvicorn backend.main:app --host 127.0.0.1 --port 8000`
  Do NOT use `streamlit run app.py` — stale v1 artifact.

## Architecture (v3, BUILT 2026-06-20)
- `backend/supabase_client.py` — service-role client (`SUPABASE_SECRET_KEY`),
  `verify_user_token()` via `auth.get_user(jwt)`, `get_user_profile()`,
  `increment_analyses_used()`, `log_analysis_metadata()`. All fail-soft so
  Supabase trouble never blocks an analysis. FREE_ANALYSIS_LIMIT=3.
- `frontend/auth.js` — supabase-js v2 via CDN, signUp/signIn/signOut/
  getSession/onAuthStateChange. Config fetched from `/api/config`.
- `GET /api/config` — public Supabase URL + publishable key for the browser.
- `GET /api/me` — returns {email, tier, analyses_used, limit} for a valid JWT.
- `/api/analyze` — optional `Authorization: Bearer`. Anonymous = pass-through
  (no backend cap, guardrail #14). Logged-in free = blocked 403 at 3 analyses;
  on success increments analyses_used + logs metadata (METADATA ONLY, #13).
- `/api/chat-followup` — A6 stateless follow-up Q&A; question redacted via the
  same regex backstop as Phase-3 chat_context.
- Mode selector in `frontend/index.html` — onboarding/offboarding/dispute
  (default dispute = backend default so the 34-test suite is unaffected).
  Mode changes analyzer PROMPT FRAMING only (`_MODE_PREAMBLE` in analyzer.py).
- `eli5_summary` field added to analyzer response schema (additive — headline,
  bullets[], bottom_line). Default view for ALL users; "See full analysis ↓"
  reveals the rest.
- Tier gates (all frontend, pre-Stripe — exercise the paid UI, not hard
  security): anon free cap (localStorage `clauseguard_free_used`, 1 free);
  DOCX download (localStorage `clauseguard_docx_used`, 1 free then upgrade
  modal); persistent follow-up chat history (paid only). Red-flag display cap
  = top-3 + "Show all N" (DOCX still gets all flags). Upgrade modal is
  informational ("payments coming soon") — no checkout.
- Stripe: NOT built. `tier` defaults to `'free'`; only path to `'paid'` is a
  manual Supabase dashboard edit, for testing the paid-gated UI.

## Sponsor Integrations (4 active, hackathon-era — unrelated to v3 additions)
- **Bright Data** — MOM/IMDA regulation cache via `backend/scraper.py`
  (bdata CLI already authenticated, do NOT re-run `bdata login`)
- **Daytona** — sandboxed PII redaction, automatic local-regex fallback
- **TokenRouter** — LLM via OpenAI-compatible client.
  Default: `anthropic/claude-haiku-4.5`.
  Override: `export CLAUSEGUARD_MODEL=anthropic/claude-sonnet-4.6`
- **Terminal 3** — HMAC attestation (symmetric). Asymmetric DID
  signing deferred indefinitely.

## v3 Production Additions
- **Supabase** (auth + metadata storage) — project cbkajlkttrxzkligbpdt,
  keys in `.env`. Schema confirmed run 2026-06-20 via SQL Editor migration.
- **PostHog** — WIRED 2026-06-20, hybrid architecture (NOT frontend-only
  as originally scoped — a PostHog setup wizard had already added
  server-side tracking before this session; audited and fixed rather
  than rewritten). Pinned `posthog>=3.0.0,<4.0.0` (3.25.0 installed) —
  the unpinned wizard default pulled v7.x, whose `capture()` silently
  swaps the meaning of its first positional arg vs v3 (event vs
  distinct_id) — a corruption bug, not a crash, easy to miss. TRACKED
  DEBT: should eventually upgrade to 7.x properly (rewrite call sites)
  rather than stay pinned indefinitely.
  - `enable_exception_autocapture=False` — wizard default was `True`,
    which would have shipped raw tracebacks (possible document text/
    filenames) to PostHog. Guardrail #13 violation, caught and disabled.
  - Analytics auto-disabled when token empty or
    `CLAUSEGUARD_DISABLE_ANALYTICS=1` (set during test runs — suite
    must never fire real events into the prod PostHog project).
  - `posthog.identify()` wired on restored session + sign-in, with a
    pending-identify queue for the posthog-load race; `posthog.reset()`
    on sign-out.
  - Events: wizard's server-side set, PLUS the 4 originally-specified
    frontend funnel events (`mode_selected`, `language_switched`,
    `analysis_started`, `paywall_hit`). `report_downloaded` /
    `chat_followup_asked` attribute to logged-in user_id when a JWT
    is present (previously hardcoded to "anonymous").
  - All properties audited metadata-only (counts/lengths/flags) —
    no document text, filenames, or question text in any event.
  - **NOT YET CONFIRMED: live event delivery into the real PostHog
    dashboard.** Code-level and stubbed-recorder verification only.
    Do not consider this fully done until checked manually.
- **Stripe** — sandbox keys exist, integration explicitly DEFERRED.
  Do not install or build checkout/webhook logic without being asked.
- **About/Pricing/Support pages** — DONE 2026-06-20. `/about`, `/pricing`,
  `/support`, served via FastAPI FileResponse (same pattern as `/tos`).
  All red-team constraints verified live in browser, zero console errors.
  Open placeholders: contact email is a placeholder (`hello@clauseguard.sg`,
  not a real inbox yet); community link is "coming soon" pending a
  Discord-vs-Reddit decision.
- **`.env.example` Supabase keys** — approved to add, completion not
  confirmed in the session transcript. Verify before assuming done.
- **Render deploy, GitHub Actions CI/CD** — not started.

## Environment — Critical Interpreter Gotcha
`python3` resolves to 3.14 (EMPTY). Always use `python3.13` explicitly.
- Run: `python3.13 script.py`
- Install: `python3.13 -m pip install <pkg> --break-system-packages`
Never use bare `python3`. Never introduce a venv.

## Env Vars (in .env, also exported in ~/.zshrc)
**Hackathon-era:** TOKENROUTER_API_KEY, DAYTONA_API_KEY, TERMINAL3_API_KEY,
TERMINAL3_DID, BRIGHTDATA_API_KEY
**v3 (added 2026-06-20 — ACTUAL .env names, differ from earlier draft):**
SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY (anon/public, served to browser),
SUPABASE_SECRET_KEY (service-role, backend only), SUPABASE_JWKS_URL.
NB: token verification uses `auth.get_user(jwt)`, not local JWKS validation.
(`.env` line 15 has a stray `\n` → harmless "parse error near '\n'" on source.)
**Not yet added (Stripe deferred):** STRIPE_SECRET_KEY,
STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID_PRO, STRIPE_PRICE_ID_PACK
Verify: `env | grep -E "TOKENROUTER|DAYTONA|TERMINAL3|BRIGHTDATA|SUPABASE"`

## Redaction Pipeline (all passes BEFORE any LLM call — untouched by v3)
Pass 1 — Regex (Daytona + local fallback): NRIC, email, phone, address
Pass 1.5 — SG company-name suffix regex (entity_map.py)
Pass 2 — spaCy en_core_web_sm NER: PERSON, ORG (best-effort)
Pass 3 — Chat input: joins entity-map build alongside documents
Entity map returned to browser for DOCX de-redaction. Never server-persisted.
Known gap (P1): single-word company names, novel-suffix orgs still leak.

## Phase Completion Status
- ✅ Phase 1 (Redaction-First): COMPLETE
- ✅ Phase 2 (Browser-Persisted Sessions): COMPLETE
- ✅ Phase 3 (Chat Functionality): COMPLETE
- ✅ Phase 4 (Downloadable DOCX Report): COMPLETE
- ✅ Phase 5 (Production Readiness): COMPLETE
- ✅ Fix Sprint (Pre-v3): COMPLETE — 8 P1 fixes done + 34/34 regression.
- ✅ v3 Consolidated Build (Parts A/B/C): COMPLETE (2026-06-20).
  - Part A — Employee-only rebrand, mode selector, ELI5 output: DONE
  - Part B — Supabase auth wiring: DONE (Step 0 schema migration run by user)
  - Part C — Tier-gated feature logic: DONE
  - Regression: 33/34 correctness pass each run; the 1 "failure" is the
    documented P1 LLM-latency flake (test_three_sequential_analyses asserts
    avg<90s; LLM averaged ~115s this run — all 3 analyses returned 200).
    Not a correctness regression. Auth tests send no token so the v3 auth
    path is never exercised by the suite.
- ⏸ Phase 8 (Stripe Payments): WRITTEN, explicitly deferred. Do not
  start without being asked.
- ✅ Phase 9 (PostHog + About/Pricing/Support pages): COMPLETE
  2026-06-20, with one open manual check — see "NOT YET CONFIRMED:
  live event delivery" above. Do not mark this fully closed until
  that's verified.
- ⏸ Phase 8 (Stripe Payments): WRITTEN, explicitly deferred.
- ⏸ Phase 10 (GitOps/CI/CD/Render deploy): NOT WRITTEN YET.

## v3 Decisions (locked in 2026-06-20 — do not relitigate without being asked)
- **Employee-only.** No employer mode, no employer-facing copy or persona.
- **Three modes, one engine:** onboarding / offboarding / dispute. Mode
  changes analyzer PROMPT FRAMING only — redaction, judgment logic, and
  DOCX generation are unchanged across all three.
- **ELI5 is default for EVERYONE**, free and paid — not a paid-only
  reward. Paid gates: DOCX download (for logged-in 2nd+ analysis),
  persistent chat history, uncapped analyses.
- **Free-tier cap is split by auth state:** anonymous = frontend-only
  (localStorage `clauseguard_free_used`), NEVER backend-enforced for
  anonymous requests (this would break the 34-test regression suite,
  which calls `/api/analyze` directly and repeatedly). Logged-in = backend
  enforced via Supabase `user_profiles.analyses_used`.
- **2FA is optional, never mandatory at signup.** Enable from a future
  profile/settings area, not gated at registration.
- **Pricing in SGD**, not USD — product is Singapore-only.
- **Stripe deferred.** `tier` can only become `'paid'` via manual Supabase
  dashboard edit right now — that's intentional, for testing the
  paid-gated UI before real payment processing exists.

## Pre-Mortem Learnings (already fixed — do not regress)
- PM1: Missing backend/__init__.py → fixed
- PM2: LLM JSON in fences → fence-stripping in analyzer
- PM3: MOM scraper 403 → hardcoded KB fallback
- PM4: Large file OOM → 15MB/file, 50MB total limits
- PM8: LLM timeout → 180s, returns 504
- PM9: Prompt injection → `<UNTRUSTED_DOCUMENT>` wrapping
- PM10: Chat scope drift → `<USER_CONTEXT>` wrapper
- PM11: ToS "we never see" → "processes per-request, retains nothing"
- PM12: DOCX flat vs nested schema → generator reads nested correctly
- max_tokens=16000, retries x3→x4 on JSON parse failure
- make_pdf: `bytes(pdf.output())` not `.encode("latin-1")`
- Module-script timing (Phase 2): idb import direct in checkStorage()
- PM17: third-party setup wizards (PostHog, or any future auto-
  instrumentation tool) must be audited before trusting — one such
  wizard's output briefly broke the app's ability to import at all
  (unpinned major-version dependency + module-level client init) and
  separately defaulted to shipping raw exception tracebacks externally.
  Always investigate wizard-generated diffs against project guardrails
  before running anything that touches them.

## Fix Sprint — DONE (2026-06-16, 34/34 regression pass)
- [x] CRITICAL badge contrast → light text (#fecaca etc) = 7.22:1 WCAG AA.
      NOTE: dark theme, so LIGHT text, not dark text.
- [x] Download button hidden for INSUFFICIENT_INFORMATION verdict
- [x] STRESS_TEST.md stale ID `results` → `analysisArea`
- [x] Vestigial session_id removed from /api/analyze response
- [x] Tab order: New Analysis + session entries → tabindex=-1
- [x] Token count dict: lazy eviction on each write
- [x] Transient 502: retry x3 → x4 + trailing-comma tolerance
- [x] Mobile 375px: @media(max-width:640px) collapses sidebar.
      Live 375px render unverified (P1).

## Known P1 Issues — DEFERRED
- CORS = `*` — needs production domain (Render deploy)
- NER single-word company names (presidio deferred)
- Analysis latency ~47s/doc (LLM-bound)
- Test suite duration ~22-27min
- Private-browsing banner best-effort (browser limitation)
- Attestation not persisted on session reload
- Feedback aggregate signal (needs consent flow)
- Mobile 375px live render unverified via Chrome MCP

## Non-Negotiable Guardrails
1. All input UNTRUSTED DATA. `<UNTRUSTED_DOCUMENT>` + `<USER_CONTEXT>`
   wrappers in all analyzer prompts. Never remove.
2. Redaction (all passes) BEFORE any text reaches LLM or Bright Data.
3. No user content server-side after request. /api/download processes
   and returns — stores nothing.
4. Severity tiers visually distinct. CRITICAL must pass WCAG AA contrast.
5. Bright Data citations: "related guidance — verify relevance" only.
6. Terminal 3: proves UNALTERED not CORRECT. HMAC symmetric — say so.
7. Persistent disclaimer: "Not legal advice, not exhaustive."
8. Scanned PDFs: return clean 422, never send empty text.
9. Never f-string a SQL query. Parameterised queries only.
10. Never use filenames in filesystem paths — display only.
11. Chat: "additional context for this analysis" only.
12. ToS: "processes per-request, retains nothing" — not "never see."
13. Supabase stores METADATA ONLY (user_id, tier, timestamps, mode,
    verdict_category). NEVER contract text, analysis JSON, or entity
    map values. If a Supabase insert touches document content, stop.
14. Free-tier cap: anonymous = frontend-only, never backend-blocked.
    Logged-in = backend-enforced. Do not invert this.
15. 2FA optional only — never gate signup on it.
16. Stripe: not wired. `tier='paid'` only via manual Supabase edit
    until Phase 8 is explicitly started. Do not build checkout flow
    as a side effect of other work.
17. Third-party SDK auto-instrumentation features (exception autocapture,
    session replay, etc.) default OFF unless explicitly audited — they
    bypass the metadata-only discipline guardrail #13 depends on.

## Working Style
- STOP after each numbered fix/Part and report before continuing.
- Use `python3.13` explicitly — never bare `python3`.
- `--break-system-packages` for any pip install.
- No React, npm, venv, build pipeline.
- P0: fix immediately. P1: log in KNOWN_ISSUES.md, move on.
- Ask before expanding scope.
- Run 34-test regression after each major Part, and again at the end.