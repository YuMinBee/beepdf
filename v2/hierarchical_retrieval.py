from __future__ import annotations

from collections import OrderedDict

from v2.rag.answering import _best_sentence, _keyword_terms, _sources_from_chunks
from v2.schemas import Chunk

OVERVIEW_QUERY_TERMS = {
    "전체",
    "요약",
    "정리",
    "핵심",
    "개요",
    "흐름",
    "overview",
    "summary",
    "summarize",
    "course",
    "pack",
    "week",
}
DETAIL_QUERY_TERMS = {
    "정의",
    "관계",
    "차이",
    "예시",
    "어떻게",
    "왜",
    "definition",
    "relationship",
    "example",
    "detail",
}


def build_hierarchical_summary_index(chunks: list[Chunk], pack_id: str) -> dict:
    warnings: list[str] = []
    if not chunks:
        return {
            "pack_id": pack_id,
            "root_id": None,
            "nodes": [],
            "warnings": ["No chunks were available for hierarchical summary indexing."],
        }

    grouped = _group_chunks_by_document(chunks)
    nodes: list[dict] = []
    lecture_node_ids: list[str] = []

    for index, group in enumerate(grouped.values(), start=1):
        lecture_id = _lecture_node_id(group, index)
        lecture_node_ids.append(lecture_id)
        chunk_node_ids: list[str] = []
        for chunk in group:
            chunk_node_id = _chunk_summary_node_id(chunk)
            chunk_node_ids.append(chunk_node_id)
            nodes.append(_chunk_summary_node(chunk, parent_id=lecture_id))
        nodes.append(_lecture_summary_node(group, node_id=lecture_id, children=chunk_node_ids, parent_id="course_pack_summary"))

    nodes.append(_course_pack_summary_node(chunks, children=lecture_node_ids, pack_id=pack_id))
    return {
        "pack_id": pack_id,
        "root_id": "course_pack_summary",
        "nodes": nodes,
        "warnings": warnings,
    }


def retrieve_hierarchical_summary(query: str, chunks: list[Chunk], pack_id: str, top_k: int = 4) -> dict:
    index = build_hierarchical_summary_index(chunks, pack_id=pack_id)
    nodes = index.get("nodes", [])
    strategy = _hierarchical_strategy(query)

    if strategy == "course_pack":
        selected_nodes = _nodes_by_type(nodes, {"course_pack_summary", "lecture_summary"})[: max(top_k, 2)]
    elif strategy == "lecture":
        selected_nodes = _rank_summary_nodes(query, _nodes_by_type(nodes, {"lecture_summary"}), top_k=max(top_k, 2))
    else:
        selected_nodes = _rank_summary_nodes(query, nodes, top_k=max(top_k, 2))

    if not selected_nodes:
        selected_nodes = _nodes_by_type(nodes, {"course_pack_summary"})[:1]

    support_chunks = _supporting_chunks(selected_nodes, chunks, top_k=top_k)
    return {
        "retrieval_mode": "hierarchical_summary",
        "abstraction_level": strategy,
        "selected_summary_nodes": selected_nodes,
        "supporting_chunks": [source.to_dict() for source in _sources_from_chunks(support_chunks)],
        "chunks": support_chunks,
        "hierarchical_summary_index": index,
    }


def _course_pack_summary_node(chunks: list[Chunk], children: list[str], pack_id: str) -> dict:
    grouped = _group_chunks_by_document(chunks)
    concept_hint = _concept_hint(chunks)
    text = (
        f"Course Pack {pack_id}는 {len(grouped)}개의 강의자료를 묶어 {concept_hint}를 중심으로 전체 학습 흐름을 정리합니다. "
        "상위 요약은 lecture summary와 supporting chunk로 내려갈 수 있도록 구성됩니다."
    )
    return {
        "id": "course_pack_summary",
        "type": "course_pack_summary",
        "text": text,
        "children": children,
        "sources": _source_dicts(_representative_chunks(grouped)),
    }


def _lecture_summary_node(chunks: list[Chunk], node_id: str, children: list[str], parent_id: str) -> dict:
    representative = _representative_chunk(chunks)
    metadata = representative.metadata if representative else {}
    filename = metadata.get("filename") if metadata else None
    week = metadata.get("week") if metadata else None
    lecture_no = metadata.get("lecture_no") if metadata else None
    sentence = _best_sentence(representative.text, _keyword_terms(representative.text)) if representative else ""
    label = _lecture_label(filename, week, lecture_no)
    return {
        "id": node_id,
        "type": "lecture_summary",
        "label": label,
        "text": f"{label}는 {sentence}를 중심으로 다룹니다.",
        "parent_id": parent_id,
        "children": children,
        "doc_id": metadata.get("doc_id") if metadata else None,
        "filename": filename,
        "week": week,
        "lecture_no": lecture_no,
        "sources": _source_dicts([representative] if representative else []),
    }


def _chunk_summary_node(chunk: Chunk, parent_id: str) -> dict:
    metadata = chunk.metadata or {}
    sentence = _best_sentence(chunk.text, _keyword_terms(chunk.text))
    return {
        "id": _chunk_summary_node_id(chunk),
        "type": "chunk_summary",
        "text": sentence,
        "parent_id": parent_id,
        "children": [],
        "doc_id": metadata.get("doc_id"),
        "filename": metadata.get("filename"),
        "week": metadata.get("week"),
        "lecture_no": metadata.get("lecture_no"),
        "page": chunk.page,
        "chunk_id": chunk.chunk_id,
        "sources": _source_dicts([chunk]),
    }


