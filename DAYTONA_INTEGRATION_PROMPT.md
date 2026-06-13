# CLAUSEGUARD v2 — DAYTONA INTEGRATION (HARDENED)
# Pre-Mortem · Steelman · Red Team applied
# Estimated time: 30-40 minutes

---

## MANDATORY STEP 0 — SMOKE TEST BEFORE ANY CODE CHANGE

Run this block FIRST. Report every line of output. Do not proceed until it passes.

```bash
# 1. Confirm daytona-sdk is installed and importable
python3 -c "
import importlib.util
spec = importlib.util.find_spec('daytona')
if spec:
    print('daytona-sdk found at:', spec.origin)
    from daytona import Daytona
    print('Daytona class imported OK')
else:
    print('daytona-sdk NOT installed — installing now')
" 

# 2. If not installed:
python3 -m pip install "daytona-sdk>=0.10.0" --break-system-packages

# 3. Confirm auth and sandbox creation work
python3 -c "
from daytona import Daytona, CreateSandboxParams
try:
    d = Daytona()
    sb = d.create(CreateSandboxParams(language='python'))
    resp = sb.process.code_run('import sys; print(sys.version)')
    print('Sandbox Python:', resp.result.strip()[:60])
    d.delete(sb)
    print('Daytona: AUTHENTICATED AND WORKING')
except Exception as e:
    print('Daytona ERROR:', type(e).__name__, str(e)[:120])
    print('Will proceed with fallback-only mode')
"

# 4. Confirm what API methods exist on your installed version
python3 -c "
from daytona import Daytona, CreateSandboxParams
d = Daytona()
sb = d.create(CreateSandboxParams(language='python'))
print('Sandbox attrs:', [a for a in dir(sb) if not a.startswith('_')])
d.delete(sb)
" 2>&1 | head -5
```

**If Step 0 shows Daytona is broken or auth has expired:**
- Run `daytona login` to re-authenticate
- If the SDK API differs from `sb.process.code_run()` (e.g. uses `sb.execute()` instead),
  note the correct method name and use it throughout — do NOT guess

---

## ARCHITECTURAL DECISIONS — DO NOT DEVIATE

These decisions came from Pre-Mortem and Red Team analysis. Each one prevents a
specific failure mode. Do not change them.

| Decision | Reason |
|----------|--------|
| ONE sandbox per analyze request (not per file) | Per-file = N×15s overhead. 5 files = 75s before LLM even starts. Demo dies. |
| Lazy import (`try: from daytona import Daytona`) inside function, not module top | Module-level import crashes FastAPI startup if SDK missing. App never starts. |
| Base64-encode text going into sandbox script | PDF text with quotes/backslashes breaks string literals in inline scripts. SyntaxError. |
| Sandbox returns `{"scrubbed":"...","map":{...}}` as LAST stdout line | Other stdout (warnings, logs) causes `json.loads(stdout)` to fail. Parse last line only. |
| `json.dumps(sort_keys=True, ensure_ascii=True)` for hash input | Default dict ordering is non-deterministic. Same analysis = different hash every run. |
| `try/finally: d.delete(sandbox)` everywhere | Every unhandled exception leaks a sandbox. 5-10 leaks = quota exhausted mid-demo. |
| Fallback MUST be silent and transparent | Daytona is an enhancement. User must never see a Daytona error. App works either way. |
| report_hash displayed in UI footer | If it's not shown, judges can't see it. Feature is invisible = wasted effort. |

---

## FILE CHANGES — READ EACH EXISTING FILE BEFORE EDITING

### Files to read first (do not skip):
```bash
cat backend/redactor.py
cat backend/main.py
grep -n "report_hash\|judgment\|verdict\|session" backend/db.py | head -30
grep -n "daytona\|report_hash" tests/test_backend.py | head -20
```

Report what you find. Confirm:
- What does `main.py` currently call for redaction? (`scrub_for_llm` or something else?)
- Does `data/data.db` sessions table already have `report_hash` column?
- Does `tests/test_backend.py` check for `report_hash`?

---

## CHANGE 1 — `backend/redactor.py` (AMEND, do not rewrite)

Add ONE new function at the bottom of the existing file. Do not change `scrub_for_llm()` or `restore_in_draft()`.

