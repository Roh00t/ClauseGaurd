# ClauseGuard — Known Issues

**Status as of 2026-06-20:** No P0 issues. v3 Consolidated Build (Parts
A/B/C) complete. Automated regression: 33/34 (1 documented non-correctness
latency-threshold flake). Fix Sprint complete (34/34 at the time).

---

## Open P1 Issues

### Redaction / Privacy
- NER under-redaction: single-word company names, unlisted suffixes not
  caught. Requires presidio or a larger spaCy model — deferred.
- Terminal 3 signing is symmetric (HMAC) — third parties can't independently
  verify without ClauseGuard's key.
- Attestation receipt is response-only, not persisted on session reload.
- Private-browsing banner best-effort (modern browsers often allow
  IndexedDB in incognito — footer notice is the real safeguard).

### Performance
- Analysis latency ~47s/doc, ~108-115s/multi-doc — LLM-bound.
- `test_three_sequential_analyses` regression threshold (avg<90s) flakes
  against real-world latency variance — test-threshold issue, not a bug.
- Transient 502/504 risk reduced (4 retries + trailing-comma tolerance)
  but not eliminated.
- Test suite duration ~22-27min, longer with v3 LLM-backed auth/mode tests.
- In-memory rate-limit state is single-process — needs Redis at scale.

### Security / Abuse
- Per-session-token rate limit bypassable via UUID rotation under per-IP cap.
- CORS = `*` — must restrict to the Render production domain before public launch.
- Anonymous free-tier cap is localStorage-only — clearing browser data or
  using a new browser resets it. Accepted as growth, not abuse, per v3 decisions.

### Accessibility / Mobile
- Mobile 375px CSS present/parsed but unverified at true render (Chrome
  MCP limitation) — needs manual device test before public launch.
- Tab order: Clear-my-data/Privacy precede main workflow (deliberate,
  avoids positive-tabindex anti-pattern).

### Product / Scope
- Feedback (👍/👎) has no aggregate signal — client-side only by design.
- i18n covers UI copy only — red flags, ELI5 summary, and full analysis
  output remain English.
- Scraper fallback: mom.gov.sg may 403; hardcoded KB guarantees coverage
  but freshness isn't guaranteed for KB-served entries.
- Scanned/image-only PDFs return clean 422 — no OCR fallback.

### v3 / Auth & Monetisation (new, 2026-06-20)
- **Automated test suite does not exercise the auth path.** No test sends
  an `Authorization` header — tier-gating logic (free cap, paid bypass,
  metadata-only logging) is manually verified only, not by `pytest`.
  Should get at least minimal automated coverage before production traffic.
- **`.env` line 15 has a stray `\n`** — harmless "parse error near '\n'"
  message on source, cosmetic, easy one-line fix.
- **Stripe is not wired.** `tier='paid'` is reachable only via manual
  Supabase dashboard edit — by design, for testing the paid-gated UI,
  not a bug, but a hard stop before any public "Pro" claim can be made.
- **Persistent cross-device chat sync is UI-messaging only** — the actual
  sync mechanism (so chat history follows a logged-in user across devices)
  was explicitly deferred; current chat is single-session/browser-local only.

### Needs Verification
- STRESS_TEST.md `make_pdf` helper: confirm `bytes(pdf.output())` (not
  `.encode("latin-1")`) is present in the embedded copy, not just
  `tests/test_backend.py`. `grep -n 'encode.*latin' STRESS_TEST.md` should
  return 0 results.

---

## Recently Resolved (v3 Consolidated Build, 2026-06-20)
- Employee-only rebrand — no employer-persona copy remains
- Mode selector (onboarding/offboarding/dispute) with genuinely distinct framing
- ELI5 summary as default view for all users, full detail behind a toggle
- Red flags capped to top 3 by default in-app; DOCX always gets all flags
- Post-analysis follow-up chat (distinct from pre-analysis chat_context),
  reuses existing redaction path, single-session/IndexedDB-backed
- Supabase auth (signup/signin/signout/session persistence), 2FA optional
- Tier-gated feature logic (free cap, DOCX gate, paid bypass via manual
  Supabase edit), metadata-only logging verified clean

## Recently Resolved (Fix Sprint, 2026-06-16)
- CRITICAL badge contrast (red-on-red ~1.3:1 → light text ~7.22:1 WCAG AA)
- Download button gated on verdict (hidden for INSUFFICIENT_INFORMATION)
- STRESS_TEST.md stale `results` ID → `analysisArea`
- Vestigial `session_id` removed from `/api/analyze` response
- Tab order interleaving — `tabindex=-1` on nav/session entries
- Token-count dict unbounded growth — lazy eviction added
- Transient 502 retry 3→4 attempts + trailing-comma JSON tolerance
- Mobile @media(max-width:640px) responsive layout added

## Resolved Earlier (Phases 1-5)
- `make_pdf` bytearray crash (fpdf2 2.8.7)
- Module-script timing bug (false private-browsing banner)
- QuotaExceededError unhandled on IndexedDB save
- Orphaned pre-Phase-2 session rows in data.db — cleared
- No session-reload de-redaction — fixed when entity map moved client-side
- DOCX generator flat-vs-nested schema mismatch — corrected
### v3 / Analytics (new, 2026-06-20)
- **Live PostHog event delivery unconfirmed.** All verification so far
  is code-level (stubbed recorder, property audit). Needs a manual
  check: trigger real actions, confirm they appear in PostHog Live
  Events within ~30s.
- **posthog package pinned to 3.x (3.25.0), not the installed-by-default
  7.x.** The wizard's generated code used the v3 API; v7 breaks
  `capture()`'s argument order silently (no error, just wrong data).
  Tracked debt: upgrade to 7.x properly later, don't leave pinned forever.
- **`.env.example` Supabase keys — completion not confirmed.** Last
  known state: approved, not verified done.
- **Contact email and community link are placeholders** on the new
  About/Pricing/Support pages (`hello@clauseguard.sg` is not a real
  inbox; community link says "coming soon," Discord vs Reddit undecided).

### Two distinct flaky tests — do not conflate
- `test_three_sequential_analyses` — asserts avg latency <90s; real-world
  LLM latency varies (~47-115s observed), threshold-mismatch flake.
- `test_analyze_completes_within_budget` — 502 when the LLM returns
  malformed JSON 4 consecutive times (exhausts all retries); passes
  clean on isolated re-run. Separate known failure mode from the one above.
Both are documented transient flakes, not regressions — but track them
by name, not as one generic "the known flake," or a real regression
could hide behind that assumption in a future session.

## Recently Resolved (PostHog + Pages, 2026-06-20)
- App-breaking import failure from an unpinned posthog dependency +
  module-level client init — caught before merge, not in production
- v7/v3 API mismatch in capture() argument order — would have silently
  corrupted all analytics data, caught via investigation before any
  real events were sent
- Exception autocapture shipping raw tracebacks externally — disabled
  (guardrail #13)
- Returning-visitor identify gap + posthog-load race condition — fixed
- Misattributed report_downloaded/chat_followup_asked events — now
  correctly tied to logged-in user_id
- About/Pricing/Support pages built, red-team constraints verified live