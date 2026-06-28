# BeePDF v2 Upgrade Summary

## What Changed

BeePDF v2 upgrades the original PDF-to-audio pipeline into a runnable local Document AI demo. The service now ingests local documents, creates page-level chunks, retrieves source-grounded contexts, and generates Q&A, Study Kit, Audio Script, and GraphRAG-lite concept maps with citations.

## Added Technologies And Why

| Area | Added technology | Why it was added |
| --- | --- | --- |
| API | FastAPI v2 demo entrypoint in `v2/main.py` | Makes the demo executable through `/docs` instead of remaining as isolated functions. |
| Parsing | PyMuPDF-based local PDF parsing and dependency-free PPTX slide parsing | Extracts text-layer PDFs and lecture slide text locally without paid APIs. |
| OCR fallback | Tesseract via `LocalTesseractOCRProvider` | Handles image-only/scanned PDFs in a free local demo path. It remains replaceable by cloud OCR later. |
| Chunking | Page-level chunk schema | Preserves `page`, `chunk_id`, and char offsets so every answer can cite its source. |
| Retrieval | Keyword/TF-IDF style local retriever | Provides lightweight source retrieval without embeddings, FAISS, or GPU/model downloads. |
| RAG | Source-grounded answer generator with Korean templates | Prevents unsupported answers by returning sources from retrieved chunks only, then formats the evidence as readable Korean answers. |
| LLM API | `OpenAIProvider` using the Responses API | Adds optional API-backed Korean summary refinement while preserving mock/rule fallback when no API key is configured. |
| Citation Check | Term-overlap source grounding validator | Blocks unsupported LLM summary refinements and falls back to rule-based source-grounded output. |
| Course Pack | Multi-document pack service with balanced overview retrieval | Groups several lecture files into one learning unit, keeps `doc_id`, `filename`, `page`, and `chunk_id` on every source, and prevents overview answers from being dominated by a single file. |
| Study Kit | Rule/template generator | Produces summary, key points, glossary, quiz, and expected questions while preserving sources. |
| Audio Script | Source-grounded script modes | Supports `brief_1min`, `briefing_3min`, `lecture`, and `podcast` modes without requiring real TTS. |
| GraphRAG-lite | Heuristic concept map builder plus Mermaid/HTML export | Adds relationship/context visualization with evidence-backed edges and portfolio-friendly concept map artifacts without heavy LLM extraction. |
| Providers | Storage/Parser/OCR/LLM/TTS/Index interfaces | Keeps the local demo replaceable by cloud object storage, managed OCR, external LLM, managed vector DB, and real TTS. |
| Tests | Local unit/service/E2E-style tests | Verifies ingest, chunks, source-grounded ask, study kit, audio script, concept map, OCR fallback, and API routes. |

## Why These Changes Fit The Existing Project

The original BeePDF architecture focused on document processing, cost reduction, request tracing, OCR fallback, TTS, and object storage. v2 keeps that direction but upgrades the service layer first, because the full cloud architecture is expensive and harder to reproduce locally.

The result is a local-first but cloud-ready implementation:

- Local providers keep the demo free and reproducible.
- Provider interfaces keep the production path open.
- Source citations make PDF answers auditable.
- OCR fallback makes scanned PDFs part of the same RAG workflow.
- GraphRAG-lite adds document relationship analysis without overbuilding Microsoft GraphRAG.

## Implemented Locally

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
- `.txt`, `.md`, `.pdf`, `.pptx` ingest
- Text-layer PDF parsing
- Tesseract OCR fallback for image-only PDFs
- Page/slide-level chunks with `doc_id`, `filename`, `page`, and `chunk_id` source metadata
- Multi-document Course Pack ingest and pack-level generation
- Balanced Course Pack overview retrieval across lecture files
- Course Pack Summary generation with sources
- Optional `OpenAIProvider` summary refinement with safe fallback
- Citation check for LLM-refined summaries
- Keyword/TF-IDF retrieval
- Source-grounded Q&A
- Study Kit generation
- Audio Script generation
- GraphRAG-lite concept map
- Course Pack artifact preview endpoint
- Mermaid/HTML concept map export
- Output artifacts under `outputs/{doc_id}` and `outputs/course_packs/{pack_id}`

## Designed As Optional Future Replacements

- `LocalStorageProvider` -> Object Storage provider
- `LocalTesseractOCRProvider` -> CLOVA OCR or managed OCR provider
- `MockLLMProvider` -> CLOVA Studio, OpenAI, or Ollama provider
- `MockTTSProvider` -> CLOVA Voice or local TTS provider
- `LocalIndexProvider` -> FAISS, Chroma, or managed vector DB provider
- In-process workflow -> Queue-based worker execution

## Validation

Current local validation:

```text
python -m unittest discover -s tests
48 tests OK
```

Manual checks performed:

- FastAPI `/docs` and OpenAPI route registration
- Text-layer Korean NLP lecture PDF ingest: 36 pages, 39 chunks
- 11-week PPTX Course Pack ingest: 3 documents, 112 chunks
- Course Pack overview answer sources balanced across 1차시, 2차시, and 3차시 PPTX files
- Course Pack summary generated from 11-week PPTX pack with 3 lecture summaries, 5 key concepts, and 5 concept connections
- Course Pack demo document added at `docs/COURSE_PACK_DEMO.md`
- 11-week concept map exported to Mermaid/HTML with 60 nodes and 120 edges for visual review
- Citation check verifies grounded LLM refinements and rejects unsupported generated terms
- Image-only PDF OCR fallback through Tesseract
- Source-grounded ask/study-kit/audio-script/concept-map from OCR output

## Current Limits

- Retrieval is keyword/TF-IDF style, not embedding based.
- LLM output defaults to mock/rule mode. API refinement requires `OPENAI_API_KEY` and explicit `llm_provider: "openai"`. Refined output must pass `citation_check` or BeePDF falls back to the rule-based summary.
- TTS is mock and returns `audio_path: null`.
- GraphRAG-lite uses heuristics, not LLM-based entity/relation extraction. Mermaid/HTML export is capped by default to keep large graphs readable.
- Korean OCR quality depends on installed Tesseract language data.