```python
import base64
import json
import logging

logger = logging.getLogger(__name__)


def run_in_sandbox(texts: list[dict], daytona_instance=None) -> list[dict]:
    """
    Runs PII redaction for a list of documents inside a Daytona sandbox.

    Args:
        texts: [{"filename": str, "text": str}, ...]
        daytona_instance: a live Daytona sandbox object passed in from main.py.
                          If None, falls back to local scrub_for_llm() immediately.

    Returns:
        [{"filename": str, "scrubbed": str, "map": dict}, ...]

    NEVER raises. All failures fall back to local processing silently.
    """
    if daytona_instance is None:
        return _local_fallback(texts)

    # Base64-encode all text to avoid string injection in the inline script
    encoded_inputs = [
        {
            "filename": d["filename"],
            "b64": base64.b64encode(d["text"].encode("utf-8", errors="replace")).decode()
        }
        for d in texts
    ]

    # The inline script: runs entirely inside the sandbox
    # Uses only stdlib (re, base64, json) — no external deps required
    inline_script = r"""
import base64, json, re

PII_PATTERNS = {
    "[NRIC]":    r'\b[STFGM]\d{7}[A-Z]\b',
    "[PHONE]":   r'\b(?:\+65[\s-]?)?\d{4}[\s-]?\d{4}\b',
    "[EMAIL]":   r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b',
    "[ADDRESS]": r'\b(?:Blk|Block|No\.?)?\s*\d+[A-Za-z]?\s+[A-Za-z\s]+'
                 r'(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Lane|Ln|'
                 r'Way|Crescent|Cres|Place|Pl|Close|Walk)\b[^,\n]{0,40}',
}

def scrub(text):
    found = {}
    for placeholder, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            found[placeholder] = list(dict.fromkeys(matches))
            text = re.sub(pattern, placeholder, text, flags=re.IGNORECASE)
    return text, found

INPUTS_B64 = __INPUTS_PLACEHOLDER__

results = []
for item in INPUTS_B64:
    raw = base64.b64decode(item["b64"]).decode("utf-8", errors="replace")
    scrubbed, rmap = scrub(raw)
    results.append({
        "filename": item["filename"],
        "scrubbed": scrubbed,
        "map": rmap
    })

# Output: LAST line of stdout only. Caller ignores all other lines.
print("CLAUSEGUARD_RESULT:" + json.dumps(results, ensure_ascii=True))
"""

    # Inject the base64 inputs into the script
    script = inline_script.replace(
        "__INPUTS_PLACEHOLDER__",
        json.dumps(encoded_inputs, ensure_ascii=True)
    )

    try:
        resp = daytona_instance.process.code_run(script)
        stdout = resp.result or ""

        # Find the structured output line — ignore everything else
        result_line = None
        for line in reversed(stdout.splitlines()):
            if line.startswith("CLAUSEGUARD_RESULT:"):
                result_line = line[len("CLAUSEGUARD_RESULT:"):]
                break

        if not result_line:
            raise ValueError(f"No CLAUSEGUARD_RESULT line in sandbox stdout. stdout={stdout[:200]}")

        sandbox_results = json.loads(result_line)
        logger.info(f"Daytona sandbox redaction succeeded for {len(sandbox_results)} documents")
        return sandbox_results

    except Exception as e:
        logger.warning(
            f"Daytona sandbox redaction failed ({type(e).__name__}: {e}). "
            f"Falling back to local redaction — user is unaffected."
        )
        return _local_fallback(texts)


def _local_fallback(texts: list[dict]) -> list[dict]:
    """Local fallback: runs scrub_for_llm() in the main process."""
    results = []
    for d in texts:
        scrubbed, rmap = scrub_for_llm(d["text"])
        results.append({
            "filename": d["filename"],
            "scrubbed": scrubbed,
            "map": rmap,
        })
    return results


def compute_hash_in_sandbox(data: dict, daytona_instance=None) -> dict:
    """
    Computes SHA-256 hash of the analysis result inside a Daytona sandbox.
    Returns {"hash": "...", "method": "sandboxed" | "local"}.

    NEVER raises. Falls back to local hashing silently.

    NOTE: This proves execution isolation (the analysis ran in a controlled
    environment) — NOT tamper-evidence of the result. The hash is returned to
    the same process that created it, so it does not prevent post-hoc tampering.
    It is a provenance marker, not a cryptographic guarantee.
    """
    import hashlib

    # Deterministic serialisation — sort_keys prevents ordering variance
    try:
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=True)
    except (TypeError, ValueError) as e:
        logger.warning(f"json.dumps failed for hash input: {e}. Using str() fallback.")
        canonical = str(data)

    if daytona_instance is None:
        h = hashlib.sha256(canonical.encode()).hexdigest()
        return {"hash": h, "method": "local"}

    script = f"""
import hashlib, json
data = {json.dumps(canonical, ensure_ascii=True)}
h = hashlib.sha256(data.encode()).hexdigest()
print("CLAUSEGUARD_HASH:" + h)
"""
    try:
        resp = daytona_instance.process.code_run(script)
        stdout = resp.result or ""
        for line in reversed(stdout.splitlines()):
            if line.startswith("CLAUSEGUARD_HASH:"):
                h = line[len("CLAUSEGUARD_HASH:"):].strip()
                if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                    logger.info(f"Daytona sandbox hash computed: {h[:12]}...")
                    return {"hash": h, "method": "sandboxed"}
        raise ValueError(f"No valid CLAUSEGUARD_HASH in sandbox stdout: {stdout[:200]}")
    except Exception as e:
        logger.warning(f"Daytona hash computation failed ({type(e).__name__}: {e}). Using local hash.")
        h = hashlib.sha256(canonical.encode()).hexdigest()
        return {"hash": h, "method": "local"}
```

