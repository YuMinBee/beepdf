from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from v2.audio_script import generate_audio_script
from v2.background_knowledge import BACKGROUND_SCOPE_VALUES, background_chunks_for_query
from v2.course_summary import generate_course_pack_summary
from v2.documents import chunk_from_dict, load_chunks
from v2.graph.concept_map import build_concept_map
from v2.hierarchical_retrieval import build_hierarchical_summary_index, retrieve_hierarchical_summary
from v2.ingest import ingest_local_document
from v2.providers.local import MockLLMProvider
from v2.rag.answering import _sources_from_chunks, generate_source_grounded_answer
from v2.rag.retrieval import chunks_from_contexts, retrieve_contexts
from v2.retrieval_router import classify_course_pack_question
from v2.schemas import Chunk
from v2.study_kit import generate_study_kit

OVERVIEW_QUERY_TERMS = {
    "전체",
    "요약",
    "정리",
    "핵심",
    "개요",
    "흐름",
    "course",
    "pack",
    "overview",
    "summary",
    "summarize",
    "outline",
}


def course_pack_dir(pack_id: str, output_root: str = "outputs") -> Path:
    return Path(output_root) / "course_packs" / pack_id


def create_course_pack(
    paths: list[str],
    output_root: str = "outputs",
    max_chunk_chars: int = 900,
    pack_id: str | None = None,
) -> dict:
    warnings: list[str] = []
    documents: list[dict] = []
    chunks: list[Chunk] = []

    for path in paths:
        result = ingest_local_document(path=path, output_root=output_root, max_chunk_chars=max_chunk_chars)
        document = result.to_dict()
        documents.append(document)
        warnings.extend([f"{result.filename}: {warning}" for warning in result.warnings])
        for chunk in load_chunks(result.doc_id, output_root=output_root):
            chunk.metadata.setdefault("doc_id", result.doc_id)
            chunk.metadata.setdefault("filename", result.filename)
            chunks.append(chunk)

    safe_pack_id = _safe_pack_id(pack_id) if pack_id else _pack_id_from_documents(documents)
    for chunk in chunks:
        chunk.metadata["pack_id"] = safe_pack_id

    output_dir = course_pack_dir(safe_pack_id, output_root=output_root)
    (output_dir / "answers").mkdir(parents=True, exist_ok=True)

    response = {
        "pack_id": safe_pack_id,
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "documents": documents,
        "output_dir": str(output_dir),
        "warnings": warnings,
    }

    _write_json(output_dir / "course_pack.json", response)
    _write_json(output_dir / "chunks.json", {"chunks": [asdict(chunk) for chunk in chunks]})
    build_concept_map(chunks, output_dir=str(output_dir))
    _write_json(output_dir / "hierarchical_summary_index.json", build_hierarchical_summary_index(chunks, safe_pack_id))
    _write_json(output_dir / "summary.json", {})
    _write_json(output_dir / "study_kit.json", {})
    _write_json(output_dir / "audio_script.json", {})
    return response


def load_course_pack(pack_id: str, output_root: str = "outputs") -> dict:
    path = course_pack_dir(pack_id, output_root=output_root) / "course_pack.json"
    if not path.exists():
        return {"pack_id": pack_id, "warnings": [f"course pack not found: {pack_id}"]}
    return json.loads(path.read_text(encoding="utf-8"))


def load_course_pack_chunks(pack_id: str, output_root: str = "outputs") -> list[Chunk]:
    path = course_pack_dir(pack_id, output_root=output_root) / "chunks.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    chunks = [chunk_from_dict(item) for item in data.get("chunks", [])]
    for chunk in chunks:
        chunk.metadata.setdefault("pack_id", pack_id)
    return chunks


