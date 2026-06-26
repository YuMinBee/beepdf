# GraphRAG-lite

BeePDF v2 uses GraphRAG-lite to capture practical relationships inside a PDF without requiring the full Microsoft GraphRAG stack.

## Pipeline

```text
chunk
→ entity extraction
→ relation extraction
→ NetworkX graph
→ entity neighbor retrieval
→ vector result + graph context
```

## Example Relations

```text
sha256 cache → reduces → repeated processing cost
request_id → enables → failure tracking
OCR fallback → handles → scanned PDFs
Object Storage → stores → generated MP3
```

## Query Output

```json
{
  "answer": "BeePDF의 비용 절감은 OCR 호출 최소화와 sha256 캐시를 중심으로 설계됩니다.",
  "vector_sources": [
    {"page": 3, "chunk_id": "p3_c2"}
  ],
  "graph_context": [
    ["sha256 cache", "reduces", "repeated processing cost"],
    ["OCR fallback", "handles", "scanned PDFs"]
  ]
}
```

## Retrieval Strategy

1. Run vector search to find source chunks.
2. Extract candidate entities from the question and retrieved chunks.
3. Expand one-hop neighbors in the graph.
4. Pass both the vector context and graph triples to the answer generator.
5. Return citations from vector chunks and relation triples from the graph.

## Portfolio Value

The design shows that GraphRAG is applied because PDFs contain concepts and operational relationships, not because graph retrieval is fashionable.
