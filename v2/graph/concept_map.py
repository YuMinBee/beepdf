from __future__ import annotations

import json
import re
from pathlib import Path

from v2.rag.answering import _sources_from_chunks
from v2.schemas import Chunk

KNOWN_CONCEPTS = [
    "OCR",
    "PDF parsing",
    "source citation",
    "sha256 cache",
    "request_id",
    "failure tracking",
    "GraphRAG",
    "GraphRAG-lite",
    "RAG",
    "chunk",
    "page",
    "TTS",
    "Object Storage",
    "BPE",
    "OOV",
    "Tokenizer",
    "subword tokenization",
    "subword",
    "RNN",
    "LSTM",
    "CNN",
    "sequence data",
    "long-term dependency",
    "local pattern",
    "text classification",
    "NLP pipeline",
]

RELATION_HINTS: dict[str, list[tuple[str, str]]] = {
    "OCR": [("PDF parsing", "supports")],
    "source citation": [("RAG", "grounds")],
    "sha256 cache": [("repeated processing cost", "reduces")],
    "request_id": [("failure tracking", "enables")],
    "GraphRAG-lite": [("concept map", "builds"), ("RAG", "augments")],
    "chunk": [("source citation", "preserves")],
    "page": [("source citation", "anchors")],
    "TTS": [("audio script", "renders")],
    "Tokenizer": [("BPE", "uses"), ("BPE", "prerequisite_of")],
    "subword tokenization": [("BPE", "prerequisite_of"), ("OOV", "reduces")],
    "subword": [("BPE", "prerequisite_of"), ("OOV", "reduces")],
    "BPE": [("OOV", "reduces"), ("subword tokenization", "is_a"), ("NLP pipeline", "used_in")],
    "RNN": [("sequence data", "handles"), ("NLP pipeline", "used_in")],
    "LSTM": [("RNN", "improves"), ("long-term dependency", "handles"), ("NLP pipeline", "used_in")],
    "CNN": [("local pattern", "captures"), ("text classification", "used_in"), ("NLP pipeline", "used_in")],
}

STRUCTURAL_RELATIONS = {"contains", "mentions", "introduces", "appears_in", "evidence_in"}


def build_concept_map(chunks: list[Chunk], output_dir: str | None = None) -> dict:
    warnings: list[str] = []
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str, str | None, str]] = set()

    for chunk in chunks:
        metadata = chunk.metadata or {}
        concepts = _concepts_from_text(chunk.text)
        doc_id = metadata.get("doc_id")
        filename = metadata.get("filename")
        doc_node_id = _document_node_id(doc_id, filename)
        lecture_node_id = _lecture_node_id(metadata, doc_node_id)
        page_node_id = _page_node_id(metadata, doc_node_id, chunk.page)
        chunk_node_id = _chunk_node_id(metadata, doc_node_id, chunk.page, chunk.chunk_id)

        if doc_node_id:
            nodes.setdefault(
                doc_node_id,
                {
                    "id": doc_node_id,
                    "label": filename or doc_id or "document",
                    "type": "document",
                    "doc_id": doc_id,
                    "filename": filename,
                },
            )

        if lecture_node_id:
            nodes.setdefault(
                lecture_node_id,
                {
                    "id": lecture_node_id,
                    "label": _lecture_label(metadata, filename),
                    "type": "lecture",
                    "doc_id": doc_id,
                    "filename": filename,
                    "week": metadata.get("week"),
                    "lecture_no": metadata.get("lecture_no"),
                },
            )
            if doc_node_id:
                _append_edge(edges, seen_edges, doc_node_id, lecture_node_id, "contains", chunk, doc_id)

        if page_node_id:
            nodes.setdefault(
                page_node_id,
                {
                    "id": page_node_id,
                    "label": f"page {chunk.page}",
                    "type": "page",
                    "doc_id": doc_id,
                    "filename": filename,
                    "page": chunk.page,
                },
            )
            parent = lecture_node_id or doc_node_id
            if parent:
                _append_edge(edges, seen_edges, parent, page_node_id, "contains", chunk, doc_id)

        nodes.setdefault(
            chunk_node_id,
            {
                "id": chunk_node_id,
                "label": chunk.chunk_id,
                "type": "chunk",
                "doc_id": doc_id,
                "filename": filename,
                "page": chunk.page,
                "chunk_id": chunk.chunk_id,
            },
        )
        if page_node_id:
            _append_edge(edges, seen_edges, page_node_id, chunk_node_id, "contains", chunk, doc_id)

        for concept in concepts:
            node = nodes.setdefault(concept, {"id": concept, "label": concept, "type": "concept", "documents": []})
            _add_document_to_node(node, doc_id=doc_id, filename=filename)
            _append_edge(edges, seen_edges, chunk_node_id, concept, "mentions", chunk, doc_id)
            _append_edge(edges, seen_edges, concept, chunk_node_id, "evidence_in", chunk, doc_id)
            if lecture_node_id:
                _append_edge(edges, seen_edges, lecture_node_id, concept, "introduces", chunk, doc_id)
            elif doc_node_id:
                _append_edge(edges, seen_edges, doc_node_id, concept, "introduces", chunk, doc_id)
            if doc_node_id:
                _append_edge(edges, seen_edges, concept, doc_node_id, "appears_in", chunk, doc_id)

        for source, target, relation in _edges_from_concepts(concepts):
            source_node = nodes.setdefault(source, {"id": source, "label": source, "type": "concept", "documents": []})
            target_node = nodes.setdefault(target, {"id": target, "label": target, "type": "concept", "documents": []})
            _add_document_to_node(source_node, doc_id=doc_id, filename=filename)
            _add_document_to_node(target_node, doc_id=doc_id, filename=filename)
            _append_edge(edges, seen_edges, source, target, relation, chunk, doc_id)

    if not nodes or not edges:
        warnings.append("No course graph could be built from the provided chunks.")

    graph = {"nodes": list(nodes.values()), "edges": edges, "warnings": warnings}
    if output_dir:
        path = Path(output_dir) / "graph.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return graph