def ask_course_pack(pack_id: str, question: str, output_root: str = "outputs", top_k: int = 4, mode: str = "vector") -> dict:
    if mode in {"auto", "router", "dual", "lightrag", "lightrag_dual"}:
        payload = _ask_course_pack_with_router(pack_id=pack_id, question=question, output_root=output_root, top_k=top_k)
    elif mode == "local_graph":
        payload = _ask_course_pack_with_graph(pack_id=pack_id, question=question, output_root=output_root, top_k=top_k)
    elif mode in {"hierarchical", "hierarchical_summary"}:
        payload = _ask_course_pack_with_hierarchical_summary(pack_id=pack_id, question=question, output_root=output_root, top_k=top_k)
    else:
        payload = _ask_course_pack_with_vector(pack_id=pack_id, question=question, output_root=output_root, top_k=top_k, mode=mode)
    _save_pack_artifact(pack_id, output_root, f"answers/{_artifact_name(question)}.json", payload)
    return payload


def summary_for_course_pack(
    pack_id: str,
    query: str = "",
    output_root: str = "outputs",
    top_k: int = 8,
    max_items: int = 5,
    llm_provider: str = "mock",
    llm_model: str | None = None,
) -> dict:
    all_chunks = load_course_pack_chunks(pack_id, output_root=output_root)
    target_query = query or "course pack overview summary"
    min_top_k = max(top_k, max_items, len(_group_chunks_by_document(all_chunks)))
    selected_chunks = _balanced_chunks(query=target_query, chunks=all_chunks, top_k=min_top_k)
    summary_chunks = _dedupe_chunks([*selected_chunks, *all_chunks])
    payload = generate_course_pack_summary(
        summary_chunks,
        llm_provider=llm_provider,
        llm_model=llm_model,
        max_items=max_items,
    )
    payload["pack_id"] = pack_id
    _save_pack_artifact(pack_id, output_root, "summary.json", payload)
    return payload


def study_kit_for_course_pack(
    pack_id: str,
    query: str = "",
    output_root: str = "outputs",
    top_k: int = 4,
    max_items: int = 4,
) -> dict:
    all_chunks = load_course_pack_chunks(pack_id, output_root=output_root)
    chunks = _select_pack_chunks(pack_id, query=query, output_root=output_root, top_k=top_k)
    study_chunks = _dedupe_chunks([*chunks, *all_chunks])
    base = generate_study_kit(chunks, max_items=max_items)
    summary_payload = generate_course_pack_summary(study_chunks, max_items=max(max_items, 5))
    payload = {
        "overview": summary_payload.get("overview", {}),
        "lecture_summaries": summary_payload.get("lecture_summaries", []),
        "connections": summary_payload.get("connections", []),
        "key_concepts": summary_payload.get("key_concepts", []),
        "expected_questions": base.get("expected_questions", []),
        "flashcards": _flashcards_from_study_payload(base, summary_payload, limit=max_items),
        "summary": base.get("summary", {"text": "", "sources": []}),
        "key_points": base.get("key_points", []),
        "glossary": base.get("glossary", []),
        "quiz": base.get("quiz", []),
        "sources": summary_payload.get("sources", []),
        "warnings": [*base.get("warnings", []), *summary_payload.get("warnings", [])],
    }
    _save_pack_artifact(pack_id, output_root, "study_kit.json", payload)
    return payload


def audio_script_for_course_pack(
    pack_id: str,
    query: str = "",
    output_root: str = "outputs",
    top_k: int = 4,
    mode: str = "briefing_3min",
    llm_provider: str = "mock",
    llm_model: str | None = None,
    grounding: str = "creative",
    target_minutes: int | None = None,
    target_chars: int | None = None,
    knowledge_scope: str = "course_pack",
) -> dict:
    chunks = _select_pack_chunks(pack_id, query=query, output_root=output_root, top_k=top_k)
    background_chunks: list[Chunk] = []
    if knowledge_scope in BACKGROUND_SCOPE_VALUES:
        background_chunks = background_chunks_for_query(query=query, source_chunks=chunks)
        chunks = _dedupe_chunks([*chunks, *background_chunks])
    payload = generate_audio_script(chunks, mode=mode, llm_provider=llm_provider, llm_model=llm_model, grounding=grounding, target_minutes=target_minutes, target_chars=target_chars)
    payload["knowledge_scope"] = knowledge_scope
    payload["background_sources"] = [chunk.metadata for chunk in background_chunks]
    _save_pack_artifact(pack_id, output_root, "audio_script.json", payload)
    return payload


