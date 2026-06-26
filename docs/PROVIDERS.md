# Providers

BeePDF v2 separates infrastructure concerns behind provider interfaces. Local implementations are used by default, while cloud services can be added without rewriting the workflow.

## StorageProvider

- `LocalStorageProvider`
- `S3LikeStorageProvider`
- `NCPObjectStorageProvider`

Responsibilities:

- Save uploaded PDFs.
- Save JSON artifacts.
- Save generated audio.
- Return stable paths or presigned URLs.

## LLMProvider

- `OllamaProvider`
- `OpenAIProvider`
- `ClovaStudioProvider`
- `MockProvider`

Responsibilities:

- Generate summaries.
- Answer questions with context.
- Extract entities and relations.
- Generate study kits and audio scripts.

## TTSProvider

- `LocalTTSProvider`
- `ClovaVoiceProvider`
- `MockTTSProvider`

Responsibilities:

- Convert generated scripts to audio.
- Return local file paths or object storage URLs.

## IndexProvider

- `LocalFAISSProvider`
- `ChromaProvider`
- `FutureVectorDBProvider`

Responsibilities:

- Build document indexes.
- Search relevant chunks.
- Preserve `page_number` and `chunk_id` in search results.

## Contract Rule

Every provider should return serializable data. This keeps workflow state portable between local execution, HTTP APIs, background workers, and cloud deployment.
