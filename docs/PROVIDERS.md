# Providers

BeePDF v2 separates infrastructure concerns behind provider interfaces. Local implementations are used by default, while cloud services can be added without rewriting the workflow.

## StorageProvider

Local demo:

- `LocalStorageProvider`

Future replacements:

- `S3LikeStorageProvider`
- `NCPObjectStorageProvider`
- Object Storage provider

Responsibilities:

- Save uploaded PDFs.
- Save JSON artifacts.
- Save generated audio.
- Return stable paths or presigned URLs.

## ParserProvider

Local demo:

- `LocalParserProvider`

Future replacements:

- Managed parser worker
- OCR-backed parser
- Cloud document parser

Responsibilities:

- Parse `.pdf`, `.txt`, and `.md` documents.
- Preserve page-level markdown.
- Return graceful warnings when optional PDF parsers are unavailable.


## OCRProvider

Local demo:

- `MockOCRProvider`
- `LocalTesseractOCRProvider`

Future replacements:

- `ClovaOCRProvider`
- `GoogleVisionOCRProvider`
- `AzureDocumentIntelligenceProvider`
- OCR worker backed by PaddleOCR or another document OCR engine

Responsibilities:

- Extract page text from scanned or image-only PDFs.
- Return page-level markdown so the same chunk/RAG pipeline can continue.
- Preserve warnings when OCR is unavailable or produces no text.

The local Tesseract provider is a working CPU-based fallback for demo and tests. It is not a hard requirement for production; managed OCR providers can replace it behind the same interface.

## LLMProvider

Local demo:

- `MockLLMProvider`
- `OpenAIProvider` when `OPENAI_API_KEY` is configured
- `OllamaProvider` for local LLM script generation, defaulting to `gemma2:2b` and accepting `qwen3:8b` later

Future replacements:

- `OllamaProvider`
- OpenAI-compatible managed LLM provider
- `ClovaStudioProvider`

Responsibilities:

- Generate source-grounded summaries and optional API-refined Course Pack overviews.
- Answer questions with context.
- Extract entities and relations.
- Generate study kits and audio scripts.
- For Course Pack audio scripts, `llm_provider: "ollama"` can call a local model and fall back to rule output if Ollama is unavailable.

## TTSProvider

Local demo:

- `MockTTSProvider`

Future replacements:

- `LocalTTSProvider`
- `ClovaVoiceProvider`

Responsibilities:

- Convert generated scripts to audio.
- Return local file paths, object storage URLs, or `null` for mock TTS.

## RetrieverProvider

Local demo:

- `LexicalRetriever`
- `SimpleRetriever` compatibility alias

Current implementation:

- Tokenizes query and chunk text.
- Computes term frequency and IDF-style scores.
- Returns top-k chunks while preserving `doc_id`, `filename`, `page`, `chunk_id`, and lecture metadata.

Production replacements:

- `EmbeddingRetriever` backed by sentence-transformers or OpenAI embeddings
- `VectorDBRetriever` backed by Chroma, FAISS, pgvector, or a managed vector DB
- `HybridRetriever` combining lexical and embedding scores
- Optional `Reranker` using a cross-encoder or LLM judge

This split is intentional. The local demo favors reproducibility and explainability, while production can swap in semantic retrieval behind the same provider boundary.
## IndexProvider

Local demo:

- `LocalIndexProvider`
- `LexicalRetriever`
- `SimpleRetriever` compatibility alias

Future replacements:

- `ChromaProvider`
- `ManagedVectorDBProvider`
- `FutureVectorDBProvider`

Responsibilities:

- Build document indexes.
- Search relevant chunks.
- Preserve `page` and `chunk_id` in search results.

## Contract Rule

Every provider should return serializable data. This keeps workflow state portable between local execution, HTTP APIs, background workers, and cloud deployment.

## Replacement Path

```text
LocalStorageProvider -> ObjectStorageProvider
LocalParserProvider -> OCR/parser worker
MockOCRProvider/LocalTesseractOCRProvider -> ClovaOCRProvider/managed OCR
MockLLMProvider -> OpenAIProvider/ClovaStudioProvider/OllamaProvider
MockTTSProvider -> ClovaVoiceProvider/LocalTTSProvider
LexicalRetriever/LocalIndexProvider -> EmbeddingRetriever/HybridRetriever/ManagedVectorDBProvider
In-process workflow -> Queue-based worker execution
```
