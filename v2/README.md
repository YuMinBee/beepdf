# BeePDF v2

This directory contains the v2 local demo for document ingest, PPTX lecture ingest, Course Pack aggregation, page-level chunking, lightweight retrieval, source-grounded answering, study-kit generation, audio-script generation, GraphRAG-lite concept maps, LangGraph-style workflow orchestration, and cloud-ready provider adapters.

The default implementation is intentionally local and lightweight. Heavy components such as Docling, sentence-transformers, FAISS, Chroma, external LLMs, and TTS APIs can be added through providers without changing the workflow contract. `OpenAIProvider` is available as an optional API-backed LLM provider and falls back to rule/mock behavior when `OPENAI_API_KEY` is not configured. API-refined summaries are accepted only when `citation_check` confirms they are grounded in retrieved source chunks.

## Modules

- `ingest.py`: local `.pdf`, `.pptx`, `.txt`, and `.md` document ingest
- `documents.py`: local document/chunk loading helpers
- `course_packs.py`: multi-document Course Pack ingest and pack-level generation helpers
- `course_summary.py`: Course Pack summary generation with source-preserving rule output and optional OpenAI refinement
- `schemas.py`: shared serializable models
- `api/schemas.py`: Pydantic request and response models
- `providers/`: storage, LLM, TTS, OCR, parser, and index provider contracts
- `rag/chunking.py`: page-level chunking with `page`, `chunk_id`, char offsets, `doc_id`, and `filename`
- `rag/retrieval.py`: lightweight keyword/TF-IDF style retrieval
- `rag/answering.py`: source-grounded answer generation
- `study_kit.py`: rule/template based study-kit generation with sources
- `audio_script.py`: source-grounded audio script generation
- `graph/concept_map.py`: heuristic GraphRAG-lite concept map builder
- `workflows/`: state and node functions
- `api/routes.py`: FastAPI routes wired to local service functions

## Local Ingest

`ingest_local_document()` writes this artifact structure:

```text
outputs/{doc_id}/
- document.json
- pages.json
- chunks.json
- graph.json
- answers/
- study_kit.json
- audio_script.json
```

PDF ingest tries `pymupdf4llm` first and `PyMuPDF` second. If the text layer is empty, BeePDF tries local Tesseract OCR. PPTX ingest reads slide text from the `.pptx` zip/XML package with the Python standard library and maps each slide to the existing `page` field. If optional PDF libraries are unavailable, the app returns warnings instead of crashing. Text, Markdown, and PPTX ingest do not require extra dependencies.

## Chunk Schema

```json
{
  "chunk_id": "p3_c2",
  "page": 3,
  "text": "...",
  "char_start": 1200,
  "char_end": 1800,
  "metadata": {
    "doc_id": "sha256-doc-id",
    "filename": "sample.pdf",
    "pack_id": "pack_abc123"
  }
}
```

Empty pages are skipped during chunking, while `pages.json` can still preserve parsed page records.

## Course Pack Ingest

Course Packs aggregate multiple documents into one learning unit. Each input file still receives its own `doc_id`, while pack-level chunks preserve `doc_id`, `filename`, `page`, and `chunk_id` for source-grounded outputs.

```json
{
  "paths": ["week1.pdf", "week2.pdf", "week3.pdf"],
  "output_root": "outputs"
}
```

The pack artifact structure is:

```text
outputs/course_packs/{pack_id}/
- course_pack.json
- chunks.json
- graph.json
- answers/
- study_kit.json
- summary.json
- audio_script.json
- concept_map.mmd
- concept_map.html
```

Pack-level Q&A, Summary, Study Kit, Audio Script, Concept Map, artifact preview, and Mermaid/HTML concept map export use the aggregated chunks. A verified local walkthrough is documented in `docs/COURSE_PACK_DEMO.md`. Overview-style pack queries balance retrieval across documents so each lecture can contribute source evidence to the final answer. Concept Map adds document nodes and `appears_in` edges so shared concepts across lecture files are visible.

## Local Retrieval

The first retrieval implementation avoids embedding models and uses a simple keyword/TF-IDF style scorer. It returns only matched contexts.

Source-grounded answer generation returns an answer only when retrieval provides at least one source chunk. If no context is found, the answer is empty and a warning is returned.

## OCR Fallback

Image-only PDFs can flow through a real local OCR fallback when Tesseract is installed:

```text
empty PDF text layer -> LocalTesseractOCRProvider -> PageMarkdown -> chunks -> v2 services
```

`MockOCRProvider` is available for deterministic tests. `LocalTesseractOCRProvider` renders PDF pages with PyMuPDF and extracts text with Tesseract through `pytesseract`.

## Audio Script Modes

`generate_audio_script()` supports:

- `brief_1min`
- `briefing_3min`
- `lecture`
- `podcast`

The response keeps sources on every script segment and uses mock TTS by default:

```json
{
  "mode": "briefing_3min",
  "script": [
    {
      "speaker": "narrator",
      "text": "...",
      "sources": [{"doc_id": "...", "filename": "week1.pdf", "page": 1, "chunk_id": "p1_c1"}]
    }
  ],
  "tts_status": "mock",
  "audio_path": null
}
```

## GraphRAG-lite Concept Map

`build_concept_map()` creates heuristic nodes and edges from chunk text. Every edge includes source evidence from the chunk that produced it. For Course Packs, document nodes and `appears_in` edges make cross-document concept links visible. If no graph can be built, it returns empty `nodes` and `edges` with a warning.

GraphRAG-lite remains a helper feature and is not required for answer generation. Course Pack concept maps can also be exported to `concept_map.mmd` and `concept_map.html` for easier visual review.

## FastAPI v2 Endpoints

The route skeleton uses Pydantic request and response models for the main v2 API surface:

- `POST /v2/documents/ingest`
- `GET /v2/documents/{doc_id}`
- `POST /v2/ask`
- `POST /v2/study-kit`
- `POST /v2/audio-script`
- `POST /v2/concept-map`
- `POST /v2/course-packs`
- `GET /v2/course-packs/{pack_id}`
- `GET /v2/course-packs/{pack_id}/artifacts`
- `POST /v2/course-packs/ask`
- `POST /v2/course-packs/study-kit`
- `POST /v2/course-packs/summary`
- `POST /v2/course-packs/audio-script`
- `POST /v2/course-packs/concept-map`
- `POST /v2/course-packs/concept-map/export`

Compatibility aliases remain for `/v2/ingest`, `/v2/retrieve`, and `/v2/answer`.

## Resource Policy

The scaffold does not run embedding models or paid LLM APIs by default. To try API refinement, set `OPENAI_API_KEY` and send `llm_provider: "openai"`; otherwise summary generation uses source-grounded rule/mock output. If citation validation fails, BeePDF returns the rule-based summary with a warning instead of using unsupported LLM text. It is safe to inspect and extend on a small local machine while GPU workloads are running elsewhere.







