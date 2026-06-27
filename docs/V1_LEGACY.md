# v1 Legacy PDF-to-Audio

v1 is the original BeePDF service direction.

## Goal

```text
single PDF
-> text extraction or OCR fallback
-> CLOVA Studio script generation
-> CLOVA Voice TTS
-> Object Storage upload
-> presigned audio URL
```

## Main Files

- `app/main.py`: legacy FastAPI application
- `db/`: request and processing metadata schema
- `infra/`: NCP/cloud deployment notes
- `web/`: original web/static assets

## Main Value

v1 demonstrates an end-to-end cloud service pipeline:

- PDF upload
- text-layer extraction before OCR to reduce cost
- OCR fallback for scanned PDFs
- `sha256` cache for repeated files
- `request_id` based failure tracking
- TTS generation
- Object Storage result delivery

## Why It Is Kept

v1 is still useful as infrastructure and service-operations evidence. It shows the original production-style design: API server, DB logging, object storage, external AI APIs, and deployment concerns.

## Relationship To v2

v2 does not replace v1 line by line. It upgrades the service value from a single-file audio converter into a Course Pack learning AI.

```text
v1: PDF 1개 -> 대본/오디오
v2: 여러 강의자료 -> Course Pack -> Q&A / Study Kit / Audio Script / Concept Map
```
