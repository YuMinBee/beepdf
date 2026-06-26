# BeePDF v2

This directory contains the v2 scaffold for source-grounded RAG, GraphRAG-lite, LangGraph-style workflow orchestration, and cloud-ready provider adapters.

The default implementation is intentionally local and lightweight. Heavy components such as Docling, sentence-transformers, FAISS, Chroma, external LLMs, and TTS APIs can be added through providers without changing the workflow contract.

## Modules

- `schemas.py`: shared serializable models
- `providers/`: storage, LLM, TTS, and index provider contracts
- `rag/`: source-grounded vector retrieval helpers
- `graph/`: GraphRAG-lite relation graph helpers
- `workflows/`: state and node functions
- `api/`: FastAPI route skeleton

## Target APIs

- `/v2/ask`
- `/v2/summary`
- `/v2/graph/build`
- `/v2/graph/query`
- `/v2/concept-map`

## Resource Policy

The scaffold does not run embedding models or PDF parsing by default. It is safe to inspect and extend on a small local machine while GPU workloads are running elsewhere.
