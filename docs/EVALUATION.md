# Evaluation

BeePDF v2 evaluation focuses on whether answers are grounded in PDF pages and whether graph context improves relationship-heavy questions.

## Test Sets

- Text-layer PDFs
- Scanned PDFs requiring OCR fallback
- Repeated uploads for sha256 cache behavior
- Documents with clear operational relationships
- Long documents requiring chunk retrieval

## Metrics

- Citation presence rate
- Citation correctness by page
- Answer faithfulness to retrieved chunks
- Graph relation usefulness
- Cache hit behavior
- Node-level failure trace quality

## Manual Checks

- Ask a question whose answer exists on one page and verify `source page`.
- Ask a relationship question and verify graph triples are relevant.
- Upload the same PDF twice and verify repeated processing can be skipped.
- Force regeneration and verify cache bypass behavior.

## Example Expected Output

```json
{
  "answer": "BeePDF는 request_id를 사용해 각 처리 단계를 추적합니다.",
  "vector_sources": [
    {"page": 4, "chunk_id": "p4_c1"}
  ],
  "graph_context": [
    ["request_id", "enables", "failure tracking"]
  ]
}
```