def concept_map_for_course_pack(
    pack_id: str,
    output_root: str = "outputs",
) -> dict:
    chunks = load_course_pack_chunks(pack_id, output_root=output_root)
    return build_concept_map(chunks, output_dir=str(course_pack_dir(pack_id, output_root=output_root)))


def artifacts_for_course_pack(
    pack_id: str,
    output_root: str = "outputs",
    include_content: bool = True,
) -> dict:
    output_dir = course_pack_dir(pack_id, output_root=output_root)
    warnings: list[str] = []
    artifact_names = {
        "course_pack": "course_pack.json",
        "summary": "summary.json",
        "study_kit": "study_kit.json",
        "audio_script": "audio_script.json",
        "graph": "graph.json",
        "chunks": "chunks.json",
        "concept_map_mermaid": "concept_map.mmd",
        "concept_map_html": "concept_map.html",
        "hierarchical_summary_index": "hierarchical_summary_index.json",
    }
    artifacts = {
        name: _artifact_preview(output_dir / filename, include_content=include_content)
        for name, filename in artifact_names.items()
    }
    answers_dir = output_dir / "answers"
    answers = []
    if answers_dir.exists():
        answers = [_artifact_preview(path, include_content=include_content) for path in sorted(answers_dir.glob("*.json"))]

    missing = [name for name, artifact in artifacts.items() if not artifact["exists"]]
    if missing:
        warnings.append("Missing artifacts: " + ", ".join(missing))

    return {
        "pack_id": pack_id,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "answers": answers,
        "warnings": warnings,
    }


def export_concept_map_for_course_pack(
    pack_id: str,
    output_root: str = "outputs",
    max_nodes: int = 60,
    max_edges: int = 120,
) -> dict:
    output_dir = course_pack_dir(pack_id, output_root=output_root)
    graph = concept_map_for_course_pack(pack_id=pack_id, output_root=output_root)
    export = _export_concept_map(graph, output_dir=output_dir, max_nodes=max_nodes, max_edges=max_edges)
    return {
        "pack_id": pack_id,
        "output_dir": str(output_dir),
        "node_count": len(graph.get("nodes", [])),
        "edge_count": len(graph.get("edges", [])),
        **export,
        "warnings": [*graph.get("warnings", []), *export.get("warnings", [])],
    }


def select_balanced_course_pack_chunks(pack_id: str, query: str, output_root: str = "outputs", top_k: int = 4) -> list[Chunk]:
    chunks = load_course_pack_chunks(pack_id, output_root=output_root)
    return _balanced_chunks(query=query, chunks=chunks, top_k=top_k)



def _ask_course_pack_with_vector(pack_id: str, question: str, output_root: str, top_k: int, mode: str = "vector") -> dict:
    chunks = select_balanced_course_pack_chunks(pack_id, query=question, output_root=output_root, top_k=top_k)
    result = generate_source_grounded_answer(
        query=question,
        chunks=chunks,
        index_provider=_PreselectedIndexProvider(),
        llm_provider=MockLLMProvider(),
        top_k=top_k,
    )
    payload = result.to_dict()
    payload["mode"] = mode
    payload["retrieval_mode"] = "vector"
    return payload


def _ask_course_pack_with_router(pack_id: str, question: str, output_root: str, top_k: int) -> dict:
    route = classify_course_pack_question(question)
    selected_mode = route["selected_mode"]
    if selected_mode == "local_graph":
        payload = _ask_course_pack_with_graph(pack_id=pack_id, question=question, output_root=output_root, top_k=top_k)
    elif selected_mode == "hierarchical":
        payload = _ask_course_pack_with_hierarchical_summary(pack_id=pack_id, question=question, output_root=output_root, top_k=top_k)
    else:
        payload = _ask_course_pack_with_vector(pack_id=pack_id, question=question, output_root=output_root, top_k=top_k)

    payload["mode"] = "auto"
    payload["routed_mode"] = selected_mode
    payload["question_type"] = route["question_type"]
    payload["retrieval_plan"] = route["retrieval_plan"]
    payload["selected_retrievers"] = route["selected_retrievers"]
    if route["question_type"] == "mixed_question":
        payload["warnings"] = [
            *payload.get("warnings", []),
            "Mixed question routed to hierarchical summary first; course_graph is included in the retrieval plan for relationship follow-up.",
        ]
    return payload

