# CourseBee v2

CourseBee v2는 단일 PDF RAG 도구였던 BeePDF를 여러 강의자료 기반 Course Pack 학습 시스템으로 확장한 프로젝트입니다.

CourseBee는 여러 차시의 Learning Materials를 하나의 `Course Pack`으로 묶고, source metadata를 유지한 상태에서 Q&A, Study Kit, Concept Map, Podcast Script, TTS artifact를 생성하는 AI 학습 콘텐츠 생성 시스템입니다.

![CourseBee v2 Architecture](images/coursebee-v2-architecture.png)

## Why CourseBee?

기존 단일 PDF RAG는 문서 하나 안의 질문에는 대응하기 쉽지만, 실제 강의 복습처럼 여러 차시 자료를 하나의 학습 단위로 묶어 이해하는 데는 한계가 있습니다.

CourseBee v2는 여러 강의자료를 하나의 Course Pack으로 묶고, 각 chunk에 `doc_id`, `filename`, `week`, `lecture_no`, `page`, `chunk_id`를 보존합니다. 이를 통해 답변과 학습 자료가 어떤 강의자료의 어떤 부분을 근거로 했는지 추적할 수 있습니다.

CourseBee의 graph 기능은 Course Pack 내부의 concept graph와 evidence chunk를 활용해 관계형 질문의 검색 근거를 보강하는 Concept Graph-assisted Retrieval입니다. 고급 graph indexing 제품을 흉내 내기보다, 강의 개념 관계를 검색 context로 쓰는 좁고 설명 가능한 범위에 집중했습니다.

## Retrieval Strategy

CourseBee v2 separates the local demo retriever from the production retrieval path.

Local demo에서는 외부 의존성을 줄이고 재현성을 높이기 위해 `LexicalRetriever`를 기본으로 사용합니다. 현재 `retrieve_contexts`는 query/chunk를 토큰화하고, term frequency와 IDF 기반 점수를 계산해 top-k chunk를 반환하는 설명 가능한 lexical retrieval입니다.

Production path에서는 같은 `RetrieverProvider` 인터페이스 뒤에서 embedding retriever, vector DB, hybrid retriever, reranker를 교체할 수 있도록 설계했습니다.

```text
RetrieverProvider
├─ LexicalRetriever      # current local/demo implementation
├─ EmbeddingRetriever    # sentence-transformers or OpenAI embeddings
├─ HybridRetriever       # lexical + embedding retrieval
└─ Reranker              # optional cross-encoder or LLM judge
```

이 선택은 약점이 아니라 의식적인 trade-off입니다. Local demo는 재현성과 설명 가능성을 우선하고, production에서는 retrieval provider를 교체해 semantic search와 reranking을 붙이는 방향으로 확장합니다.
## Key Features

- Multi-document Course Pack ingestion
- Source-grounded Q&A
- Explicit local lexical retriever and production `RetrieverProvider` path
- Query-type Retrieval Router via `mode="auto"`
- Multi-level Summary Retrieval for global overview questions
- Concept Graph-assisted Retrieval via `local_graph`
- Study Kit generation
- Concept Map generation
- Staged Podcast Script generation: `outline -> scene generation -> repair`
- Edge TTS artifact generation
- Evaluation harness for router accuracy, source recall, citation coverage, graph usefulness, and fallback behavior

## Demo Course Pack

- `pack_id`: `pack_static_nlp_11week_demo`
- Input: NLP 11주차 1~3차시 강의자료
- Output: Q&A, Study Kit, Concept Map, Podcast Script, Edge TTS mp3

원본 강의자료는 저작권 문제로 공개하지 않습니다. 포트폴리오에는 Course Pack 구조, source metadata 설계, 샘플 artifact, 실행 가능한 로컬 데모 코드만 포함합니다.

mp3 같은 큰 생성 artifact는 `outputs/` 경로에 직접 링크하지 않습니다. 공개 가능한 샘플만 필요한 경우 `assets/demo/` 아래에 별도로 둘 수 있습니다.

## Operations Surface

CourseBee exposes a small operations surface so long-running Course Pack ingestion and RAG decisions can be inspected.