def _hierarchical_strategy(query: str) -> str:
    normalized = query.lower().strip()
    if not normalized:
        return "course_pack"
    if any(term in normalized for term in OVERVIEW_QUERY_TERMS):
        return "course_pack"
    if any(term in normalized for term in ["강의", "차시", "lecture"]):
        return "lecture"
    if any(term in normalized for term in DETAIL_QUERY_TERMS):
        return "chunk"
    return "lecture"


def _rank_summary_nodes(query: str, nodes: list[dict], top_k: int) -> list[dict]:
    terms = _keyword_terms(query)
    if not terms:
        return nodes[:top_k]
    scored: list[tuple[int, int, dict]] = []
    for index, node in enumerate(nodes):
        text = " ".join(str(node.get(key, "")) for key in ["text", "label", "filename"])
        lowered = text.lower()
        score = sum(1 for term in terms if term in lowered)
        if score > 0:
            scored.append((score, -index, node))
    scored.sort(reverse=True)
    return [node for _score, _index, node in scored[:top_k]] or nodes[:top_k]


def _supporting_chunks(selected_nodes: list[dict], chunks: list[Chunk], top_k: int) -> list[Chunk]:
    selected: list[Chunk] = []
    for node in selected_nodes:
        node_type = node.get("type")
        if node_type == "chunk_summary":
            chunk = _chunk_by_source(node, chunks)
            if chunk:
                selected.append(chunk)
            continue
        if node_type == "lecture_summary":
            selected.extend(_chunks_for_doc(node, chunks)[: max(1, top_k)])
            continue
        if node_type == "course_pack_summary":
            selected.extend(_representative_chunks(_group_chunks_by_document(chunks)))
    return _dedupe_chunks(selected)[:top_k]


def _chunk_by_source(node: dict, chunks: list[Chunk]) -> Chunk | None:
    for chunk in chunks:
        metadata = chunk.metadata or {}
        if node.get("chunk_id") != chunk.chunk_id:
            continue
        if node.get("page") != chunk.page:
            continue
        if node.get("doc_id") and node.get("doc_id") != metadata.get("doc_id"):
            continue
        if node.get("filename") and node.get("filename") != metadata.get("filename"):
            continue
        return chunk
    return None


def _chunks_for_doc(node: dict, chunks: list[Chunk]) -> list[Chunk]:
    doc_id = node.get("doc_id")
    filename = node.get("filename")
    selected = []
    for chunk in chunks:
        metadata = chunk.metadata or {}
        if doc_id and metadata.get("doc_id") == doc_id:
            selected.append(chunk)
        elif filename and metadata.get("filename") == filename:
            selected.append(chunk)
    return selected


def _nodes_by_type(nodes: list[dict], types: set[str]) -> list[dict]:
    return [node for node in nodes if node.get("type") in types]


def _group_chunks_by_document(chunks: list[Chunk]) -> OrderedDict[str, list[Chunk]]:
    groups: OrderedDict[str, list[Chunk]] = OrderedDict()
    for chunk in chunks:
        metadata = chunk.metadata or {}
        key = str(metadata.get("doc_id") or metadata.get("filename") or "document")
        groups.setdefault(key, []).append(chunk)
    return groups


def _representative_chunks(groups: OrderedDict[str, list[Chunk]]) -> list[Chunk]:
    return [chunk for chunk in (_representative_chunk(group) for group in groups.values()) if chunk is not None]


def _representative_chunk(chunks: list[Chunk]) -> Chunk | None:
    if not chunks:
        return None
    meaningful = [chunk for chunk in chunks if len(chunk.text.strip()) >= 30]
    return meaningful[0] if meaningful else chunks[0]


def _dedupe_chunks(chunks: list[Chunk]) -> list[Chunk]:
    deduped: list[Chunk] = []
    seen: set[tuple[str | None, str | None, int, str]] = set()
    for chunk in chunks:
        metadata = chunk.metadata or {}
        key = (metadata.get("doc_id"), metadata.get("filename"), chunk.page, chunk.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped


def _lecture_node_id(chunks: list[Chunk], index: int) -> str:
    representative = _representative_chunk(chunks)
    metadata = representative.metadata if representative else {}
    week = metadata.get("week") if metadata else None
    lecture_no = metadata.get("lecture_no") if metadata else None
    doc_id = metadata.get("doc_id") if metadata else None
    filename = metadata.get("filename") if metadata else None
    if week is not None or lecture_no is not None:
        return f"lecture:{week or 'unknown'}-{lecture_no or 'unknown'}"
    return f"lecture:{doc_id or filename or index}"


def _chunk_summary_node_id(chunk: Chunk) -> str:
    metadata = chunk.metadata or {}
    doc = metadata.get("doc_id") or metadata.get("filename") or "document"
    return f"chunk_summary:{doc}:{chunk.page}:{chunk.chunk_id}"


def _lecture_label(filename: str | None, week: int | None, lecture_no: int | None) -> str:
    if week is not None and lecture_no is not None:
        return f"Lecture {week}-{lecture_no}"
    if filename:
        return str(filename)
    return "Lecture"


def _concept_hint(chunks: list[Chunk]) -> str:
    terms: list[str] = []
    for chunk in chunks:
        for term in _keyword_terms(chunk.text):
            if len(term) < 3 or term in terms:
                continue
            terms.append(term)
            if len(terms) >= 4:
                return ", ".join(terms)
    return "핵심 개념"


def _source_dicts(chunks: list[Chunk]) -> list[dict]:
    return [source.to_dict() for source in _sources_from_chunks(chunks)]
