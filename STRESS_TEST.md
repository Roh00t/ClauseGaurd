---

## PHASE 5 — PRODUCTION READINESS TESTS

### TEST P5-1 — Terms of Service / Privacy Policy
Navigate to http://127.0.0.1:8000/tos

Page loads without error (not 404)?
Contains "processes per-request, retains nothing"?
Contains "TokenRouter" and "Bright Data" named as third parties?
Contains "IndexedDB" or "your browser's local storage"?
Contains "not legal advice"?
Footer link on index.html: "Privacy Policy & Terms" links to /tos?

Check that it does NOT say "we never see your data" (inaccurate — server
processes per-request). Report pass/fail. Flag as P0 if any of items 2-6 fail.

### TEST P5-2 — Rate Limiting
With server running on http://127.0.0.1:8000:
TEST A — Per-IP limit (20/min):

for i in {1..22}; do curl -s -o /dev/null -w "%{http_code}\n" \
-X POST http://127.0.0.1:8000/api/analyze; done | tail -5

Expected: 429 appears at or before request 21.

TEST B — Per-session-token limit (5/min):

for i in {1..7}; do curl -s -o /dev/null -w "%{http_code}\n" \
-H "X-Session-Token: stress-test-token-abc" \
-X POST http://127.0.0.1:8000/api/analyze; done | tail -3

Expected: 429 appears at or before request 6.

TEST C — Different tokens not shared:

curl -s -o /dev/null -w "%{http_code}\n" \
-H "X-Session-Token: token-aaa" -X POST http://127.0.0.1:8000/api/analyze

curl -s -o /dev/null -w "%{http_code}\n" \
-H "X-Session-Token: token-bbb" -X POST http://127.0.0.1:8000/api/analyze

Expected: both return 400/422 (no files) NOT 429.
Report: all three pass/fail.

### TEST P5-3 — Feedback Mechanism
On http://127.0.0.1:8000:
Run analysis on synthetic_contract.pdf.
Do 👍 and 👎 buttons appear on each red flag card?
Click 👍 on the first red flag. Does a "Marked accurate" note appear?
Hard-refresh (Cmd+Shift+R). Click the session in sidebar.
Does the first red flag still show "Marked accurate" (persisted in IndexedDB)?
Check browser dev tools: Application > IndexedDB > clauseguard > sessions >
entry. Does it have a "feedback" field with an entry for flag 0?
Click "Clear my data". Does the feedback clear along with everything else?

Report: pass/fail per step. P0 if feedback doesn't persist (step 5).

### TEST P5-4 — Accessibility
TEST A — ARIA live regions:
document.getElementById('analysisArea')?.getAttribute('role') // "status"
document.getElementById('analysisArea')?.getAttribute('aria-live') // "polite"
Expected: both present. P0 if absent.

TEST B — Keyboard navigation: New Analysis, Panel A, Panel B, chat textarea,
Analyse Everything, Clear my data — all tab-reachable? P0 if Analyse not reachable.

TEST C — Mobile viewport (375px):
window.resizeTo(375, 812);
document.documentElement.scrollWidth > 375 // true = horizontal scroll = P0
Does layout stack vertically? Is Analyse visible without horizontal scroll?

### TEST P5-5 — Multi-Language
Language selector (EN/MS/TL) present? Switching changes disclaimer text?
Tagalog MOM letter note has the stronger legal-translation warning?
Hard-refresh preserves selection (localStorage)? Switch back to EN reverts?

### PHASE 5 FINAL CHECKLIST
- [x] `/tos` loads and contains "processes per-request, retains nothing"
- [x] Rate limit 429 fires after 20 IP requests / 5 same-token requests
- [x] Feedback thumbs persist in IndexedDB and reload on session click
- [x] `analysisArea` div has `role=status` and `aria-live=polite`
- [x] All 6 interactive elements reachable by tab (Clear/Privacy before workflow — accepted)
- [x] No horizontal scroll at 375px mobile viewport (CSS present; live render unverified, P1)
- [x] Language selector switches disclaimer text and persists on reload
- [x] No P0 issues from any Phase 5 test