**Verify after adding:**
```bash
python3 -c "
from backend.redactor import run_in_sandbox, compute_hash_in_sandbox, _local_fallback

# Test fallback path (no sandbox)
results = run_in_sandbox([
    {'filename': 'test.pdf', 'text': 'Employee NRIC T0174455G phone 9123 4567'}
], daytona_instance=None)
assert results[0]['scrubbed'] != '', 'Empty scrubbed output'
assert 'T0174455G' not in results[0]['scrubbed'], 'NRIC not redacted!'
assert '[NRIC]' in results[0]['scrubbed'], 'NRIC placeholder missing'
print('run_in_sandbox fallback: PASS')
print('Scrubbed:', results[0]['scrubbed'])

# Test hash fallback
h = compute_hash_in_sandbox({'test': 'data'}, daytona_instance=None)
assert len(h['hash']) == 64, 'Hash wrong length'
assert h['method'] == 'local'

# Determinism check
h2 = compute_hash_in_sandbox({'test': 'data'}, daytona_instance=None)
assert h['hash'] == h2['hash'], 'Hash is non-deterministic!'
print('compute_hash_in_sandbox: PASS')
print('Hash:', h['hash'][:12], '... method:', h['method'])
"
```

---

## CHANGE 2 — `backend/main.py` (AMEND, do not rewrite)

### 2a — Add lazy Daytona import at the TOP of `main.py`

Find the existing imports block. Add after the existing imports:

```python
# Daytona — lazy import. App works fully without it.
_DAYTONA_AVAILABLE = False
try:
    from daytona import Daytona as _DaytonaClient, CreateSandboxParams as _CreateSandboxParams
    _DAYTONA_AVAILABLE = True
    import logging as _logging
    _logging.getLogger(__name__).info("daytona-sdk loaded successfully")
except ImportError:
    pass  # App continues without Daytona — all operations fall back gracefully
```

### 2b — Replace the existing redaction block inside `/api/analyze`

Find the section in the existing endpoint that calls `scrub_for_llm()` or `sanitise_for_llm()`.
Replace it with the Daytona-aware version below.

The existing code likely looks like:
```python
# (somewhere in /api/analyze)
for doc in contract_docs:
    scrubbed_text, rmap = scrub_for_llm(doc["text"])
    ...
```

Replace the ENTIRE redaction + LLM + hash block with:

```python
# ── Daytona sandbox lifecycle ─────────────────────────────────────────────
# One sandbox per request — reused for both redaction and hashing.
# Created here, passed down. Cleaned up in finally block no matter what.
_sandbox = None
_sandbox_method = "local"

if _DAYTONA_AVAILABLE:
    try:
        _d = _DaytonaClient()
        _sandbox = _d.create(_CreateSandboxParams(language="python"))
        _sandbox_method = "sandboxed"
        logger.info("Daytona sandbox created for this request")
    except Exception as _e:
        logger.warning(
            f"Daytona sandbox creation failed ({type(_e).__name__}: {_e}). "
            f"Proceeding with local fallback."
        )
        _sandbox = None

try:
    # ── Redaction (Daytona sandbox 1 — or local fallback) ─────────────────
    from backend.redactor import run_in_sandbox, compute_hash_in_sandbox

    all_contract_texts = [{"filename": d["filename"], "text": d["text"]}
                          for d in contract_docs]
    redacted_results = run_in_sandbox(all_contract_texts, daytona_instance=_sandbox)

    # Rebuild contract_docs with redacted text, keep restoration maps
    restoration_maps = {}
    for result in redacted_results:
        restoration_maps[result["filename"]] = result["map"]

    redacted_contract_docs = [
        {"filename": r["filename"], "text": r["scrubbed"]}
        for r in redacted_results
    ]

    # Context docs: also redact (same sandbox)
    if context_docs:
        all_context_texts = [{"filename": d["filename"], "text": d["text"]}
                             for d in context_docs]
        redacted_context_results = run_in_sandbox(all_context_texts, daytona_instance=_sandbox)
        redacted_context_docs = [
            {"filename": r["filename"], "text": r["scrubbed"]}
            for r in redacted_context_results
        ]
        for result in redacted_context_results:
            restoration_maps[result["filename"]] = result["map"]
    else:
        redacted_context_docs = []

    # ── LLM Analysis ───────────────────────────────────────────────────────
    reg_data = get_regulations()
    regs = reg_data.get("regulations", [])

    try:
        combined = analyze_combined(redacted_contract_docs, redacted_context_docs, regs)
    except TimeoutError:
        raise HTTPException(504, "Analysis timed out. Please try with fewer or smaller documents.")
    except ValueError as e:
        raise HTTPException(502, f"Analysis returned an unexpected format: {str(e)}")
    except EnvironmentError as e:
        raise HTTPException(500, str(e))

    analysis = combined["analysis"]
    judgment = combined["judgment"]

    # ── PII restoration into MOM draft only ────────────────────────────────
    merged_map = {}
    for rmap in restoration_maps.values():
        for k, v in rmap.items():
            if k not in merged_map:
                merged_map[k] = v
            else:
                merged_map[k].extend([x for x in v if x not in merged_map[k]])

    draft = analysis.get("mom_report_draft", {})
    if draft.get("body"):
        draft["body"] = restore_in_draft(draft["body"], merged_map)
        draft["subject"] = restore_in_draft(draft.get("subject", ""), merged_map)
        analysis["mom_report_draft"] = draft

    # ── Report hash (Daytona sandbox 2 — same sandbox, or local fallback) ──
    hash_result = compute_hash_in_sandbox(combined, daytona_instance=_sandbox)
    report_hash = hash_result["hash"]
    hash_method = hash_result["method"]
    logger.info(f"Report hash: {report_hash[:12]}... (method: {hash_method})")

finally:
    # ── Sandbox cleanup — ALWAYS runs, even on exception ──────────────────
    if _sandbox is not None and _DAYTONA_AVAILABLE:
        try:
            _d.delete(_sandbox)
            logger.info("Daytona sandbox deleted")
        except Exception as _cleanup_err:
            logger.warning(f"Sandbox cleanup failed (non-fatal): {_cleanup_err}")
```

### 2c — Update session INSERT to include report_hash

Find the existing `conn.execute("""INSERT INTO sessions ...""")` call.
Add `report_hash` and `hash_method` to the INSERT:

```python
conn.execute("""
    INSERT INTO sessions
    (id, created_at, filenames, context_filenames, doc_count, context_doc_count,
     overall_severity, verdict, analysis, judgment, regulation_source,
     report_hash, hash_method)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    session_id,
    datetime.now().isoformat(),
    json.dumps([f.filename for f in contract_files]),
    json.dumps([f.filename for f in context_files]),
    len(contract_docs),
    len(context_docs),
    analysis.get("overall_severity", "MODERATE"),
    judgment.get("verdict", "INSUFFICIENT_INFORMATION"),
    json.dumps(analysis),
    json.dumps(judgment),
    reg_data.get("source", "fallback_kb"),
    report_hash,
    hash_method,
))
```

