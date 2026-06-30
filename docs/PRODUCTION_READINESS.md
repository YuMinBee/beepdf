# Production Readiness

CourseBee v2 is currently a local-first portfolio demo with clear production upgrade boundaries. The local path is implemented intentionally so the project can run without paid services or private infrastructure. The production path is separated behind provider interfaces and documented as planned work.

## Current Local Demo

Implemented locally:

- Local lexical retrieval
- Mock/rule LLM fallback
- Optional OpenAI summary refinement when `OPENAI_API_KEY` is set
- File-system artifact store
- Local `outputs/` directory for generated artifacts
- Local Course Pack metadata JSON
- Concept graph-assisted retrieval over Course Pack concept edges
- Hierarchical summary retrieval over course structure
- Evaluation harness for route/source/graph/fallback behavior
- File-backed Course Pack job API for ingestion status
- Answer trace with request id, stage latency, and retrieval debug

## Production Upgrade Path

Planned production replacements:

- Embedding retriever plus vector DB
- Hybrid lexical + embedding retrieval
- Optional reranker with cross-encoder or LLM judge
- Async ingestion job queue / worker process
- Object storage for artifacts
- DB-backed Course Pack metadata
- Observability: request id, latency, token usage, retrieval trace
- Auth, quota, and file validation
- CI/CD and deployment automation

## Status

```text
Status
- Local demo: implemented
- Source-grounded artifacts: implemented
- Citation / grounding check: implemented for API-refined summaries
- Course Pack job API: implemented locally
- Answer trace / retrieval debug: implemented
- Concept graph-assisted retrieval: implemented
- Hierarchical summary retrieval: implemented
- Query-type retrieval router: implemented
- Retrieval evaluation harness: implemented
- Production vector DB: planned
- Async ingestion worker: planned
- Object storage: planned
- DB-backed metadata: planned
- Observability: planned
- Auth / quota / file validation: planned
- CI/CD: planned
```

## Why This Is Not Hidden

The distinction between local demo and production path is explicit because it is an engineering trade-off. Hiding mock providers would make the project look less reliable. Naming them makes the architecture easier to evaluate.

Local demo priorities:

- reproducibility
- no paid dependencies
- deterministic tests
- explainable retrieval behavior
- source-grounded artifacts

Production priorities:

- semantic retrieval quality
- scalability
- background processing
- artifact durability
- observability and access control

## Observability

Course Pack answer responses include a `trace` field:

```json
{
  "trace": {
    "request_id": "req_abc123",
    "stages": [
      {"name": "classify_question", "latency_ms": 3},
      {"name": "retrieve_graph_context", "latency_ms": 18},
      {"name": "select_evidence_chunks", "latency_ms": 5},
      {"name": "compose_answer", "latency_ms": 11}
    ],
    "retrieval_debug": {
      "candidate_chunks": 12,
      "selected_chunks": 4,
      "candidate_graph_edges": 30,
      "selected_graph_edges": 2,
      "fallback_used": false
    }
  }
}
```

This makes router decisions and retrieval failures inspectable without adding a full tracing backend yet.

## Provider Replacement Map

| Local component | Production replacement |
| --- | --- |
| `LexicalRetriever` | `EmbeddingRetriever`, `HybridRetriever`, vector DB retriever |
| `MockLLMProvider` | OpenAI-compatible provider, Clova Studio, hosted local model |
| `MockTTSProvider` | Clova Voice, Edge TTS service wrapper, local TTS service |
| local file system artifacts | object storage |
| JSON Course Pack metadata | relational DB or document DB |
| in-process ingestion | queue-based worker |
| local logs | structured tracing and metrics |

## Readiness Summary

CourseBee v2 is production-shaped but not production-deployed. The current repository proves the core retrieval and grounding behavior locally, while provider boundaries show how to replace local components with production infrastructure.