def _ask_course_pack_with_hierarchical_summary(pack_id: str, question: str, output_root: str, top_k: int) -> dict:
    all_chunks = load_course_pack_chunks(pack_id, output_root=output_root)
    retrieval = retrieve_hierarchical_summary(query=question, chunks=all_chunks, pack_id=pack_id, top_k=top_k)
    chunks = retrieval.pop("chunks")

    result = generate_source_grounded_answer(
        query=question,
        chunks=chunks,
        index_provider=_PreselectedIndexProvider(),
        llm_provider=MockLLMProvider(),
        top_k=top_k,
    )
    payload = result.to_dict()
    payload["mode"] = "hierarchical"
    payload["retrieval_mode"] = "hierarchical_summary"
    payload["abstraction_level"] = retrieval["abstraction_level"]
    payload["selected_summary_nodes"] = retrieval["selected_summary_nodes"]
    payload["supporting_chunks"] = retrieval["supporting_chunks"]
    payload["hierarchical_summary_index"] = {
        "root_id": retrieval["hierarchical_summary_index"].get("root_id"),
        "node_count": len(retrieval["hierarchical_summary_index"].get("nodes", [])),
    }
    return payload

COURSE_GRAPH_PATH_RELATIONS = {
    "prerequisite_of",
    "explains",
    "contrasts",
    "used_in",
    "is_a",
    "reduces",
    "handles",
    "improves",
    "captures",
    "supports",
    "uses",
    "extends",
    "grounds",
    "augments",
    "builds",
    "related_to",
}
PREREQUISITE_RELATIONS = {"prerequisite_of"}
CONTRAST_RELATIONS = {"contrasts"}
STRUCTURAL_RELATIONS = {"contains", "mentions", "evidence_in", "appears_in", "introduces"}


def _ask_course_pack_with_graph(pack_id: str, question: str, output_root: str, top_k: int) -> dict:
    all_chunks = load_course_pack_chunks(pack_id, output_root=output_root)
    graph = _load_or_build_course_pack_graph(pack_id, output_root=output_root, chunks=all_chunks)
    graph_selection = _select_course_graph_context(question, graph)
    graph_edges = graph_selection["graph_context"]
    graph_chunks = _chunks_from_graph_edges(graph_edges, all_chunks)
    warnings: list[str] = []
    retrieval_mode = "course_graph_path" if graph_selection["graph_paths"] else "local_graph"

    if graph_chunks:
        chunks = _dedupe_chunks(graph_chunks)[:top_k]
    else:
        retrieval_mode = "local_graph_fallback_vector"
        warnings.append("No matching course graph evidence was found. Falling back to balanced vector retrieval.")
        chunks = _balanced_chunks(query=question, chunks=all_chunks, top_k=top_k)

    result = generate_source_grounded_answer(
        query=question,
        chunks=chunks,
        index_provider=_PreselectedIndexProvider(),
        llm_provider=MockLLMProvider(),
        top_k=top_k,
    )
    payload = result.to_dict()
    payload["mode"] = "local_graph"
    payload["retrieval_mode"] = retrieval_mode
    payload["graph_context"] = graph_edges
    payload["matched_entities"] = graph_selection["matched_entities"]
    payload["traversal_strategy"] = graph_selection["traversal_strategy"]
    payload["graph_paths"] = graph_selection["graph_paths"]
    payload["evidence_chunks"] = [source_ref.to_dict() for source_ref in _sources_from_chunks(chunks)]
    payload["warnings"] = [*payload.get("warnings", []), *warnings]
    return payload


def _load_or_build_course_pack_graph(pack_id: str, output_root: str, chunks: list[Chunk]) -> dict:
    output_dir = course_pack_dir(pack_id, output_root=output_root)
    return build_concept_map(chunks, output_dir=str(output_dir))


