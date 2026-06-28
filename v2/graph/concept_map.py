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
]

RELATION_HINTS = {
    "OCR": ("PDF parsing", "supports"),
    "source citation": ("RAG", "grounds"),
    "sha256 cache": ("repeated processing cost", "reduces"),
    "request_id": ("failure tracking", "enables"),
    "GraphRAG-lite": ("concept map", "builds"),
    "chunk": ("source citation", "preserves"),
    "page": ("source citation", "anchors"),
    "TTS": ("audio script", "renders"),
}


def build_concept_map(chunks: list[Chunk], output_dir: str | None = None) -> dict:
    warnings: list[str] = []
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str, str | None, str]] = set()

    for chunk in chunks:
        concepts = _concepts_from_text(chunk.text)
        doc_id = chunk.metadata.get("doc_id") if chunk.metadata else None
        filename = chunk.metadata.get("filename") if chunk.metadata else None
        doc_node_id = _document_node_id(doc_id, filename)

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

        for concept in concepts:
            node = nodes.setdefault(concept, {"id": concept, "label": concept, "type": "concept", "documents": []})
            _add_document_to_node(node, doc_id=doc_id, filename=filename)
            if doc_node_id:
                _append_edge(
                    edges,
                    seen_edges,
                    source=concept,
                    target=doc_node_id,
                    relation="appears_in",
                    chunk=chunk,
                    evidence_doc_id=doc_id,
                )

        for source, target, relation in _edges_from_concepts(concepts):
            source_node = nodes.setdefault(source, {"id": source, "label": source, "type": "concept", "documents": []})
            target_node = nodes.setdefault(target, {"id": target, "label": target, "type": "concept", "documents": []})
            _add_document_to_node(source_node, doc_id=doc_id, filename=filename)
            _add_document_to_node(target_node, doc_id=doc_id, filename=filename)
            _append_edge(
                edges,
                seen_edges,
                source=source,
                target=target,
                relation=relation,
                chunk=chunk,
                evidence_doc_id=doc_id,
            )

    if not nodes or not edges:
        warnings.append("No concept graph could be built from the provided chunks.")

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
            "evidence": [source_ref.to_dict() for source_ref in _sources_from_chunks([chunk])],
        }
    )


def _document_node_id(doc_id: str | None, filename: str | None) -> str | None:
    value = doc_id or filename
    return f"doc:{value}" if value else None


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

    return concepts[:8]


def _edges_from_concepts(concepts: list[str]) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = []
    for source in concepts:
        hinted = RELATION_HINTS.get(source)
        if hinted:
            target, relation = hinted
            edges.append((source, target, relation))
            continue
    for left, right in zip(concepts, concepts[1:]):
        if left != right and (left, right, "related_to") not in edges:
            edges.append((left, right, "related_to"))
    return edges