def _append_edge(
    edges: list[dict],
    seen_edges: set[tuple[str, str, str, str | None, str]],
    source: str,
    target: str,
    relation: str,
    chunk: Chunk,
    evidence_doc_id: str | None,
) -> None:
    key = (source, target, relation, evidence_doc_id, chunk.chunk_id)
    if key in seen_edges:
        return
    seen_edges.add(key)
    edges.append(
        {
            "source": source,
            "target": target,
            "relation": relation,
            "edge_type": "structural" if relation in STRUCTURAL_RELATIONS else "conceptual",
            "evidence": [source_ref.to_dict() for source_ref in _sources_from_chunks([chunk])],
        }
    )


def _document_node_id(doc_id: str | None, filename: str | None) -> str | None:
    value = doc_id or filename
    return f"doc:{value}" if value else None


def _lecture_node_id(metadata: dict, doc_node_id: str | None) -> str | None:
    week = metadata.get("week")
    lecture_no = metadata.get("lecture_no")
    if week is None and lecture_no is None:
        return None
    suffix = f"week:{week or 'unknown'}:lecture:{lecture_no or 'unknown'}"
    return f"lecture:{doc_node_id}:{suffix}" if doc_node_id else f"lecture:{suffix}"


def _page_node_id(metadata: dict, doc_node_id: str | None, page: int) -> str | None:
    value = doc_node_id or metadata.get("filename") or metadata.get("doc_id")
    return f"page:{value}:{page}" if value else f"page:{page}"


def _chunk_node_id(metadata: dict, doc_node_id: str | None, page: int, chunk_id: str) -> str:
    value = doc_node_id or metadata.get("filename") or metadata.get("doc_id") or "document"
    return f"chunk:{value}:{page}:{chunk_id}"


def _lecture_label(metadata: dict, filename: str | None) -> str:
    week = metadata.get("week")
    lecture_no = metadata.get("lecture_no")
    if week is not None and lecture_no is not None:
        return f"Lecture {week}-{lecture_no}"
    if week is not None:
        return f"Week {week} lecture"
    if lecture_no is not None:
        return f"Lecture {lecture_no}"
    return filename or "lecture"


def _add_document_to_node(node: dict, doc_id: str | None, filename: str | None) -> None:
    if "documents" not in node:
        return
    value = {key: item for key, item in {"doc_id": doc_id, "filename": filename}.items() if item}
    if value and value not in node["documents"]:
        node["documents"].append(value)


def _concepts_from_text(text: str) -> list[str]:
    lowered = text.lower()
    concepts = [concept for concept in KNOWN_CONCEPTS if concept.lower() in lowered]

    for phrase in re.findall(r"\b[A-Z][A-Za-z0-9_-]*(?:\s+[A-Z][A-Za-z0-9_-]*)?\b", text):
        if len(phrase) >= 3 and phrase not in concepts:
            concepts.append(phrase)

    return concepts[:10]


def _edges_from_concepts(concepts: list[str]) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = []
    for source in concepts:
        for target, relation in RELATION_HINTS.get(source, []):
            if source != target and (source, target, relation) not in edges:
                edges.append((source, target, relation))
    for left, right in zip(concepts, concepts[1:]):
        if left != right and (left, right, "related_to") not in edges:
            edges.append((left, right, "related_to"))
    return edges
