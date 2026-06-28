# BeePDF v1 Legacy

This directory contains the original BeePDF PDF-to-audio service direction.

## Role

v1 is kept as legacy infrastructure and service-operations evidence:

- FastAPI PDF processing API
- OCR / text extraction path
- script generation and TTS integration
- DB/request tracking hooks
- cloud/object-storage oriented deployment notes

## Run Target

```bash
uvicorn v1.app.main:app
```

v1 requires the original cloud/API environment variables. For the current portfolio direction, use `v2/` instead.
