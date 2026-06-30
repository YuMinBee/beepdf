# Citation and Grounding

CourseBee v2 treats source grounding as a reliability layer, not only as a UI citation feature. The same source metadata that starts at chunk creation is carried into Q&A, Study Kit, Course Pack Summary, Concept Map, Podcast Script, and artifact previews.

## Metadata Carried Through Artifacts

Each chunk can preserve:

```json
{
  "doc_id": "doc_week11_1",
  "filename": "natural_language_processing_week11_lecture1.pptx",
  "week": 11,
  "lecture_no": 1,
  "page": 3,
  "chunk_id": "p3_c1"
}
```

This makes generated artifacts auditable. A reader can trace a statement back to the lecture file, page, and chunk that supported it.

## Citation Quality

CourseBee checks grounding through four practical signals:

- source coverage: generated artifacts should keep source references
- unsupported claim detection: generated terms should appear in retrieved source chunks
- source/chunk preview: artifacts expose enough metadata for UI hover or detail panels
- answer sentence to supporting chunk mapping: answer items retain source lists where possible

## `check_text_grounding`

`v2.rag.citations.check_text_grounding` compares generated claim terms with the terms available in retrieved source chunks.

It returns:

```json
{
  "checked": true,
  "passed": true,
  "coverage": 0.82,
  "matched_terms": ["ocr", "rag", "source"],
  "unsupported_terms": [],
  "source_count": 3,
  "warnings": []
}
```

If unsupported terms dominate the generated text, the check fails and returns warnings.

## Current Enforcement

Current strict enforcement is applied to API-refined Course Pack summaries:

```text
OpenAIProvider summary -> check_text_grounding -> accept if grounded
OpenAIProvider summary -> check_text_grounding -> fallback if unsupported
```

If `OPENAI_API_KEY` is absent, CourseBee also falls back to rule-based source-grounded output. This means the demo stays reproducible while still showing the production reliability gate.

## Existing Tests

The behavior is covered by tests:

- `test_citation_check_passes_grounded_text`
- `test_citation_check_flags_unsupported_text`
- `test_v2_course_pack_summary_openai_grounded_refine_passes_citation_check`
- `test_v2_course_pack_summary_openai_ungrounded_refine_falls_back`
- artifact tests that ensure Q&A, Study Kit, Audio Script, Summary, and Concept Map outputs keep sources

## Next Improvements

Good next steps:

- Add citation checks to podcast/script generation when `llm_provider` is not mock.
- Add answer sentence to chunk alignment in the response schema.
- Add source hover previews in a small static demo UI.
- Add per-artifact citation coverage to `eval/run_eval.py`.
- Track unsupported terms as an evaluation metric across all generated artifacts.