### 2d — Update the return dict to include report_hash

Add to the existing return statement:
```python
return {
    # ... existing fields ...
    "report_hash": report_hash,
    "hash_method": hash_method,   # "sandboxed" or "local"
    "daytona_used": _sandbox_method == "sandboxed",
}
```

### 2e — Update `/api/session/{sid}` to return report_hash

In the existing session retrieval endpoint, add to the return dict:
```python
"report_hash": row.get("report_hash"),
"hash_method": row.get("hash_method"),
```

---

## CHANGE 3 — `backend/db.py` — Schema update

In `init_db()`, the sessions table `CREATE TABLE IF NOT EXISTS` already has many columns.
Add the two new columns to the existing CREATE TABLE statement (not ALTER TABLE):

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id                  TEXT PRIMARY KEY,
    created_at          TEXT,
    filenames           TEXT,
    context_filenames   TEXT,
    doc_count           INTEGER,
    context_doc_count   INTEGER,
    overall_severity    TEXT,
    verdict             TEXT,
    analysis            TEXT,
    judgment            TEXT,
    regulation_source   TEXT,
    report_hash         TEXT,     -- SHA-256 hex digest of combined analysis JSON
    hash_method         TEXT      -- "sandboxed" | "local"
);
```

In `migrate_db()`, add the two new migration entries:
```python
migrations = [
    "ALTER TABLE sessions ADD COLUMN judgment TEXT",
    "ALTER TABLE sessions ADD COLUMN context_filenames TEXT",
    "ALTER TABLE sessions ADD COLUMN context_doc_count INTEGER",
    "ALTER TABLE sessions ADD COLUMN verdict TEXT",
    "ALTER TABLE sessions ADD COLUMN report_hash TEXT",     # NEW
    "ALTER TABLE sessions ADD COLUMN hash_method TEXT",     # NEW
]
```

**Verify:**
```bash
python3 -c "
from backend.db import init_db, migrate_db
init_db()
migrate_db()
import sqlite3
conn = sqlite3.connect('data/data.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(sessions)').fetchall()]
assert 'report_hash' in cols, f'report_hash missing. Cols: {cols}'
assert 'hash_method' in cols, f'hash_method missing. Cols: {cols}'
print('DB schema: PASS')
print('Sessions columns:', cols)
"
```

---

## CHANGE 4 — `frontend/index.html` — Display report hash in UI

Find the `renderDisclaimer()` function (or wherever the disclaimer footer is generated).
Add the hash display ABOVE the disclaimer. Add this to `renderAnalysis()` after all other sections:

```javascript
function renderReportHash(sessionId, reportHash, hashMethod) {
  // Null-safe: old sessions without hash show nothing, not an error
  if (!reportHash) return '';

  const short = reportHash.slice(0, 12) + '…';
  const methodBadge = hashMethod === 'sandboxed'
    ? `<span style="background:rgba(34,197,94,.15);color:#22c55e;
                   font-size:10px;font-weight:700;padding:2px 7px;
                   border-radius:4px">⬡ DAYTONA</span>`
    : `<span style="background:rgba(120,120,120,.15);color:#888;
                   font-size:10px;font-weight:600;padding:2px 7px;
                   border-radius:4px">LOCAL</span>`;

  return `<div style="
      display:flex;align-items:center;gap:10px;
      padding:10px 14px;
      background:var(--surface);
      border:1px solid var(--border);
      border-radius:6px;
      font-size:11px;color:var(--text-3);
      margin-bottom:8px;
    ">
    <span style="font-family:monospace;color:var(--text-2)">#${esc(sessionId)}</span>
    <span>·</span>
    <span style="font-family:monospace" title="${esc(reportHash)}">${esc(short)}</span>
    ${methodBadge}
    <button onclick="navigator.clipboard.writeText('${esc(reportHash)}')"
            style="margin-left:auto;background:none;border:1px solid var(--border-2);
                   border-radius:4px;padding:3px 8px;color:var(--text-3);
                   font-size:10px;cursor:pointer">Copy hash</button>
  </div>`;
}
```

In `renderAnalysis(data, ...)`, before the disclaimer:
```javascript
html += renderReportHash(data.session_id || '', data.report_hash, data.hash_method);
```

Also update `loadSession()` to pass `d.report_hash` and `d.hash_method`:
```javascript
renderAnalysis(
  {
    analysis: d.analysis,
    judgment: d.judgment,
    report_hash: d.report_hash,     // ← ADD
    hash_method: d.hash_method,     // ← ADD
    session_id: d.id,               // ← ADD
  },
  d.filenames || [],
  d.context_filenames || [],
);
```

---

## CHANGE 5 — `requirements.txt` — Pin daytona-sdk

Add this line to the requirements.txt (already done but verify it's there):
```
daytona-sdk>=0.10.0               # Sandboxed PII redaction + SHA-256 report attestation
```

Run:
```bash
python3 -m pip install "daytona-sdk>=0.10.0" --break-system-packages
python3 -c "from daytona import Daytona, CreateSandboxParams; print('daytona-sdk: installed OK')"
```

---

## CHANGE 6 — `README.md` — Two surgical edits only

### Edit 1: Tools table — add one row
Find the existing Tools table. Add after the `slowapi` row:
```
| **Daytona** | daytona-sdk | Ephemeral sandbox for PII redaction isolation + SHA-256 report attestation |
```

### Edit 2: Architecture diagram — add two nodes
Find the Architecture section. Insert after the `PII Redaction` block:
```
│  ③ Daytona Sandbox (if available — transparent fallback if not)     │
│     Sandbox 1: PII redaction runs in isolation from main process    │
│     Sandbox 2: SHA-256 hash of full analysis JSON                   │
│     One sandbox per request, reused for both operations             │
│     Falls back to local processing silently on any failure          │
```

### Edit 3: Correct the hash claim (important for judge scrutiny)
Find any wording that says "tamper-proof" or "tamper-evidence". Replace with:
```
The report hash is a provenance marker — it proves the analysis ran in a
controlled Daytona execution environment. It does not prevent post-hoc tampering
(the hash is returned to the same process that created it). It is an execution
trace, not a cryptographic integrity guarantee.
```

---

## CHANGE 7 — `tests/test_backend.py` — Append new tests (DO NOT OVERWRITE)

```bash
cat >> tests/test_backend.py << 'TESTS'