def _select_course_graph_context(question: str, graph: dict) -> dict:
    entities = sorted(_query_entities(question, graph))
    strategy = _graph_traversal_strategy(question, entities)
    graph_paths: list[dict] = []

    if not entities:
        return {
            "matched_entities": [],
            "traversal_strategy": strategy,
            "graph_context": [],
            "graph_paths": [],
        }

    if strategy == "prerequisite":
        graph_edges = _prerequisite_edges(entities, graph)
        graph_paths = _direct_edge_paths(graph_edges)
    elif strategy == "contrast":
        graph_edges = _contrast_edges(entities, graph)
        graph_paths = _direct_edge_paths(graph_edges)
    elif strategy == "path":
        graph_edges, graph_paths = _graph_paths_between_entities(entities, graph)
        if not graph_edges:
            graph_edges = _select_graph_edges(question, graph, entities=entities)
    else:
        graph_edges = _select_graph_edges(question, graph, entities=entities)

    return {
        "matched_entities": entities,
        "traversal_strategy": strategy,
        "graph_context": _dedupe_graph_edges(graph_edges),
        "graph_paths": graph_paths,
    }


def _graph_traversal_strategy(question: str, entities: list[str]) -> str:
    normalized = question.lower()
    if any(term in normalized for term in ["먼저", "이해하려면", "선수", "기초", "prerequisite", "before"]):
        return "prerequisite"
    if any(term in normalized for term in ["차이", "비교", "대조", "contrast", "different"]):
        return "contrast"
    if len(entities) >= 2 and any(term in normalized for term in ["연결", "흐름", "pipeline", "path", "connect"]):
        return "path"
    return "edge"


def _select_graph_edges(question: str, graph: dict, entities: list[str] | None = None) -> list[dict]:
    target_entities = set(entities or _query_entities(question, graph))
    if not target_entities:
        return []
    exact: list[dict] = []
    partial: list[dict] = []
    for edge in graph.get("edges", []):
        relation = str(edge.get("relation", ""))
        if relation in STRUCTURAL_RELATIONS:
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in target_entities and target in target_entities:
            exact.append(edge)
        elif source in target_entities or target in target_entities:
            partial.append(edge)
    return [*exact, *partial]


def _prerequisite_edges(entities: list[str], graph: dict) -> list[dict]:
    target_entities = set(entities)
    edges: list[dict] = []
    for edge in graph.get("edges", []):
        if edge.get("relation") in PREREQUISITE_RELATIONS and edge.get("target") in target_entities:
            edges.append(edge)
    if edges:
        return edges
    for edge in graph.get("edges", []):
        if edge.get("target") in target_entities and edge.get("relation") in {"is_a", "uses", "explains"}:
            edges.append(edge)
    return edges


def _contrast_edges(entities: list[str], graph: dict) -> list[dict]:
    target_entities = set(entities)
    edges = [
        edge
        for edge in graph.get("edges", [])
        if edge.get("relation") in CONTRAST_RELATIONS
        and (edge.get("source") in target_entities or edge.get("target") in target_entities)
    ]
    return edges or _select_graph_edges(" ".join(entities), graph, entities=entities)


def _graph_paths_between_entities(entities: list[str], graph: dict) -> tuple[list[dict], list[dict]]:
    edges: list[dict] = []
    paths: list[dict] = []
    for index, source in enumerate(entities):
        for target in entities[index + 1 :]:
            steps = _find_shortest_graph_path(source, target, graph, max_depth=4)
            if not steps:
                continue
            edges.extend(step[0] for step in steps)
            paths.append(_graph_path_payload(steps))
            if len(paths) >= 4:
                return _dedupe_graph_edges(edges), paths
    return _dedupe_graph_edges(edges), paths


def _find_shortest_graph_path(source: str, target: str, graph: dict, max_depth: int = 4) -> list[tuple[dict, str, str, str]]:
    adjacency: dict[str, list[tuple[str, dict, str]]] = {}
    for edge in graph.get("edges", []):
        relation = str(edge.get("relation", ""))
        if relation not in COURSE_GRAPH_PATH_RELATIONS:
            continue
        left = str(edge.get("source", ""))
        right = str(edge.get("target", ""))
        if not left or not right:
            continue
        adjacency.setdefault(left, []).append((right, edge, "forward"))
        adjacency.setdefault(right, []).append((left, edge, "reverse"))

    queue: list[tuple[str, list[tuple[dict, str, str, str]]]] = [(source, [])]
    visited = {source}
    while queue:
        current, path = queue.pop(0)
        if len(path) >= max_depth:
            continue
        for neighbor, edge, direction in adjacency.get(current, []):
            if neighbor in visited:
                continue
            next_path = [*path, (edge, direction, current, neighbor)]
            if neighbor == target:
                return next_path
            visited.add(neighbor)
            queue.append((neighbor, next_path))
    return []


