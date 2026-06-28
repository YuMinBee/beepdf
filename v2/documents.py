from __future__ import annotations

import json
from pathlib import Path

from v2.schemas import Chunk
from v2.source_metadata import enrich_source_metadata


def document_dir(doc_id: str, output_root: str = "outputs") -> Path:
    return Path(output_root) / doc_id


def load_document(doc_id: str, output_root: str = "outputs") -> dict:
    path = document_dir(doc_id, output_root) / "document.json"
    if not path.exists():
        return {"doc_id": doc_id, "warnings": [f"document not found: {doc_id}"]}
    return json.loads(path.read_text(encoding="utf-8"))


def load_chunks(doc_id: str, output_root: str = "outputs") -> list[Chunk]:
    path = document_dir(doc_id, output_root) / "chunks.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [chunk_from_dict(item) for item in data.get("chunks", [])]


def chunk_from_dict(item: dict) -> Chunk:
    metadata = dict(item.get("metadata", {}))
    if item.get("doc_id") and "doc_id" not in metadata:
        metadata["doc_id"] = item["doc_id"]
    if item.get("filename") and "filename" not in metadata:
        metadata["filename"] = item["filename"]
    if item.get("pack_id") and "pack_id" not in metadata:
        metadata["pack_id"] = item["pack_id"]
    for key in ("week", "lecture_no"):
        if item.get(key) is not None and key not in metadata:
            metadata[key] = item[key]
    metadata = enrich_source_metadata(metadata)
    return Chunk(
        chunk_id=item["chunk_id"],
        page=item.get("page", item.get("page_number", 1)),
        text=item["text"],
        char_start=item.get("char_start", 0),
        char_end=item.get("char_end", len(item["text"])),
        metadata=metadata,
    )


def chunks_from_payload_or_doc(payload: dict) -> list[Chunk]:
    if "chunks" in payload:
        return [chunk_from_dict(item) for item in payload.get("chunks", [])]
    doc_id = payload.get("doc_id")
    if doc_id:
        return load_chunks(doc_id, output_root=payload.get("output_root", "outputs"))
    output_dir = payload.get("output_dir")
    if output_dir:
        path = Path(output_dir) / "chunks.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return [chunk_from_dict(item) for item in data.get("chunks", [])]
    return []
