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

Future replacements:

- `OllamaProvider`
- `OpenAIProvider`
- `ClovaStudioProvider`

Responsibilities:

- Generate summaries.
- Answer questions with context.
- Extract entities and relations.
- Generate study kits and audio scripts.

## TTSProvider

Local demo:

- `MockTTSProvider`

Future replacements:

- `LocalTTSProvider`
- `ClovaVoiceProvider`

Responsibilities:

- Convert generated scripts to audio.
- Return local file paths, object storage URLs, or `null` for mock TTS.

## IndexProvider

Local demo:

- `LocalIndexProvider`
- `SimpleRetriever`

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
MockLLMProvider -> ClovaStudioProvider/OpenAIProvider/OllamaProvider
MockTTSProvider -> ClovaVoiceProvider/LocalTTSProvider
LocalIndexProvider -> ManagedVectorDBProvider
In-process workflow -> Queue-based worker execution
```


