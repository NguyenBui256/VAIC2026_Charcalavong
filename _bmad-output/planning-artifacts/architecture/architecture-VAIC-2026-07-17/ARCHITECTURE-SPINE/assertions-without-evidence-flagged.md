# Assertions Without Evidence (Flagged)

1. **`wasmtime-py` as production sandbox replacement (line 199):** The spine mentions `wasmtime-py` as a future production sandbox upgrade. This was not web-verified in the spine and the package's current status was not confirmed in this review either. It is deferred, so it is not blocking, but builders should verify `wasmtime-py` exists and supports the use case before relying on the note.

2. **"E2B" as alternative sandbox (line 199):** E2B (e2b.dev) is a cloud sandbox service. Not verified in this review. Same status as wasmtime-py — deferred, not blocking.

3. **TanStack Router or React Router (line 291):** The spine mentions "TanStack Router or React Router" for file-based routing without committing to one. TanStack Router is real and maintained (part of the TanStack ecosystem). React Router v7 is also current. This ambiguity is a design decision, not a factual error, but the spine should note which is the default to prevent builder divergence.

---
