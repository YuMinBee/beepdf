# Workflow

BeePDF v2 uses a LangGraph-style state machine. The first implementation can run as plain local functions, while preserving node boundaries that can later become queue workers.

## State

```python
{
    "request_id": str,
    "doc_id": str,
    "pdf_path": str,
    "pages": list,
    "chunks": list,
    "vector_index_path": str,
    "graph_path": str,
    "selected_mode": str,
    "outputs": dict,
    "errors": list,
}
```

## Nodes

- `parse_pdf_node`
- `ocr_fallback_node`
- `chunk_node`
- `vector_index_node`
- `graph_index_node`
- `rag_answer_node`
- `graphrag_answer_node`
- `script_generation_node`
- `citation_check_node`
- `export_node`

## Modes

- `summary_mode`
- `qa_mode`
- `study_kit_mode`
- `audio_script_mode`
- `graphrag_mode`

## Local-first Execution

The local workflow keeps each node as a deterministic function that accepts and returns state. This makes development cheap and testable. Later, the same node contract can be moved behind worker tasks without changing the API shape.

## Failure Tracking

Each node appends structured errors:

```json
{
  "request_id": "req_123",
  "node": "vector_index_node",
  "error_type": "IndexBuildError",
  "message": "failed to build vector index",
  "retryable": true
}
```
