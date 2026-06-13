"""
backend/redaction.py
Thin adapter over src/redactor.py for the analyze flow. Does NOT reimplement
the Daytona logic -- it just calls src.redactor.redact per document and runs
the documents concurrently so N sandbox round-trips don't serialise.

Each document is redacted BEFORE its text is handed to the analyzer/LLM. A
per-document wall-clock cap guarantees a hung sandbox can't freeze the request:
on timeout we fall back to the in-process redactor (privacy preserved).
"""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from src.redactor import redact, redact_local

# Hard wall-clock cap per document's redaction (the Daytona path includes a
# sandbox create/run/delete). Beyond this we use the local engine instead.
REDACT_TIMEOUT_S = 45


def _redact_one(doc: dict) -> dict:
    """Redact a single {filename, text}. Never raises -- always returns a doc."""
    text = doc.get("text", "")
    result = redact(text)  # already falls back to local on sandbox errors
    return {
        "filename": doc.get("filename", "document"),
        "text": result["redacted_text"],          # redacted text for the LLM
        "redaction_report": result.get("redaction_report", {}),
        "total_redactions": result.get("total_redactions", 0),
        "engine": result.get("engine", "local"),
    }


def redact_documents(docs: list) -> list:
    """Redact a list of {filename, text} concurrently.

    Returns a parallel list of {filename, text(redacted), redaction_report,
    total_redactions, engine}. Order is preserved.
    """
    if not docs:
        return []

    out: list = [None] * len(docs)
    with ThreadPoolExecutor(max_workers=min(len(docs), 5)) as pool:
        futures = {pool.submit(_redact_one, d): i for i, d in enumerate(docs)}
        for fut, i in futures.items():
            try:
                out[i] = fut.result(timeout=REDACT_TIMEOUT_S)
            except (FuturesTimeout, Exception):  # noqa: BLE001
                # Sandbox hung or errored past the wrapper -> local fallback so
                # the request never sends un-redacted text and never freezes.
                d = docs[i]
                loc = redact_local(d.get("text", ""))
                out[i] = {
                    "filename": d.get("filename", "document"),
                    "text": loc["redacted_text"],
                    "redaction_report": loc["redaction_report"],
                    "total_redactions": loc["total_redactions"],
                    "engine": "local",
                }
    return out