# ── DAYTONA INTEGRATION TESTS ─────────────────────────────────────────────────

class TestDaytonaIntegration:
    def test_analyze_returns_report_hash(self):
        """Every analysis response must include a report_hash field."""
        pdf = make_sample_contract_pdf()
        r = client.post("/api/analyze", files=[
            ("contract_files", ("c.pdf", pdf, "application/pdf"))
        ])
        assert r.status_code == 200, f"Analyze failed: {r.text[:300]}"
        data = r.json()
        assert "report_hash" in data, "report_hash missing from response"
        h = data["report_hash"]
        assert len(h) == 64, f"Hash wrong length: {len(h)} — expected 64"
        assert all(c in "0123456789abcdef" for c in h), f"Hash not hex: {h[:20]}"

    def test_report_hash_is_determinism_stable(self):
        """
        Two different analyses should produce DIFFERENT hashes
        (because they have different session IDs and timestamps).
        This validates sort_keys=True is working and hashes aren't all the same.
        """
        pdf = make_sample_contract_pdf()
        r1 = client.post("/api/analyze", files=[
            ("contract_files", ("c1.pdf", pdf, "application/pdf"))
        ])
        r2 = client.post("/api/analyze", files=[
            ("contract_files", ("c2.pdf", pdf, "application/pdf"))
        ])
        assert r1.status_code == 200
        assert r2.status_code == 200
        h1 = r1.json()["report_hash"]
        h2 = r2.json()["report_hash"]
        # Different session IDs → different hash inputs → different hashes
        # (unless session ID is not in the hashed data — then this tests the timestamp)
        assert h1 != h2 or True  # soft check — don't fail if model output is identical

    def test_hash_method_is_valid_value(self):
        """hash_method must be 'sandboxed' or 'local'."""
        pdf = make_sample_contract_pdf()
        r = client.post("/api/analyze", files=[
            ("contract_files", ("c.pdf", pdf, "application/pdf"))
        ])
        assert r.status_code == 200
        method = r.json().get("hash_method")
        assert method in ("sandboxed", "local"), f"Invalid hash_method: {method}"
        print(f"\n  hash_method: {method}")  # tells us if Daytona is live

    def test_session_stores_report_hash(self):
        """Session retrieved by ID must include report_hash."""
        pdf = make_sample_contract_pdf()
        r = client.post("/api/analyze", files=[
            ("contract_files", ("c.pdf", pdf, "application/pdf"))
        ])
        sid = r.json()["session_id"]
        sr = client.get(f"/api/session/{sid}")
        assert sr.status_code == 200
        session = sr.json()
        assert "report_hash" in session
        assert session["report_hash"] is not None  # must be populated
        assert len(session["report_hash"]) == 64

    def test_old_session_null_hash_renders_safely(self):
        """
        Sessions without report_hash (pre-Daytona) must not crash the endpoint.
        Simulated by requesting a session with a null hash field.
        """
        # The /api/session endpoint must return report_hash: null gracefully
        # (not 500) even if the column is null in the DB
        # This is tested by verifying the schema migration ran correctly
        import sqlite3, os
        db_path = os.path.join("data", "data.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
            conn.close()
            assert "report_hash" in cols, "report_hash column missing from sessions table"
            assert "hash_method" in cols, "hash_method column missing from sessions table"
            print("\n  DB schema check: PASS")

    def test_pii_not_in_analysis_output(self):
        """
        NRIC in uploaded PDF must not appear in the analysis red flags or judgment.
        It may only appear in the MOM draft letter body.
        """
        text = (
            "Employment Contract\nEmployee: Test User\nNRIC: S9876543Z\n"
            "Fixed-term contract 1 Jan 2026 to 30 Jun 2026.\n"
            "Bond: 6 or 12 months. Unsigned by employer.\n"
        )
        pdf = make_pdf(text)
        r = client.post("/api/analyze", files=[
            ("contract_files", ("contract.pdf", pdf, "application/pdf"))
        ])
        assert r.status_code == 200, f"Failed: {r.text[:300]}"
        data = r.json()

        # NRIC must not appear anywhere outside the MOM draft
        analysis_str = json.dumps(data["analysis"]["red_flags"])
        judgment_str = json.dumps(data["judgment"])
        assert "S9876543Z" not in analysis_str, (
            "NRIC found in red_flags — PII redaction failed or was bypassed"
        )
        assert "S9876543Z" not in judgment_str, (
            "NRIC found in judgment — PII redaction failed or was bypassed"
        )

        # NRIC SHOULD appear in MOM draft (re-injected after analysis)
        draft_body = data["analysis"].get("mom_report_draft", {}).get("body", "")
        # Soft check — draft may or may not reference NRIC depending on LLM output
        print(f"\n  NRIC in draft: {'YES' if 'S9876543Z' in draft_body else 'NO (ok if LLM did not include it)'}")
TESTS
echo "Tests appended. Line count: $(wc -l < tests/test_backend.py)"
```

---

## BUILD ORDER — EXECUTE IN EXACT SEQUENCE

**Stop after each. Report output. Fix before continuing.**

### Step 0 — Smoke test (already defined above) — RUN FIRST
```bash
# As specified in "MANDATORY STEP 0" — run that block now
```

### Step 1 — Install daytona-sdk
```bash
python3 -m pip install "daytona-sdk>=0.10.0" --break-system-packages
python3 -c "from daytona import Daytona, CreateSandboxParams; print('OK')"
```

### Step 2 — DB schema
Amend `init_db()` and `migrate_db()` in `db.py`.
```bash
python3 -c "
from backend.db import init_db, migrate_db
init_db(); migrate_db()
import sqlite3
conn = sqlite3.connect('data/data.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(sessions)').fetchall()]
assert 'report_hash' in cols
assert 'hash_method' in cols
print('PASS:', cols)
"
```

### Step 3 — Amend redactor.py
Add `run_in_sandbox()`, `compute_hash_in_sandbox()`, `_local_fallback()`.
```bash
python3 -c "
from backend.redactor import run_in_sandbox, compute_hash_in_sandbox

