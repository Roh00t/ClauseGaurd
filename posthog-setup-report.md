<wizard-report>
# PostHog post-wizard report

The wizard has completed a deep integration of PostHog analytics into ClauseGuard. The Python `posthog` package (v3+) was installed and a `Posthog()` instance initialised in `backend/main.py` using environment variables, with `atexit` shutdown registration to flush events on exit. Eight server-side events are captured across the analyze, download, and chat-followup endpoints. Client-side tracking was added to `frontend/index.html` via a dynamically loaded posthog-js CDN bundle; user identification (`posthog.identify()`) fires on successful login, and `user_signed_up` / `user_logged_in` events are captured in the auth modal. The `/api/config` endpoint was extended to serve `posthog_token` and `posthog_host` to the browser so the public key is never hardcoded in source files.

| Event | Description | File |
|---|---|---|
| `analysis_completed` | Fires after a successful combined LLM analysis on uploaded employment documents. | `backend/main.py` |
| `free_tier_limit_reached` | Fires when a logged-in free-tier user attempts an analysis after exhausting their 3-analysis quota. | `backend/main.py` |
| `report_downloaded` | Fires when a DOCX evidence pack is successfully generated and streamed to the client. | `backend/main.py` |
| `chat_followup_asked` | Fires when the user submits a follow-up question after a completed analysis. | `backend/main.py` |
| `analysis_failed` | Fires when the LLM call or document processing raises an unrecoverable error during analysis. | `backend/main.py` |
| `analysis_file_rejected` | Fires when all uploaded contract files fail text extraction (scanned PDFs, corrupt files). | `backend/main.py` |
| `upload_size_exceeded` | Fires when the total upload size exceeds the 50 MB limit. | `backend/main.py` |
| `rate_limit_exceeded` | Fires when a request is rejected by the per-IP or per-session rate limiter. | `backend/main.py` |
| `user_signed_up` | Fires on successful account creation via the auth modal. | `frontend/index.html` |
| `user_logged_in` | Fires on successful sign-in; `posthog.identify(userId)` is called to associate the user. | `frontend/index.html` |

## Next steps

We've built some insights and a dashboard for you to keep an eye on user behavior, based on the events we just instrumented:

- [Analytics basics (wizard) — dashboard](https://us.posthog.com/project/338748/dashboard/1739009)
- [Analyses completed over time](https://us.posthog.com/project/338748/insights/2aFMLXEO)
- [Analyses by mode](https://us.posthog.com/project/338748/insights/cjd8i1Fh)
- [Free tier limit reached](https://us.posthog.com/project/338748/insights/n0IhFjK4)
- [Report download conversion rate](https://us.posthog.com/project/338748/insights/BlfMmqKF)
- [User signups and logins](https://us.posthog.com/project/338748/insights/w8HqOeYy)

## Verify before merging

- [ ] Run a full production build (the wizard only verified the files it touched) and fix any lint or type errors introduced by the generated code.
- [ ] Run the test suite — call sites that were rewritten or instrumented may need updated mocks or fixtures.
- [ ] Add `POSTHOG_PROJECT_TOKEN` and `POSTHOG_HOST` to `.env.example` (or any equivalent bootstrap script) so collaborators know what to set.
- [ ] Confirm the returning-visitor path also calls `identify` — the current implementation only calls `posthog.identify()` on fresh login; users whose session is restored from localStorage on page load will not be re-identified until they next sign in.

### Agent skill

We've left an agent skill folder in your project. You can use this context for further agent development when using Claude Code. This will help ensure the model provides the most up-to-date approaches for integrating PostHog.

</wizard-report>