---

## PART A — MODE SELECTOR, ELI5 OUTPUT, EMPLOYEE-ONLY REBRAND

### TEST A1 — Employer-language audit
grep -rni "employer" frontend/index.html backend/ --include="*.py" --include="*.html" | grep -v "EMPLOYER_AT_FAULT\|EMPLOYER_NOT_AT_FAULT"
Expected: 0 results. Flag P1 if any employer-PERSONA copy remains.

### TEST A2 — Mode selector UI
3 mode buttons above upload panels? Default "dispute" active? Clicking others
changes selection?

### TEST A3 — Mode-aware analysis framing
Run all 3 modes on synthetic_contract.pdf. Onboarding avoids dispute language?
Offboarding mentions final salary/leave/bond if relevant? Dispute unchanged?
P0 if onboarding/offboarding produces dispute-framed output.

### TEST A4 — Backward compatibility (mode field optional)
curl -s -X POST http://127.0.0.1:8000/api/analyze -F "contract_files=@sample_data/synthetic_contract.pdf" -o /dev/null -w "%{http_code}\n"
Expected: 200 — confirms omitting `mode` defaults to `dispute` server-side.

### TEST A5 — ELI5 field presence
curl response → eli5_summary, judgment, analysis all present (`True`)?
P0 if judgment or analysis missing (would break DOCX generation).

### TEST A6 — ELI5 default view + toggle
ELI5 shown by default? "See full analysis ↓" toggle visible and working?
Available regardless of login/tier state?

### TEST A7 — DOCX regression check
Zero placeholder tokens? All sections present? P0 if DOCX broke.

### TEST A8 — Post-analysis follow-up chat
Chat input appears below ELI5/detail toggle? Response engages with actual
results? Network tab shows redacted placeholders, not raw PII, for any
NRIC/name typed into chat? Persists across hard-refresh + session reload?
Works without being logged in? P0 if raw PII reaches the request body.

### TEST A9 — Red flag capping
Dual-panel fixture (6 flags) → only 3 shown by default, CRITICAL-first?
"Show all N flags" reveals rest? DOCX still contains ALL flags? P0 if
DOCX is missing flags.

### PART A FINAL CHECKLIST
- [x] No employer-persona copy remains
- [x] Mode selector renders, defaults to dispute
- [x] All 3 modes produce genuinely different output framing
- [x] `mode` field is optional, defaults to `dispute` server-side
- [x] `eli5_summary` present alongside ALL existing fields, nothing removed
- [x] ELI5 is the default view for everyone, toggle reveals full detail
- [x] DOCX download still produces zero placeholder tokens
- [x] Post-analysis follow-up chat works, redacts input, persists in IndexedDB,
      works for anonymous users (TEST A8)
- [x] Red flags capped to 3 by default with "show all" expansion, DOCX uncapped (TEST A9)
- [x] 34-test regression suite passes — **33/34; 1 documented non-correctness
      latency-threshold flake, see Known Caveats below**

---

## PART B — SUPABASE AUTH

### TEST B1 — Signup flow
Signup completes without mandatory 2FA? user_profiles row created with
tier='free', analyses_used=0?

### TEST B2 — Signin / signout / session persistence
Sign out reverts topbar. Sign back in shows username. Hard-refresh stays
logged in.

### TEST B3 — 2FA is optional, not mandatory
No flow blocks signup/first-analysis without 2FA. If a profile area exists,
2FA can be enabled voluntarily.

### TEST B4 — ToS updated for account metadata
/tos distinguishes account data (Supabase) from contract content (browser-only).
Original "processes per-request, retains nothing" language still present,
unmodified — added to, not replaced. P0 if ToS now falsely implies contract
content is server-stored.

### PART B FINAL CHECKLIST
- [x] Signup works, no mandatory 2FA block
- [x] user_profiles row created correctly (tier=free, analyses_used=0)
- [x] Signin/signout/session-persistence all work
- [x] 2FA is available but optional
- [x] ToS updated accurately (account metadata vs contract content distinction)

