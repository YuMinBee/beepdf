from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from v2.graph.concept_map import build_concept_map
from v2.providers.ocr import LocalTesseractOCRProvider
from v2.rag.chunking import chunk_pages
from v2.schemas import DocumentIngestResult, PageMarkdown

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


def ingest_local_document(path: str, output_root: str = "outputs", max_chunk_chars: int = 900) -> DocumentIngestResult:
    source_path = Path(path)
    warnings: list[str] = []

    if not source_path.exists():
        doc_id = f"missing_{uuid4().hex[:12]}"
        warnings.append(f"file not found: {source_path}")
        return _write_ingest_outputs(doc_id, source_path.name, [], output_root, warnings, max_chunk_chars)

    extension = source_path.suffix.lower()
    doc_id = _sha256_file(source_path)

    if extension not in SUPPORTED_EXTENSIONS:
        warnings.append(f"unsupported file extension: {extension or '<none>'}")
        return _write_ingest_outputs(doc_id, source_path.name, [], output_root, warnings, max_chunk_chars)

    if extension == ".pdf":
        pages = _parse_pdf(source_path, warnings)
    else:
        pages = _parse_text_document(source_path, warnings, parser=extension.lstrip("."))

    return _write_ingest_outputs(doc_id, source_path.name, pages, output_root, warnings, max_chunk_chars)


def _parse_text_document(path: Path, warnings: list[str], parser: str) -> list[PageMarkdown]:
    text = _read_text(path, warnings)
    if not text.strip():
        warnings.append("document text is empty")
        return []
    return [PageMarkdown(page_number=1, markdown=text, parser=parser)]
def _has_enough_text(pages: list[PageMarkdown], min_chars: int = 40) -> bool:
    total_chars = sum(len(page.markdown.strip()) for page in pages)
    return total_chars >= min_chars


def _parse_pdf(path: Path, warnings: list[str]) -> list[PageMarkdown]:
    parser_seen = False
    for parser in (_parse_pdf_with_pymupdf4llm, _parse_pdf_with_pymupdf):
        pages = parser(path, warnings)
        if pages is None:
            continue
        parser_seen = True
        if _has_enough_text(pages):
            return pages

    ocr_pages = LocalTesseractOCRProvider().extract_pages(str(path), warnings)
    if ocr_pages:
        warnings.append("OCR fallback used: tesseract_ocr")
        return ocr_pages

    if not parser_seen:
        warnings.append("PDF parser is unavailable. Install pymupdf4llm or PyMuPDF to ingest PDF files.")
    return []


def _parse_pdf_with_pymupdf4llm(path: Path, warnings: list[str]) -> list[PageMarkdown] | None:
    try:
        import pymupdf4llm  # type: ignore[import-not-found]
    except ImportError:
        return None

    try:
        result = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    except Exception as error:  # pragma: no cover - optional dependency boundary
        warnings.append(f"pymupdf4llm failed: {error}")
        return []

    if isinstance(result, list):
        pages: list[PageMarkdown] = []
        for index, item in enumerate(result, start=1):
            if isinstance(item, dict):
                text = str(item.get("text") or item.get("markdown") or "").strip()
                metadata = item.get("metadata") or {}
                page_number = int(metadata.get("page", index)) if isinstance(metadata, dict) else index
            else:
                text = str(item).strip()
                page_number = index
            if text:
                pages.append(PageMarkdown(page_number=page_number, markdown=text, parser="pymupdf4llm"))
        return pages

    text = str(result).strip()
    return [PageMarkdown(page_number=1, markdown=text, parser="pymupdf4llm")] if text else []


def _parse_pdf_with_pymupdf(path: Path, warnings: list[str]) -> list[PageMarkdown] | None:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError:
        return None

    try:
        pages: list[PageMarkdown] = []
        with fitz.open(str(path)) as document:
            for index, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append(PageMarkdown(page_number=index, markdown=text, parser="pymupdf"))
        if not pages:
            warnings.append("PDF text layer is empty. OCR fallback is required for this document.")
        return pages
    except Exception as error:  # pragma: no cover - optional dependency boundary
        warnings.append(f"PyMuPDF failed: {error}")
        return []


def _write_ingest_outputs(
    doc_id: str,
    filename: str,
    pages: list[PageMarkdown],
    output_root: str,
    warnings: list[str],
    max_chunk_chars: int,
) -> DocumentIngestResult:
    chunks = chunk_pages(pages, max_chars=max_chunk_chars, filename=filename)
    output_dir = Path(output_root) / doc_id
    answers_dir = output_dir / "answers"
    answers_dir.mkdir(parents=True, exist_ok=True)

    result = DocumentIngestResult(
        doc_id=doc_id,
        filename=filename,
        page_count=len(pages),
        chunk_count=len(chunks),
        output_dir=str(output_dir),
        warnings=warnings,
    )

    _write_json(output_dir / "document.json", result.to_dict())
    _write_json(output_dir / "pages.json", {"pages": [asdict(page) for page in pages]})
    _write_json(output_dir / "chunks.json", {"chunks": [asdict(chunk) for chunk in chunks]})
    build_concept_map(chunks, output_dir=str(output_dir))
    _write_json(output_dir / "study_kit.json", {})
    _write_json(output_dir / "audio_script.json", {})
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_text(path: Path, warnings: list[str]) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    warnings.append("failed to decode text as utf-8, utf-8-sig, or cp949")
    return ""


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