```text
POST /v2/course-packs/jobs
GET  /v2/course-packs/jobs/{job_id}
GET  /v2/course-packs/{pack_id}
```

Local jobs are file-backed and run inline for the demo, but they return production-shaped state:

```json
{
  "job_id": "job_20260629_001",
  "status": "succeeded",
  "stage": "completed",
  "progress": 1.0,
  "processed_documents": 3,
  "total_documents": 3,
  "warnings": []
}
```

Course Pack answers also include `trace` with `request_id`, stage latencies, and retrieval debug information such as candidate chunks, selected chunks, graph edges, and fallback usage.

## Reliability Layer

CourseBee does not simply generate study content. Every generated artifact keeps source metadata, and API-refined summaries must pass `citation_check`. If generated text introduces unsupported terms, the system falls back to rule-based grounded output.

Citation quality checks include:

- source coverage
- unsupported claim detection
- source/chunk hover preview through artifact metadata
- answer sentence to supporting chunk mapping through preserved `sources`

`check_text_grounding` compares generated claim terms with source chunk terms and returns `coverage`, `matched_terms`, `unsupported_terms`, and warnings. This keeps generated Q&A, Study Kit, Concept Map, Podcast Script, and Summary artifacts tied back to Course Pack evidence.

## Evaluation Snapshot

The evaluation harness uses a public synthetic NLP 11-week Course Pack fixture, so it can be run without private lecture materials.

```bash
python eval/run_eval.py
```

| Metric | Result |
| --- | --- |
| Overall pass rate | 10 / 10 |
| Router accuracy | 10 / 10 |
| Source recall@5 | 10 / 10 |
| Citation coverage | 0.90 |
| No-context fallback pass | 1 / 1 |
| Graph route useful cases | 4 / 4 |

Latest report: [eval/results/latest_eval.md](eval/results/latest_eval.md)

## Representative Outputs

### Source-grounded Q&A

```json
{
  "question": "BPE와 OOV는 어떤 관계야?",
  "mode": "local_graph",
  "answer": "BPE는 OOV 문제를 줄이기 위해 단어를 통째로 unknown 처리하지 않고 subword 조각으로 나누는 토큰화 방식입니다.",
  "sources": [
    {
      "doc_id": "doc_week11_1",
      "filename": "자연어처리_11주차_1차시.pptx",
      "page": 3,
      "chunk_id": "p3_c1"
    }
  ],
  "graph_context": [
    {
      "source": "BPE",
      "target": "OOV",
      "relation": "reduces",
      "evidence_chunk_id": "p3_c1"
    }
  ],
  "matched_entities": ["BPE", "OOV"],
  "traversal_strategy": "edge"
}
```

### Query-type Retrieval Router

```json
{
  "question": "RNN, LSTM, CNN은 NLP pipeline에서 어떻게 연결돼?",
  "mode": "auto",
  "question_type": "relation_question",
  "routed_mode": "local_graph",
  "retrieval_plan": [
    {"level": "high", "strategy": "course_graph"},
    {"level": "low", "strategy": "evidence_chunks"}
  ]
}
```

### Concept Graph-assisted Retrieval

```json
{
  "question": "BPE를 이해하려면 먼저 뭘 알아야 해?",
  "retrieval_mode": "course_graph_path",
  "traversal_strategy": "prerequisite",
  "matched_entities": ["BPE"],
  "graph_paths": [
    {
      "nodes": ["subword tokenization", "BPE"],
      "edges": [{"relation": "prerequisite_of"}]
    }
  ]
}
```

### Multi-level Summary Retrieval

```json
{
  "question": "11주차 전체 흐름 설명해줘",
  "mode": "hierarchical",
  "retrieval_mode": "hierarchical_summary",
  "abstraction_level": "course_pack",
  "selected_summary_nodes": [
    {"type": "course_pack_summary"},
    {"type": "lecture_summary"}
  ],
  "supporting_chunks": [
    {"filename": "자연어처리_11주차_1차시.pptx", "chunk_id": "p3_c1"}
  ]
}
```

### Study Kit

