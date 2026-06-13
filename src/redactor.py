"""
src/redactor.py
Daytona sandbox: regex-based PII redaction of extracted contract text.
Stdlib only (re, json) -- no extra installs needed in the sandbox image,
same proven pattern as sandbox_validate.py.

Redacts (best-effort): Singapore NRIC/FIN numbers, email addresses,
Singapore phone numbers, and common residential-address patterns
(unit numbers, blocks, 6-digit postal codes).

Returns {redacted_text, redaction_report}. The redaction_report lists
WHAT TYPES were redacted and HOW MANY of each -- it never echoes the
original PII values back out of the sandbox.

IMPORTANT: the contract text is NOT embedded in the script source -- it
is uploaded to the sandbox as a file (sandbox.fs.upload_file) and read
back inside the script. This avoids any source-escaping fragility (the
redaction regexes already contain brace quantifiers like \\d{7} and
{2,}, and contract text can contain arbitrary quotes/backslashes).
"""

import os
import re
import json

# ── Single source of truth for the redaction patterns ────────────────────────
# (label, regex_string, flags). Used BOTH locally (compiled below) and inside
# the Daytona sandbox (injected as JSON, recompiled there) so the two paths can
# never drift. Order matters: emails first (their local part can contain digit
# runs that would otherwise look like phone numbers), then NRIC, phone, address.
_PATTERN_SPECS = [
    # Singapore NRIC / FIN: [STFG] + 7 digits + checksum letter.
    ("NRIC", r"\b[STFGstfg]\d{7}[A-Za-z]\b", 0),
    # Email addresses.
    ("EMAIL", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", 0),
    # Singapore phone numbers: optional +65, then an 8-digit number starting
    # 3/6/8/9, allowing a space or hyphen in the middle (9123 4567).
    ("PHONE", r"(?<!\d)(?:\+?65[\s-]?)?[3689]\d{3}[\s-]?\d{4}(?!\d)", 0),
    # Address fragments: unit numbers (#12-345), block numbers (Blk/Block 123),
    # and 6-digit Singapore postal codes (often preceded by "Singapore").
    ("ADDRESS",
     r"#\d{1,3}-\d{1,4}[A-Za-z]?"
     r"|\b(?:Blk|Block)\s+\d{1,4}[A-Za-z]?\b"
     r"|\bSingapore\s+\d{6}\b"
     r"|(?<!\d)\d{6}(?!\d)",
     re.IGNORECASE),
]

_COMPILED = [(label, re.compile(pat, flags)) for label, pat, flags in _PATTERN_SPECS]


def _apply_patterns(text: str) -> tuple:
    """Run every pattern's subn over `text`. Returns (redacted_text, report)."""
    report = {}
    for label, rx in _COMPILED:
        text, count = rx.subn("[REDACTED_%s]" % label, text)
        if count:
            report[label] = count
    return text, report


def redact_local(contract_text: str) -> dict:
    """In-process redaction using the same patterns as the sandbox.

    The privacy-preserving fallback when Daytona is unavailable: the LLM still
    never sees un-redacted text. Loses only the "ran in Daytona" property.
    """
    redacted, report = _apply_patterns(contract_text)
    return {
        "redacted_text": redacted,
        "redaction_report": report,
        "total_redactions": sum(report.values()),
        "engine": "local",
    }


# Sandbox script: reads the uploaded text, recompiles the SAME specs, redacts,
# emits JSON. `__SPECS_JSON__` is replaced (not .format) with json.dumps of
# _PATTERN_SPECS -- a valid Python list literal whose backslashes/braces are
# already escaped by JSON, so it can't break the source.
REDACTION_SCRIPT = r'''
import re, json

with open("/tmp/contract.txt", "r", encoding="utf-8") as f:
    text = f.read()

SPECS = __SPECS_JSON__

redaction_report = {}
for label, pat, flags in SPECS:
    rx = re.compile(pat, flags)
    text, count = rx.subn("[REDACTED_%s]" % label, text)
    if count:
        redaction_report[label] = count

result = {
    "redacted_text": text,
    "redaction_report": redaction_report,
    "total_redactions": sum(redaction_report.values()),
}
print(json.dumps(result))
'''


def _redact_daytona(contract_text: str) -> dict:
    """Run regex PII redaction inside a Daytona sandbox. Raises on any failure."""
    api_key = os.environ.get("DAYTONA_API_KEY")
    if not api_key:
        raise RuntimeError("DAYTONA_API_KEY is not set")

    from daytona import Daytona, DaytonaConfig  # imported lazily so local-only

    daytona = Daytona(DaytonaConfig(api_key=api_key))
    sandbox = daytona.create()
    try:
        # Upload the contract text as a file rather than embedding it in the
        # script source -- see module docstring.
        sandbox.fs.upload_file(contract_text.encode("utf-8"), "/tmp/contract.txt")

        script = REDACTION_SCRIPT.replace("__SPECS_JSON__", json.dumps(_PATTERN_SPECS))
        run = sandbox.process.code_run(script)
        if run.exit_code != 0:
            raise RuntimeError(f"Sandbox redaction failed: {run.result}")

        out = json.loads(run.result.strip())
        out["engine"] = "daytona"
        return out
    finally:
        sandbox.delete()


def redact(contract_text: str) -> dict:
    """Redact PII, preferring the Daytona sandbox, falling back to local regex.

    Returns {redacted_text, redaction_report, total_redactions, engine}. The
    LLM is NEVER handed un-redacted text: if the sandbox errors or times out,
    we run the identical patterns in-process instead of failing open.
    """
    try:
        return _redact_daytona(contract_text)
    except Exception as e:  # noqa: BLE001 -- any sandbox failure -> local fallback
        out = redact_local(contract_text)
        out["fallback_reason"] = str(e)[:200]
        return out


if __name__ == "__main__":
    import pdfplumber

    # 1) Real run against the synthetic contract's extracted text.
    with pdfplumber.open("sample_data/synthetic_contract.pdf") as pdf:
        contract = "\n".join(p.extract_text() or "" for p in pdf.pages)

    print("=== Synthetic contract (redact -> Daytona, fallback local) ===")
    out = redact(contract)
    print("engine:", out["engine"])
    print("redaction_report:", json.dumps(out["redaction_report"]))
    print("total_redactions:", out["total_redactions"])

    # Force-local path must produce identical counts (no drift between engines).
    loc = redact_local(contract)
    print("local engine report:", json.dumps(loc["redaction_report"]),
          "| matches daytona:", loc["redaction_report"] == out["redaction_report"])

    # 2) Mechanism check: inject one of each PII type and confirm each
    #    pattern fires and that no original value leaks into the report.
    probe = (
        "Employee NRIC: S1234567A. Contact: alex.tan@example.com or +65 9123 4567. "
        "Address: Blk 123 Clementi Ave 3 #12-345 Singapore 120123. "
        "Office line 6789 0123. Monthly salary S$3,000.00 paid on the 1st."
    )
    print("\n=== PII probe ===")
    out2 = redact(probe)
    print("redaction_report:", json.dumps(out2["redaction_report"]))
    print("redacted_text:", out2["redacted_text"])
    # Salary/date must survive; PII must be gone.
    leaked = [v for v in ["S1234567A", "alex.tan@example.com", "9123 4567", "120123"]
              if v in out2["redacted_text"]]
    print("LEAKED (should be []):", leaked)
    print("salary preserved:", "S$3,000.00" in out2["redacted_text"])
