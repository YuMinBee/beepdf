# Repository Structure

This repository intentionally keeps v1 and v2 side by side.

## Version Boundaries

| Area | Version | Role |
| --- | --- | --- |
| `app/main.py` | v1 | Legacy FastAPI PDF-to-audio service with OCR, Studio, Voice, Object Storage, DB logging, and request tracking. |
| `db/` | v1 | Database schema and metadata for the original cloud service. |
| `infra/` | v1 | NCP/cloud deployment and infrastructure notes. |
| `web/` | v1 | Original web/static frontend assets. |
| `v2/` | v2 | Local-first Course Pack Document AI package. |
| `v2/main.py` | v2 | FastAPI entrypoint for the v2 local demo. |
| `tests/` | v2 | Current local tests for v2 behavior. |
| `docs/` | shared | Versioned architecture, provider, workflow, and evaluation documentation. |

## Why v2 Is Separate

v1 was built as a production-style PDF-to-audio pipeline. v2 changes the product direction into a learning-oriented Document AI system:

```text
multiple lecture PDFs
-> Course Pack
-> source-grounded RAG
-> Study Kit / Q&A / Audio Script
-> GraphRAG-lite Concept Map
```

Because the product direction changed, v2 has a separate package and FastAPI entrypoint instead of being mixed into `app/main.py`.

## Run Targets

v1 legacy service:

```bash
uvicorn app.main:app
```

v2 local demo:

```bash
uvicorn v2.main:app --reload --port 8000
```

## Naming Rule Going Forward

- New Course Pack features should go under `v2/`.
- New v2 API routes should go under `v2/api/`.
- New v2 tests should stay in `tests/` and use `test_v2_...` names when endpoint-level behavior is involved.
- Legacy PDF-to-audio maintenance stays in `app/main.py` or a future `v1/` extraction.