```json
{
  "overview": "11주차 Course Pack은 BPE/OOV 문제에서 시작해 RNN, LSTM, CNN이 자연어처리 pipeline 안에서 어떤 역할을 하는지 연결해 설명합니다.",
  "flashcards": [
    {
      "front": "BPE는 OOV 문제를 어떻게 줄이는가?",
      "back": "단어를 subword 조각으로 나누어 처음 보는 단어도 기존 조각의 조합으로 처리하게 한다."
    }
  ],
  "expected_questions": [
    "BPE와 word-level tokenization의 차이는 무엇인가?",
    "RNN/LSTM과 CNN은 텍스트를 보는 방식이 어떻게 다른가?"
  ]
}
```

### Podcast Script

```text
HOST: 오늘은 NLP의 복잡한 용어들이 하나의 퍼즐처럼 연결되어 있다는 걸 알아보는 시간이에요.

GUEST: BPE, OOV, RNN, LSTM, CNN 같은 용어들이 각각 다른 분야처럼 보이지만, 사실은 AI가 텍스트를 읽는 과정에서 서로 연결된 단계를 이루고 있어요.
```

## Implementation Status

```text
Status
- Local demo: implemented
- Source-grounded artifacts: implemented
- Citation / grounding check: implemented for API-refined summaries
- Course Pack job API: implemented locally
- Answer trace / retrieval debug: implemented
- Concept graph-assisted retrieval: implemented
- Retrieval evaluation harness: implemented
- Production vector DB: planned
- Async ingestion worker: planned
- CI/CD: planned
```

The current repository is intentionally local-first. Mock/rule providers make the demo reproducible without paid services, while provider interfaces define the production upgrade path.

## v1 vs v2

| Area | v1 BeePDF | CourseBee v2 |
| --- | --- | --- |
| Main unit | Single PDF | Multi-document Course Pack |
| Goal | PDF-to-audio / document QA | Learning content generation from multiple lecture materials |
| Retrieval | Single-document RAG | Auto-routed chunk, multi-level summary, and concept graph-assisted retrieval across Course Pack sources |
| Graph | None or visualization-focused | Concept graph-assisted retrieval using concept edges and evidence chunks |
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
http://127.0.0.1:8000/demo
```

Example API call:

```bash
curl -X POST http://127.0.0.1:8000/v2/course-packs/ask \
  -H "Content-Type: application/json" \
  -d '{
    "pack_id": "pack_static_nlp_11week_demo",
    "question": "BPE와 OOV는 어떤 관계야?",
    "mode": "local_graph"
  }'
```

## Expected Endpoints

- `POST /v2/documents/ingest`
- `POST /v2/ask`
- `POST /v2/study-kit`
- `POST /v2/audio-script`
- `POST /v2/concept-map`
- `POST /v2/course-packs/jobs`
- `GET /v2/course-packs/jobs/{job_id}`
- `GET /v2/course-packs/{pack_id}`
- `POST /v2/course-packs/ask`
- `POST /v2/course-packs/study-kit`
- `POST /v2/course-packs/audio-script`
- `POST /v2/course-packs/concept-map`

## Docs

- [CourseBee v2 Case Study](docs/coursebee-v2-case-study.md)
- [CourseBee Demo UI](docs/coursebee_demo_ui.html) - run the server and open `http://127.0.0.1:8000/demo`
- [CourseBee Demo UI Korean](docs/coursebee_demo_ui_ko.html) - run the server and open `http://127.0.0.1:8000/demo-ko`
- [Architecture](docs/ARCHITECTURE.md)
- [Retrieval Router](docs/LIGHTRAG_ROUTER.md)
- [Multi-level Summary Retrieval](docs/HIERARCHICAL_RETRIEVAL.md)
- [Concept Graph-assisted Retrieval](docs/GRAPH_RAG.md)
- [Concept Graph Retrieval Evaluation](docs/GRAPH_RAG_EVALUATION.md)
- [Evaluation](docs/EVALUATION.md)
- [Citation and Grounding](docs/CITATION_GROUNDING.md)
- [Providers](docs/PROVIDERS.md)
- [Production Readiness](docs/PRODUCTION_READINESS.md)
- [v1 Legacy Overview](docs/V1_LEGACY.md)

More docs: [docs/README.md](docs/README.md)

## Tests

```bash
python -m unittest discover -s tests
python eval/run_eval.py
```