def _graph_path_payload(steps: list[tuple[dict, str, str, str]]) -> dict:
    if not steps:
        return {"nodes": [], "edges": []}
    nodes = [steps[0][2]]
    edges: list[dict] = []
    for edge, direction, _current, neighbor in steps:
        nodes.append(neighbor)
        edges.append(
            {
                "source": edge.get("source"),
                "target": edge.get("target"),
                "relation": edge.get("relation"),
                "direction": direction,
                "evidence": edge.get("evidence", []),
            }
        )
    return {"nodes": nodes, "edges": edges, "description": _graph_path_description(nodes, edges)}


def _graph_path_description(nodes: list[str], edges: list[dict]) -> str:
    if not nodes:
        return ""
    parts = [nodes[0]]
    for index, edge in enumerate(edges):
        relation = str(edge.get("relation") or "related_to")
        arrow = f"--{relation}-->" if edge.get("direction") == "forward" else f"<--{relation}--"
        parts.extend([arrow, nodes[index + 1]])
    return " ".join(parts)


def _direct_edge_paths(edges: list[dict]) -> list[dict]:
    paths: list[dict] = []
    for edge in _dedupe_graph_edges(edges):
        paths.append(
            {
                "nodes": [edge.get("source"), edge.get("target")],
                "edges": [
                    {
                        "source": edge.get("source"),
                        "target": edge.get("target"),
                        "relation": edge.get("relation"),
                        "direction": "forward",
                        "evidence": edge.get("evidence", []),
                    }
                ],
                "description": f"{edge.get('source')} --{edge.get('relation')}--> {edge.get('target')}",
            }
        )
    return paths


