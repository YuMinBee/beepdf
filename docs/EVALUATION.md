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
