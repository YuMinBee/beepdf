# CourseBee v2

CourseBee v2는 단일 PDF RAG 도구였던 BeePDF를 여러 강의자료 기반 Course Pack 학습 시스템으로 확장한 프로젝트입니다.

CourseBee는 여러 차시의 Learning Materials를 하나의 `Course Pack`으로 묶고, 각 chunk의 출처 메타데이터를 유지한 상태에서 Q&A, Study Kit, Concept Map, Podcast Script, TTS artifact를 생성하는 AI 학습 콘텐츠 생성 시스템입니다.

![CourseBee v2 Architecture](images/coursebee-v2-architecture.png)

## Why CourseBee?

기존 BeePDF는 단일 PDF를 기준으로 질문 답변이나 음성화 흐름을 만들 수 있었지만, 실제 학습 상황에서는 한 주차의 여러 차시 자료를 함께 복습해야 하는 경우가 많았습니다. 단일 문서 중심 RAG만으로는 “11주차 전체 흐름”, “1차시와 3차시의 연결”, “여러 강의자료에 걸친 개념 관계”를 다루기 어렵습니다.

CourseBee v2는 이 한계를 해결하기 위해 여러 강의자료를 하나의 Course Pack으로 묶고, 모든 chunk에 `doc_id`, `filename`, `week`, `lecture_no`, `page`, `chunk_id`를 보존합니다. 이 provenance metadata를 통해 생성된 답변과 학습 자료가 어떤 강의자료의 어떤 부분을 근거로 했는지 추적할 수 있습니다.

GraphRAG-lite는 full Microsoft GraphRAG가 아니라, Course Pack 내부의 concept edge와 evidence chunk를 retrieval에 활용하는 lightweight graph-augmented retrieval입니다. 과장된 graph pipeline이 아니라, Course Pack 학습 경험에 필요한 범위의 graph retrieval을 직접 구현한 데모입니다.

## Key Features

- Multi-document Course Pack ingestion
- Source-grounded Q&A
- GraphRAG-lite `local_graph` retrieval
- Study Kit generation
- Concept Map generation
- Staged Podcast Script generation: `outline -> scene generation -> repair`
- Edge TTS artifact generation
- Local-first provider design with cloud-ready extension points

## Demo Course Pack

- `pack_id`: `pack_static_nlp_11week_demo`
- Input: NLP 11주차 1~3차시 강의자료
- Output: Q&A, Study Kit, Concept Map, Podcast Script, Edge TTS mp3

원본 강의자료는 저작권 문제로 공개하지 않습니다. 포트폴리오에는 Course Pack 구조, source metadata 설계, 샘플 artifact, 실행 가능한 로컬 데모 코드만 포함합니다.

mp3 같은 큰 생성 artifact는 `outputs/` 경로에 직접 링크하지 않습니다. 공개 가능한 샘플만 필요한 경우 `assets/demo/` 아래에 별도로 둘 수 있습니다.

## v1 vs v2

| Area | v1 BeePDF | CourseBee v2 |
| --- | --- | --- |
| Main unit | Single PDF | Multi-document Course Pack |
| Goal | PDF-to-audio / document QA | Learning content generation from multiple lecture materials |
| Retrieval | Single-document RAG | Source-grounded retrieval across Course Pack chunks |
| Graph | None or visualization-focused | GraphRAG-lite `local_graph` retrieval using concept edges and evidence chunks |
| Output | Script / TTS centered | Q&A, Study Kit, Concept Map, Podcast Script, TTS artifact |
| Generation | Mostly one-shot | Staged orchestration: `outline -> scene generation -> repair` |
| Provenance | Page/chunk-level within one file | `doc_id`, filename, week, lecture_no, page, chunk_id across files |

## Quick Start

```bash
pip install -r requirements-v2.txt
uvicorn v2.main:app --reload --port 8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Expected Endpoints

- `POST /v2/documents/ingest`
- `POST /v2/ask`
- `POST /v2/study-kit`
- `POST /v2/audio-script`
- `POST /v2/concept-map`

Course Pack endpoints are also available in the v2 API:

- `POST /v2/course-packs`
- `POST /v2/course-packs/ask`
- `POST /v2/course-packs/study-kit`
- `POST /v2/course-packs/summary`
- `POST /v2/course-packs/audio-script`
- `POST /v2/course-packs/concept-map`
- `GET /v2/course-packs/{pack_id}/artifacts`

## Docs

- [CourseBee v2 Case Study](docs/coursebee-v2-case-study.md)
- [Korean Course Pack Case Study](docs/COURSE_PACK_CASE_STUDY_KO.md)
- [English Course Pack Case Study](docs/COURSE_PACK_CASE_STUDY.md)
- [v2 Static Endpoint Viewer](docs/project_visualization.html)
- [Course Pack Demo](docs/COURSE_PACK_DEMO.md)
- [Repository Structure](docs/REPOSITORY_STRUCTURE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Providers](docs/PROVIDERS.md)
- [GraphRAG-lite](docs/GRAPH_RAG.md)
- [Cloud-ready Plan](docs/CLOUD_READY_PLAN.md)
- [Evaluation](docs/EVALUATION.md)
- [v1 Legacy Overview](docs/V1_LEGACY.md)

## Tests

```bash
python -m unittest discover -s tests
```

The current test suite focuses on v2 local demo behavior: ingestion, source metadata preservation, source-grounded Q&A, Course Pack summary, Study Kit, Audio Script, Concept Map export, provider interfaces, and FastAPI route registration.
