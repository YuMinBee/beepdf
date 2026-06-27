# tests

The current test suite targets the v2 local demo.

Covered behavior:

- local `.txt`, `.md`, and `.pdf` ingest
- page-level chunk source preservation
- source-grounded `/v2/ask`
- Study Kit source preservation
- Audio Script source preservation
- GraphRAG-lite concept map generation
- OCR fallback provider behavior
- provider interface availability
- v2 FastAPI entrypoint registration

Run:

```bash
python -m unittest discover -s tests
```