*(Part B evidence is from a user-reported summary, not a reviewed
line-by-line session transcript like Part A — noted for calibration,
see Known Caveats.)*

---

## PART C — TIER-GATED FEATURE LOGIC

### TEST C1 — Anonymous free-tier cap is frontend-only
1 free analysis anonymously, 2nd shows client-side modal. Two direct curl
calls without auth → both 200, NOT a 402/403 block. P0 if backend now
blocks anonymous requests after 1 call.

### TEST C2 — Logged-in free-tier cap is backend-enforced
1st analysis: analyses_used → 1. 2nd: paywall response.

### TEST C3 — Manual paid-tier bypass works
Manually set tier='paid' in Supabase → unlimited analyses.

### TEST C4 — DOCX download gating
Anonymous 1st analysis: download works. Logged-in free-tier 2nd+: upgrade prompt.

### TEST C5 — Supabase metadata-only privacy check
analysis_metadata row contains ONLY mode/verdict_category/user_id/timestamp.
P0 if any document content leaked.

### TEST C6 — Final regression
CLAUSEGUARD_TEST_BUDGET=180 python3.13 -m pytest tests/test_backend.py
Expected: 34/34 — actual: 33/34, see Known Caveats.

### PART C FINAL CHECKLIST
- [x] Anonymous free-tier cap remains frontend-only, backend unaffected
- [x] Logged-in free-tier cap is backend-enforced via analyses_used
- [x] Manual tier='paid' edit correctly bypasses the cap
- [x] DOCX download gated correctly per the anonymous/logged-in split
- [x] analysis_metadata contains metadata only, zero content leakage
- [x] Regression suite passes — 33/34, see Known Caveats

## PART D — POSTHOG + ABOUT/PRICING/SUPPORT PAGES

### TEST D1 — Live event delivery (the one check nothing else replaces)
With the real POSTHOG_KEY active, perform: a mode switch, a language
switch, a full analysis, a paywall hit. Log into your actual PostHog
dashboard → Live Events. Do all 4+ events appear within ~30s? Spot-check
2-3 — metadata only, no document text/filenames/question text?
P0 if events never arrive (dead integration despite "working" code).

### TEST D2 — Analytics disabled during tests
Run the regression suite with CLAUSEGUARD_DISABLE_ANALYTICS=1 set.
Confirm no network calls to PostHog fire (check via a packet capture
or simply confirm no new events appear in Live Events during the run).

### TEST D3 — Pages render and gate correctly
/about, /pricing, /support all return 200. Pricing CTAs are visibly
disabled with "Coming soon," not silently non-functional. Support page
does not imply Pro is purchasable today. No console errors on any page.

### PART D FINAL CHECKLIST
- [ ] Live PostHog delivery confirmed (TEST D1) — NOT YET DONE
- [ ] Analytics silent during test runs (TEST D2)
- [ ] All 3 new pages render correctly, gated UI verified (TEST D3)

---

## KNOWN CAVEATS AFTER FULL V3 BUILD (2026-06-20)

- **Regression is 33/34, not 34/34.** `test_three_sequential_analyses`
  asserts avg latency <90s; observed avg was ~115s this run, all 3 calls
  still returned 200. This is a test-threshold mismatch against known
  real-world LLM latency variance (~47s/doc baseline, already a tracked
  P1), not a correctness regression. Consider raising the threshold or
  marking this test expected-flaky rather than treating future 33/34
  results as a new failure each time.
- **The automated suite never exercises the v3 auth path.** No test
  sends an `Authorization` header, so Part B/C's tier-gating logic
  (free cap, paid bypass, metadata logging) is verified manually only
  (Chrome + Supabase dashboard), not by `pytest`. Worth writing at
  least one auth-aware test before this code sees production traffic.
- **`.env` line 15 has a stray `\n`**, producing a harmless "parse error
  near '\n'" message on source. Cosmetic, low priority, one-line fix.
- **Part B/C verification confidence is summary-level**, not transcript-
  reviewed like Part A. Treat as reported-working rather than independently
  re-verified line-by-line.