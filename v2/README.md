# BeePDF v2

This directory contains the v2 scaffold for local document ingest, page-level chunking, lightweight retrieval, source-grounded answering, study-kit generation, source-grounded audio-script generation, GraphRAG-lite concept maps, LangGraph-style workflow orchestration, and cloud-ready provider adapters.

The default implementation is intentionally local and lightweight. Heavy components such as Docling, sentence-transformers, FAISS, Chroma, external LLMs, and TTS APIs can be added through providers without changing the workflow contract.

## Modules

- `ingest.py`: local `.pdf`, `.txt`, and `.md` document ingest
- `documents.py`: local document/chunk loading helpers
- `schemas.py`: shared serializable models
- `api/schemas.py`: Pydantic request and response models
- `providers/`: storage, LLM, TTS, and index provider contracts
- `rag/chunking.py`: page-level chunking with `page`, `chunk_id`, and char offsets
- `rag/retrieval.py`: lightweight keyword/TF-IDF style retrieval
- `rag/answering.py`: source-grounded answer generation
- `study_kit.py`: rule/template based study-kit generation with sources
- `audio_script.py`: source-grounded audio script generation
- `graph/concept_map.py`: heuristic GraphRAG-lite concept map builder
- `workflows/`: state and node functions
- `api/routes.py`: FastAPI route skeleton wired to local service functions

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

PDF ingest tries `pymupdf4llm` first and `PyMuPDF` second. If neither is installed, the function returns a warning instead of crashing the app. Text and Markdown ingest do not require extra dependencies.

## Chunk Schema

```json
{
  "chunk_id": "p3_c2",
  "page": 3,
  "text": "...",
  "char_start": 1200,
  "char_end": 1800,
  "metadata": {
    "filename": "sample.pdf"
  }
}
```

Empty pages are skipped during chunking, while `pages.json` can still preserve parsed page records.

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
      "sources": [{"page": 1, "chunk_id": "p1_c1"}]
    }
  ],
  "tts_status": "mock",
  "audio_path": null
}
```

## GraphRAG-lite Concept Map

`build_concept_map()` creates heuristic nodes and edges from chunk text. Every edge includes source evidence from the chunk that produced it. If no graph can be built, it returns empty `nodes` and `edges` with a warning. GraphRAG-lite remains a helper feature and is not required for answer generation.

## FastAPI v2 Endpoints

The route skeleton uses Pydantic request and response models for the main v2 API surface:

- `POST /v2/documents/ingest`
- `GET /v2/documents/{doc_id}`
- `POST /v2/ask`
- `POST /v2/study-kit`
- `POST /v2/audio-script`
- `POST /v2/concept-map`

Compatibility aliases remain for `/v2/ingest`, `/v2/retrieve`, and `/v2/answer`.

## Resource Policy

The scaffold does not run embedding models or paid LLM APIs by default. It is safe to inspect and extend on a small local machine while GPU workloads are running elsewhere.