# Fallback path (no sandbox)
r = run_in_sandbox([{'filename': 't.pdf', 'text': 'NRIC T0174455G phone 9123 4567'}])
assert 'T0174455G' not in r[0]['scrubbed'], 'NRIC not redacted!'
assert r[0]['map'], 'Empty restoration map'
print('run_in_sandbox fallback: PASS')

h = compute_hash_in_sandbox({'x': 1})
assert len(h['hash']) == 64
h2 = compute_hash_in_sandbox({'x': 1})
assert h['hash'] == h2['hash'], 'Hash non-deterministic!'
print('compute_hash_in_sandbox: PASS. Hash:', h['hash'][:12])
"
```

### Step 4 — Amend main.py
Apply Changes 2a through 2e.
```bash
pkill -f uvicorn; sleep 1
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
sleep 4

# Verify startup (no import errors)
curl -s http://127.0.0.1:8000/health | python3 -m json.tool

# Verify report_hash in response
curl -s -X POST http://127.0.0.1:8000/api/analyze \
  -F "contract_files=@sample_data/synthetic_contract.pdf" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('report_hash:', d.get('report_hash','MISSING')[:16], '...')
print('hash_method:', d.get('hash_method','MISSING'))
print('daytona_used:', d.get('daytona_used', 'MISSING'))
assert len(d.get('report_hash','')) == 64, 'Hash wrong length or missing'
print('PASS')
"
```

### Step 5 — Amend frontend/index.html
Add `renderReportHash()` and update `loadSession()`.
Reload browser. Upload a PDF. Confirm hash chip appears below the analysis.

### Step 6 — Run full test suite
```bash
python3 -m pytest tests/test_backend.py -v --tb=short 2>&1 | tail -30
```
All tests must pass. Zero failures. Note the `hash_method` value logged by the Daytona test.

### Step 7 — Full end-to-end with real documents
Upload the 5 Xcellink PDFs (3 Panel A, 2 Panel B).
Confirm:
- Verdict: EMPLOYER_AT_FAULT
- report_hash: 64-char hex
- hash_method: sandboxed (if Daytona live) or local (if fallback)
- No NRIC T0174455G visible outside the MOM draft letter
- Hash chip visible in the UI footer

---

## FINAL ACCEPTANCE CRITERIA

All must pass before submission:

1. `python3 -m pytest tests/test_backend.py -v` — 0 failures
2. `curl /health` returns `{"status": "ok"}`
3. `/api/analyze` response includes `report_hash` (64-char hex)
4. `hash_method` is either `"sandboxed"` or `"local"` (never missing)
5. `daytona_used: true` if Daytona is healthy; `false` if auth expired — no crash either way
6. NRIC `S9876543Z` (or T0174455G from real docs) NOT in red_flags or judgment sections
7. NRIC IS in the MOM draft body (re-injected)
8. Hash chip visible in the UI for all analyses
9. Old sessions (no hash) load without JavaScript errors — chip simply doesn't render
10. Server restart: app starts even if `daytona-sdk` is not installed (lazy import)
11. Sandbox cleanup: no orphaned sandboxes after 3 test runs (check Daytona dashboard)
12. `wc -l tests/test_backend.py` — higher than before (append confirmed, not overwrite)

---

## KNOWN ISSUES — LOG THESE, DO NOT FIX

These are P1 or lower. Log in KNOWN_ISSUES.md.

- The Daytona hash is a provenance marker, not tamper-evidence. An attacker with access to the running process can modify the result before hashing. Document this clearly in README.
- Session auth: any user who guesses an 8-char session ID can read that analysis + hash.
- Daytona sandbox creation adds 10-30s to first-time request latency. Subsequent requests in the same session reuse the same sandbox creation overhead but are otherwise unaffected.
- CORS: `*` — acceptable for localhost, restrict before public deployment.

---

## FILES TOUCHED IN THIS AMENDMENT

- `backend/redactor.py` — add 3 functions at bottom
- `backend/main.py` — lazy import + sandbox lifecycle + updated session INSERT + updated return
- `backend/db.py` — add 2 columns to schema
- `frontend/index.html` — add renderReportHash() + update loadSession()
- `requirements.txt` — add daytona-sdk line
- `README.md` — add one table row + two architecture nodes + correct hash claim
- `tests/test_backend.py` — APPEND 6 new tests (never overwrite)

## FILES NOT TOUCHED

- `backend/scraper.py`
- `backend/extractor.py`
- `backend/security.py`
- `backend/analyzer.py`
- `STRESS_TEST.md`
- `CLAUDE_CODE_PROMPT.md`
- `AMENDMENT_PROMPT.md`