def _dedupe_graph_edges(edges: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for edge in edges:
        evidence = (edge.get("evidence") or [{}])[0]
        key = (
            str(edge.get("source", "")),
            str(edge.get("target", "")),
            str(edge.get("relation", "")),
            str(evidence.get("chunk_id", "")),
        )
        if key in seen:
            continue
        deduped.append(edge)
        seen.add(key)
    return deduped


def _query_entities(question: str, graph: dict) -> set[str]:
    normalized = question.lower()
    entities: set[str] = set()
    for node in graph.get("nodes", []):
        if node.get("type") != "concept":
            continue
        node_id = str(node.get("id", ""))
        label = str(node.get("label") or node_id)
        if node_id.lower() in normalized or label.lower() in normalized:
            entities.add(node_id)
    return entities


def _chunks_from_graph_edges(edges: list[dict], chunks: list[Chunk]) -> list[Chunk]:
    selected: list[Chunk] = []
    for edge in edges:
        for evidence in edge.get("evidence", []) or []:
            matched = _chunk_from_evidence(evidence, chunks)
            if matched is not None:
                selected.append(matched)
    return selected


def _chunk_from_evidence(evidence: dict, chunks: list[Chunk]) -> Chunk | None:
    for chunk in chunks:
        metadata = chunk.metadata or {}
        if evidence.get("chunk_id") != chunk.chunk_id:
            continue
        if evidence.get("page") != chunk.page:
            continue
        if evidence.get("doc_id") and evidence.get("doc_id") != metadata.get("doc_id"):
            continue
        if evidence.get("filename") and evidence.get("filename") != metadata.get("filename"):
            continue
        return chunk
    return None


def _flashcards_from_study_payload(base: dict, summary_payload: dict, limit: int) -> list[dict]:
    cards: list[dict] = []
    for item in base.get("glossary", []):
        term = item.get("term")
        definition = item.get("definition")
        if not term or not definition:
            continue
        cards.append({"front": term, "back": definition, "sources": item.get("sources", [])})
        if len(cards) >= limit:
            return cards
    for item in summary_payload.get("key_concepts", []):
        term = item.get("term")
        description = item.get("description")
        if not term or not description:
            continue
        cards.append({"front": term, "back": description, "sources": item.get("sources", [])})
        if len(cards) >= limit:
            return cards
    return cards
def _select_pack_chunks(pack_id: str, query: str, output_root: str, top_k: int) -> list[Chunk]:
    chunks = load_course_pack_chunks(pack_id, output_root=output_root)
    if not query:
        return _balanced_chunks(query="전체 요약", chunks=chunks, top_k=max(top_k, len(_group_chunks_by_document(chunks))))
    return _balanced_chunks(query=query, chunks=chunks, top_k=top_k)


def _balanced_chunks(query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
    if not chunks or top_k <= 0:
        return []

    groups = _group_chunks_by_document(chunks)
    is_overview = _is_overview_query(query)
    selected: list[Chunk] = []

    for group in groups.values():
        contexts = retrieve_contexts(query=query, chunks=group, top_k=1).contexts if query else []
        if contexts:
            selected.extend(chunks_from_contexts(contexts))
            continue
        if is_overview:
            representative = _representative_chunk(group)
            if representative is not None:
                selected.append(representative)

    global_contexts = retrieve_contexts(query=query, chunks=chunks, top_k=max(top_k, 1)).contexts if query else []
    selected.extend(chunks_from_contexts(global_contexts))

    if not selected and is_overview:
        selected.extend(chunk for chunk in (_representative_chunk(group) for group in groups.values()) if chunk is not None)

    return _dedupe_chunks(selected)[:top_k]


def _group_chunks_by_document(chunks: list[Chunk]) -> OrderedDict[str, list[Chunk]]:
    groups: OrderedDict[str, list[Chunk]] = OrderedDict()
    for chunk in chunks:
        key = _document_key(chunk)
        groups.setdefault(key, []).append(chunk)
    return groups


def _document_key(chunk: Chunk) -> str:
    metadata = chunk.metadata or {}
    return str(metadata.get("doc_id") or metadata.get("filename") or "document")


def _representative_chunk(chunks: list[Chunk]) -> Chunk | None:
    if not chunks:
        return None
    meaningful = [chunk for chunk in chunks if len(chunk.text.strip()) >= 30]
    if meaningful:
        return meaningful[0]
    return chunks[0]


def _dedupe_chunks(chunks: list[Chunk]) -> list[Chunk]:
    deduped: list[Chunk] = []
    seen: set[tuple[str | None, str | None, int, str]] = set()
    for chunk in chunks:
        metadata = chunk.metadata or {}
        key = (metadata.get("doc_id"), metadata.get("filename"), chunk.page, chunk.chunk_id)
        if key in seen:
            continue
        deduped.append(chunk)
        seen.add(key)
    return deduped


def _is_overview_query(query: str) -> bool:
    normalized = query.lower()
    return not query.strip() or any(term in normalized for term in OVERVIEW_QUERY_TERMS)


def _pack_id_from_documents(documents: list[dict]) -> str:
    if not documents:
        return f"pack_{uuid4().hex[:12]}"
    digest = hashlib.sha256()
    for document in documents:
        digest.update(str(document.get("doc_id", "")).encode("utf-8"))
        digest.update(str(document.get("filename", "")).encode("utf-8"))
    return f"pack_{digest.hexdigest()[:16]}"


def _safe_pack_id(pack_id: str | None) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", pack_id or "").strip("-_.")
    return cleaned or f"pack_{uuid4().hex[:12]}"


def _artifact_name(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9가-힣_.-]+", "-", text or "answer").strip("-_.")
    return (cleaned or "answer")[:80]


def _save_pack_artifact(pack_id: str, output_root: str, name: str, payload: dict) -> None:
    path = course_pack_dir(pack_id, output_root=output_root) / name
    _write_json(path, payload)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _artifact_preview(path: Path, include_content: bool) -> dict:
    preview = {
        "name": path.name,
        "path": str(path),
        "exists": path.exists(),
    }
    if not path.exists() or not include_content:
        return preview
    if path.suffix.lower() == ".json":
        try:
            preview["data"] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            preview["error"] = f"invalid json: {error}"
        return preview
    text = path.read_text(encoding="utf-8")
    preview["text"] = text[:12000]
    preview["truncated"] = len(text) > 12000
    return preview


def _export_concept_map(graph: dict, output_dir: Path, max_nodes: int, max_edges: int) -> dict:
    max_nodes = max(1, max_nodes)
    max_edges = max(1, max_edges)
    nodes = graph.get("nodes", [])[:max_nodes]
    node_ids = {node.get("id") for node in nodes}
    edges = [edge for edge in graph.get("edges", []) if edge.get("source") in node_ids and edge.get("target") in node_ids]
    edges = edges[:max_edges]
    warnings: list[str] = []
    if len(graph.get("nodes", [])) > len(nodes):
        warnings.append(f"Concept map export limited nodes to {len(nodes)} of {len(graph.get('nodes', []))}.")
    if len(graph.get("edges", [])) > len(edges):
        warnings.append(f"Concept map export limited edges to {len(edges)} of {len(graph.get('edges', []))}.")

    mermaid = _concept_map_mermaid(nodes, edges)
    html = _concept_map_html(mermaid)
    mermaid_path = output_dir / "concept_map.mmd"
    html_path = output_dir / "concept_map.html"
    mermaid_path.parent.mkdir(parents=True, exist_ok=True)
    mermaid_path.write_text(mermaid, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return {
        "format": "mermaid",
        "mermaid_path": str(mermaid_path),
        "html_path": str(html_path),
        "mermaid": mermaid,
        "exported_node_count": len(nodes),
        "exported_edge_count": len(edges),
        "warnings": warnings,
    }


def _concept_map_mermaid(nodes: list[dict], edges: list[dict]) -> str:
    lines = ["flowchart LR"]
    id_map = {str(node.get("id")): f"n{index}" for index, node in enumerate(nodes)}
    for node in nodes:
        node_id = str(node.get("id"))
        mermaid_id = id_map[node_id]
        label = _mermaid_label(str(node.get("label") or node_id))
        shape = "{{{label}}}" if node.get("type") == "document" else "[{label}]"
        lines.append(f"  {mermaid_id}{shape.format(label=label)}")
    for edge in edges:
        source = id_map.get(str(edge.get("source")))
        target = id_map.get(str(edge.get("target")))
        if not source or not target:
            continue
        relation = _mermaid_label(str(edge.get("relation") or "related_to"))
        lines.append(f"  {source} -- {relation} --> {target}")
    return "\n".join(lines) + "\n"


def _concept_map_html(mermaid: str) -> str:
    escaped = mermaid.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"ko\">",
            "<head>",
            "  <meta charset=\"utf-8\" />",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
            "  <title>BeePDF Course Pack Concept Map</title>",
            "  <style>body{font-family:Arial,sans-serif;margin:24px;background:#f7f7f8;color:#171717}.wrap{max-width:1200px;margin:auto;background:white;border:1px solid #ddd;border-radius:8px;padding:20px}pre{white-space:pre-wrap;background:#111;color:#eee;padding:16px;border-radius:6px;overflow:auto}</style>",
            "</head>",
            "<body>",
            "  <div class=\"wrap\">",
            "    <h1>BeePDF Course Pack Concept Map</h1>",
            "    <p>Mermaid diagram generated from GraphRAG-lite concept relationships.</p>",
            "    <div class=\"mermaid\">",
            escaped,
            "    </div>",
            "    <h2>Mermaid Source</h2>",
            f"    <pre>{escaped}</pre>",
            "  </div>",
            "  <script type=\"module\">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs'; mermaid.initialize({startOnLoad:true});</script>",
            "</body>",
            "</html>",
        ]
    )


def _mermaid_label(text: str) -> str:
    cleaned = " ".join(text.split())[:80]
    return "\"" + cleaned.replace("\\", "\\\\").replace("\"", "\\\"") + "\""


class _PreselectedIndexProvider:
    def search(self, question: str, chunks: list[Chunk], top_k: int = 4) -> list[Chunk]:
        return chunks[:top_k]









