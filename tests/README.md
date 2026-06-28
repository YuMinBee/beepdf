# tests

The current test suite targets the v2 local demo.

Covered behavior:

- local `.txt`, `.md`, `.pdf`, and `.pptx` ingest
- page-level chunk source preservation
- source-grounded `/v2/ask`
- Course Pack overview retrieval balanced across documents
- Course Pack Summary source preservation, OpenAI fallback behavior, and citation_check validation
- Study Kit source preservation
- Audio Script source preservation
- GraphRAG-lite concept map generation
- Course Pack artifact preview and Mermaid/HTML concept map export
- OCR fallback provider behavior
- provider interface availability
- v2 FastAPI entrypoint registration

Run:

```bash
python -m unittest discover -s tests
```






