# BeePDF v2 Upgrade Summary

## What Changed

BeePDF v2 upgrades the original PDF-to-audio pipeline into a runnable local Document AI demo. The service now ingests local documents, creates page-level chunks, retrieves source-grounded contexts, and generates Q&A, Study Kit, Audio Script, and GraphRAG-lite concept maps with citations.

## Added Technologies And Why

| Area | Added technology | Why it was added |
| --- | --- | --- |
| API | FastAPI entrypoint in `app/main.py` | Makes the demo executable through `/docs` instead of remaining as isolated functions. |
| Parsing | PyMuPDF-based local PDF parsing | Extracts text-layer PDFs locally without paid APIs. |
| OCR fallback | Tesseract via `LocalTesseractOCRProvider` | Handles image-only/scanned PDFs in a free local demo path. It remains replaceable by cloud OCR later. |
| Chunking | Page-level chunk schema | Preserves `page`, `chunk_id`, and char offsets so every answer can cite its source. |
| Retrieval | Keyword/TF-IDF style local retriever | Provides lightweight source retrieval without embeddings, FAISS, or GPU/model downloads. |
| RAG | Source-grounded answer generator | Prevents unsupported answers by returning sources from retrieved chunks only. |
| Study Kit | Rule/template generator | Produces summary, key points, glossary, quiz, and expected questions while preserving sources. |
| Audio Script | Source-grounded script modes | Supports `brief_1min`, `briefing_3min`, `lecture`, and `podcast` modes without requiring real TTS. |
| GraphRAG-lite | Heuristic concept map builder | Adds relationship/context visualization with evidence-backed edges without heavy LLM extraction. |
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
- `.txt`, `.md`, `.pdf` ingest
- Text-layer PDF parsing
- Tesseract OCR fallback for image-only PDFs
- Page-level chunks with source metadata
- Keyword/TF-IDF retrieval
- Source-grounded Q&A
- Study Kit generation
- Audio Script generation
- GraphRAG-lite concept map
- Output artifacts under `outputs/{doc_id}`

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
31 tests OK
```

Manual checks performed:

- FastAPI `/docs` and OpenAPI route registration
- Text-layer Korean NLP lecture PDF ingest: 36 pages, 39 chunks
- Image-only PDF OCR fallback through Tesseract
- Source-grounded ask/study-kit/audio-script/concept-map from OCR output

## Current Limits

- Retrieval is keyword/TF-IDF style, not embedding based.
- LLM output is mock/rule based, not paid API quality.
- TTS is mock and returns `audio_path: null`.
- GraphRAG-lite uses heuristics, not LLM-based entity/relation extraction.
- Korean OCR quality depends on installed Tesseract language data.
