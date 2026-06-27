# BeePDF

BeePDF v2는 PDF 문서를 page-level RAG와 GraphRAG-lite로 구조화하고, 요약·Q&A·Study Kit·음성 대본 생성을 source-grounded 방식으로 제공하는 cloud-ready Document AI 플랫폼입니다. 현재 버전은 비용 없이 재현 가능한 local provider를 기본값으로 사용하지만, Storage/LLM/TTS/Index 계층을 provider interface로 분리하여 향후 클라우드 Object Storage, 외부 LLM API, managed vector DB로 교체할 수 있게 설계했습니다.

## BeePDF v2 Goal

BeePDF v2 turns local `.pdf`, `.txt`, and `.md` documents into page-level chunks, retrieves source chunks for a question, and generates grounded outputs that keep page citations. The local demo avoids paid APIs, embedding models, and GPU workloads.

## Local-first But Cloud-ready

The default providers are local or mock implementations:

| Interface | Local demo | Future replacement |
| --- | --- | --- |
| `StorageProvider` | `LocalStorageProvider` | Object Storage provider |
| `ParserProvider` | `LocalParserProvider` | Managed parser/OCR worker |
| `LLMProvider` | `MockLLMProvider` | ClovaStudioProvider, OpenAIProvider, OllamaProvider |
| `TTSProvider` | `MockTTSProvider` | ClovaVoiceProvider, LocalTTSProvider |
| `IndexProvider` | `LocalIndexProvider` / `SimpleRetriever` | ManagedVectorDBProvider |
| Workflow | In-process functions | Queue-based worker execution |

## v2 Endpoints

- `POST /v2/documents/ingest`
- `GET /v2/documents/{doc_id}`
- `POST /v2/ask`
- `POST /v2/study-kit`
- `POST /v2/audio-script`
- `POST /v2/concept-map`

Compatibility aliases also exist for `/v2/ingest`, `/v2/retrieve`, and `/v2/answer`.


## Run The Local API

Install the lightweight API dependencies when you want to run the FastAPI demo:

```bash
pip install -r requirements-v2.txt
```

Start the local API:

```bash
uvicorn app.v2_main:app --reload --port 8000
```

Open the interactive docs:

```text
http://127.0.0.1:8000/docs
```

The v2 demo entrypoint is separated as `app/v2_main.py` so the existing legacy `app/main.py` can stay intact. The `/docs` page should show `/health`, `/v2/documents/ingest`, `/v2/ask`, `/v2/study-kit`, `/v2/audio-script`, and `/v2/concept-map`.

## Sample Curl

```bash
curl -X POST http://localhost:8000/v2/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{"path":"samples/beepdf.md","output_root":"outputs"}'
```

```bash
curl -X POST http://localhost:8000/v2/ask \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"<doc_id>","question":"What is the core idea?","top_k":4}'
```

```bash
curl -X POST http://localhost:8000/v2/audio-script \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"<doc_id>","query":"PDF parsing","mode":"briefing_3min"}'
```

## Output Artifacts

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

`chunks.json` keeps `page`, `chunk_id`, `char_start`, `char_end`, and filename metadata so every generated result can cite its source.


## OCR Fallback

BeePDF v2 now has a working local OCR fallback path for scanned or image-only PDFs:

```text
PDF text extraction
-> text layer is empty or too short
-> LocalTesseractOCRProvider
-> page markdown
-> chunks.json
-> source-grounded ask/study-kit/audio-script/concept-map
```

The local demo uses Tesseract OCR as an optional CPU-based provider. `MockOCRProvider` keeps tests deterministic, while `LocalTesseractOCRProvider` can run a real OCR test when the OS-level Tesseract engine is installed.

Windows install example:

```bash
winget install --id tesseract-ocr.tesseract -e
pip install pytesseract PyMuPDF
```

This does not lock the service into Tesseract. The same `OCRProvider` interface can later be implemented by CLOVA OCR or another managed OCR service.

## Why Source Citation Matters

Document AI should not answer from memory when the user asks about a specific PDF. BeePDF v2 returns sources from retrieved chunks only. If no relevant context is found, `/v2/ask` returns an empty answer with a warning instead of inventing unsupported text.

## When GraphRAG-lite Helps

GraphRAG-lite is useful for relationship questions such as:

- How does OCR support PDF parsing?
- What enables failure tracking?
- What reduces repeated processing cost?

The concept map is heuristic in the local demo. It creates nodes and edges from chunk text and attaches evidence to every edge.

## Current Limits

- No paid LLM API calls
- No high-quality TTS generation
- No embedding model or FAISS execution by default
- PDF parsing depends on optional `pymupdf4llm` or `PyMuPDF`
- GraphRAG-lite uses simple heuristics, not LLM-based entity extraction

## Local Tests

```bash
python -m unittest discover -s tests
```



