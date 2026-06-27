# BeePDF

BeePDF는 두 단계로 발전한 PDF 기반 학습/음성화 프로젝트입니다.

- **v1 Legacy PDF-to-Audio**: PDF 1개를 업로드하면 텍스트 추출/OCR, CLOVA Studio 대본 생성, CLOVA Voice TTS, Object Storage 배포까지 처리하는 클라우드 지향 음성화 파이프라인입니다.
- **v2 Course Pack Document AI**: 여러 강의자료를 하나의 Course Pack으로 묶고, source-grounded RAG와 GraphRAG-lite concept map을 통해 통합 Q&A, Study Kit, Audio Script를 생성하는 로컬 우선 학습 AI 데모입니다.

현재 메인 방향은 **v2 Course Pack 기반 멀티문서 학습 AI**입니다. GraphRAG-lite는 메인 제품명이 아니라, 여러 강의자료의 개념 연결과 concept map을 보조하는 기술로 사용합니다.

## Version Map

| Version | Purpose | Main files | Run target |
| --- | --- | --- | --- |
| v1 Legacy | PDF -> script -> TTS -> Object Storage | `app/main.py`, `db/`, `infra/`, `web/` | `uvicorn app.main:app` |
| v2 Local Demo | Course Pack RAG, Study Kit, Audio Script, Concept Map | `v2/`, `v2/main.py`, `requirements-v2.txt`, `tests/` | `uvicorn v2.main:app --reload --port 8000` |

## Repository Structure

```text
app/                  v1 legacy FastAPI service
  main.py             v1 cloud PDF-to-audio entrypoint
v2/                   v2 local Course Pack Document AI package
  main.py             v2 FastAPI demo entrypoint
  api/                v2 request/response routes
  rag/                page-level retrieval and source-grounded answers
  graph/              GraphRAG-lite concept map helpers
  providers/          local/mock/cloud-ready provider interfaces
  workflows/          LangGraph-style local workflow nodes
docs/                 architecture and version documents
tests/                current v2 local tests
requirements-v2.txt   v2 local demo dependencies
```

More detail: [docs/REPOSITORY_STRUCTURE.md](docs/REPOSITORY_STRUCTURE.md)

## Run v2 Local Demo

```bash
pip install -r requirements-v2.txt
uvicorn v2.main:app --reload --port 8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

Expected v2 endpoints:

- `POST /v2/documents/ingest`
- `GET /v2/documents/{doc_id}`
- `POST /v2/ask`
- `POST /v2/study-kit`
- `POST /v2/audio-script`
- `POST /v2/concept-map`

## v2 Positioning

BeePDF v2는 PDF 문서를 page-level RAG와 GraphRAG-lite로 구조화하고, 요약, Q&A, Study Kit, 음성 대본 생성을 source-grounded 방식으로 제공하는 cloud-ready Document AI 플랫폼입니다.

기본 구현은 비용 없이 재현 가능한 local provider를 사용합니다. 다만 `StorageProvider`, `ParserProvider`, `OCRProvider`, `LLMProvider`, `TTSProvider`, `IndexProvider`를 분리해 향후 Object Storage, managed OCR, 외부 LLM API, managed vector DB로 교체할 수 있게 설계했습니다.

## v2 Output Artifacts

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

## Docs

- [v1 Legacy Overview](docs/V1_LEGACY.md)
- [v2 Upgrade Summary](docs/V2_UPGRADE_SUMMARY.md)
- [Repository Structure](docs/REPOSITORY_STRUCTURE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Providers](docs/PROVIDERS.md)
- [GraphRAG-lite](docs/GRAPH_RAG.md)
- [Cloud-ready Plan](docs/CLOUD_READY_PLAN.md)
- [Evaluation](docs/EVALUATION.md)

## Tests

```bash
python -m unittest discover -s tests
```

The current test suite focuses on v2 local demo behavior: ingest, chunk source preservation, source-grounded ask, Study Kit, Audio Script, concept map, OCR fallback, provider interfaces, and FastAPI route registration.
