from __future__ import annotations

import json

try:
    from fastapi import APIRouter, HTTPException
except ImportError:  # Keeps the scaffold importable without FastAPI installed.
    APIRouter = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]

from v2.api.schemas import (
    AnswerResponse,
    AudioScriptRequest,
    AudioScriptResponse,
    ConceptMapRequest,
    ConceptMapResponse,
    CoursePackAudioScriptRequest,
    CoursePackConceptMapExportResponse,
    CoursePackConceptMapExportRequest,
    CoursePackArtifactsResponse,
    CoursePackConceptMapRequest,
    CoursePackIngestRequest,
    CoursePackQueryRequest,
    CoursePackResponse,
    CoursePackStudyKitRequest,
    CoursePackSummaryResponse,
    CoursePackSummaryRequest,
    DocumentResponse,
    IngestRequest,
    QueryRequest,
    StudyKitRequest,
)
from v2.audio_script import generate_audio_script
from v2.course_packs import (
    ask_course_pack as ask_course_pack_service,
    audio_script_for_course_pack,
    export_concept_map_for_course_pack,
    artifacts_for_course_pack,
    concept_map_for_course_pack,
    course_pack_dir,
    create_course_pack,
    load_course_pack,
    study_kit_for_course_pack,
    summary_for_course_pack,
)
from v2.documents import chunks_from_payload_or_doc, document_dir, load_document
from v2.graph.concept_map import build_concept_map
from v2.ingest import ingest_local_document
from v2.providers.local import LocalIndexProvider, MockLLMProvider
from v2.rag.answering import generate_source_grounded_answer
from v2.rag.retrieval import retrieve_contexts
from v2.study_kit import generate_study_kit

router = APIRouter(prefix="/v2", tags=["v2"]) if APIRouter else None


def _payload(model) -> dict:
    return model.model_dump(exclude_none=True) if hasattr(model, "model_dump") else model.dict(exclude_none=True)


def _query(payload: dict) -> str:
    return payload.get("question") or payload.get("query") or ""


def _selected_chunks(payload: dict):
    chunks = chunks_from_payload_or_doc(payload)
    query = _query(payload)
    if not query:
        return chunks
    result = retrieve_contexts(query=query, chunks=chunks, top_k=payload.get("top_k", 4))
    from v2.rag.retrieval import chunks_from_contexts

    return chunks_from_contexts(result.contexts)


def _save_doc_artifact(payload: dict, name: str, data: dict) -> None:
    doc_id = payload.get("doc_id")
    if not doc_id:
        return
    path = document_dir(doc_id, payload.get("output_root", "outputs")) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _raise_not_found(doc_id: str):
    if HTTPException is not None:
        raise HTTPException(status_code=404, detail={"error": "document_not_found", "doc_id": doc_id})
    raise FileNotFoundError(f"document not found: {doc_id}")


def _raise_pack_not_found(pack_id: str):
    if HTTPException is not None:
        raise HTTPException(status_code=404, detail={"error": "course_pack_not_found", "pack_id": pack_id})
    raise FileNotFoundError(f"course pack not found: {pack_id}")


def _ensure_course_pack(pack_id: str, output_root: str) -> dict:
    course_pack = load_course_pack(pack_id, output_root=output_root)
    if course_pack.get("warnings") and not course_pack.get("output_dir"):
        _raise_pack_not_found(pack_id)
    return course_pack


def ingest_document(request: IngestRequest) -> dict:
    payload = _payload(request)
    result = ingest_local_document(
        path=payload["path"],
        output_root=payload.get("output_root", "outputs"),
        max_chunk_chars=payload.get("max_chunk_chars", 900),
    )
    return result.to_dict()


def get_document(doc_id: str, output_root: str = "outputs") -> dict:
    document = load_document(doc_id, output_root=output_root)
    if document.get("warnings") and not document.get("filename"):
        _raise_not_found(doc_id)
    return document


def ask(request: QueryRequest) -> dict:
    payload = _payload(request)
    result = generate_source_grounded_answer(
        query=_query(payload),
        chunks=chunks_from_payload_or_doc(payload),
        index_provider=LocalIndexProvider(),
        llm_provider=MockLLMProvider(),
        top_k=payload.get("top_k", 4),
    )
    return result.to_dict()


def study_kit(request: StudyKitRequest) -> dict:
    payload = _payload(request)
    result = generate_study_kit(_selected_chunks(payload), max_items=payload.get("max_items", 4))
    _save_doc_artifact(payload, "study_kit.json", result)
    return result


def audio_script(request: AudioScriptRequest) -> dict:
    payload = _payload(request)
    result = generate_audio_script(
        _selected_chunks(payload),
        mode=payload.get("mode", "briefing_3min"),
        llm_provider=payload.get("llm_provider", "mock"),
        llm_model=payload.get("llm_model"),
        grounding=payload.get("grounding", "creative"),
        target_minutes=payload.get("target_minutes"),
        target_chars=payload.get("target_chars"),
    )
    _save_doc_artifact(payload, "audio_script.json", result)
    return result


def concept_map(request: ConceptMapRequest) -> dict:
    payload = _payload(request)
    output_dir = None
    if payload.get("doc_id"):
        output_dir = str(document_dir(payload["doc_id"], payload.get("output_root", "outputs")))
    return build_concept_map(_selected_chunks(payload), output_dir=output_dir)


def retrieve(request: QueryRequest) -> dict:
    payload = _payload(request)
    result = retrieve_contexts(
        query=_query(payload),
        chunks=chunks_from_payload_or_doc(payload),
        top_k=payload.get("top_k", 4),
    )
    return result.to_dict()


def ingest_course_pack(request: CoursePackIngestRequest) -> dict:
    payload = _payload(request)
    return create_course_pack(
        paths=payload.get("paths", []),
        output_root=payload.get("output_root", "outputs"),
        max_chunk_chars=payload.get("max_chunk_chars", 900),
        pack_id=payload.get("pack_id"),
    )


def get_course_pack(pack_id: str, output_root: str = "outputs") -> dict:
    return _ensure_course_pack(pack_id, output_root=output_root)


def get_course_pack_artifacts(pack_id: str, output_root: str = "outputs", include_content: bool = True) -> dict:
    _ensure_course_pack(pack_id, output_root=output_root)
    return artifacts_for_course_pack(pack_id=pack_id, output_root=output_root, include_content=include_content)


def ask_course_pack(request: CoursePackQueryRequest) -> dict:
    payload = _payload(request)
    _ensure_course_pack(payload["pack_id"], output_root=payload.get("output_root", "outputs"))
    return ask_course_pack_service(
        pack_id=payload["pack_id"],
        question=_query(payload),
        output_root=payload.get("output_root", "outputs"),
        top_k=payload.get("top_k", 4),
        mode=payload.get("mode", "vector"),
    )


def study_kit_course_pack(request: CoursePackStudyKitRequest) -> dict:
    payload = _payload(request)
    _ensure_course_pack(payload["pack_id"], output_root=payload.get("output_root", "outputs"))
    return study_kit_for_course_pack(
        pack_id=payload["pack_id"],
        query=_query(payload),
        output_root=payload.get("output_root", "outputs"),
        top_k=payload.get("top_k", 4),
        max_items=payload.get("max_items", 4),
    )


def summary_course_pack(request: CoursePackSummaryRequest) -> dict:
    payload = _payload(request)
    _ensure_course_pack(payload["pack_id"], output_root=payload.get("output_root", "outputs"))
    return summary_for_course_pack(
        pack_id=payload["pack_id"],
        query=_query(payload),
        output_root=payload.get("output_root", "outputs"),
        top_k=payload.get("top_k", 8),
        max_items=payload.get("max_items", 5),
        llm_provider=payload.get("llm_provider", "mock"),
        llm_model=payload.get("llm_model"),
    )


def audio_script_course_pack(request: CoursePackAudioScriptRequest) -> dict:
    payload = _payload(request)
    _ensure_course_pack(payload["pack_id"], output_root=payload.get("output_root", "outputs"))
    return audio_script_for_course_pack(
        pack_id=payload["pack_id"],
        query=_query(payload),
        output_root=payload.get("output_root", "outputs"),
        top_k=payload.get("top_k", 4),
        mode=payload.get("mode", "briefing_3min"),
        llm_provider=payload.get("llm_provider", "mock"),
        llm_model=payload.get("llm_model"),
        grounding=payload.get("grounding", "creative"),
        target_minutes=payload.get("target_minutes"),
        target_chars=payload.get("target_chars"),
        knowledge_scope=payload.get("knowledge_scope", "course_pack"),
    )


def export_concept_map_course_pack(request: CoursePackConceptMapExportRequest) -> dict:
    payload = _payload(request)
    _ensure_course_pack(payload["pack_id"], output_root=payload.get("output_root", "outputs"))
    return export_concept_map_for_course_pack(
        pack_id=payload["pack_id"],
        output_root=payload.get("output_root", "outputs"),
        max_nodes=payload.get("max_nodes", 60),
        max_edges=payload.get("max_edges", 120),
    )


def concept_map_course_pack(request: CoursePackConceptMapRequest) -> dict:
    payload = _payload(request)
    _ensure_course_pack(payload["pack_id"], output_root=payload.get("output_root", "outputs"))
    return concept_map_for_course_pack(pack_id=payload["pack_id"], output_root=payload.get("output_root", "outputs"))


def ingest_alias(request: IngestRequest) -> dict:
    return ingest_document(request)


def answer_alias(request: QueryRequest) -> dict:
    return ask(request)


if router:
    router.post("/documents/ingest", response_model=DocumentResponse)(ingest_document)
    router.get("/documents/{doc_id}", response_model=DocumentResponse)(get_document)
    router.post("/course-packs", response_model=CoursePackResponse)(ingest_course_pack)
    router.get("/course-packs/{pack_id}", response_model=CoursePackResponse)(get_course_pack)
    router.get("/course-packs/{pack_id}/artifacts", response_model=CoursePackArtifactsResponse)(get_course_pack_artifacts)
    router.post("/course-packs/ask", response_model=AnswerResponse)(ask_course_pack)
    router.post("/course-packs/study-kit")(study_kit_course_pack)
    router.post("/course-packs/summary", response_model=CoursePackSummaryResponse)(summary_course_pack)
    router.post("/course-packs/audio-script", response_model=AudioScriptResponse)(audio_script_course_pack)
    router.post("/course-packs/concept-map", response_model=ConceptMapResponse)(concept_map_course_pack)
    router.post("/course-packs/concept-map/export", response_model=CoursePackConceptMapExportResponse)(export_concept_map_course_pack)
    router.post("/ask", response_model=AnswerResponse)(ask)
    router.post("/study-kit")(study_kit)
    router.post("/audio-script", response_model=AudioScriptResponse)(audio_script)
    router.post("/concept-map", response_model=ConceptMapResponse)(concept_map)
    router.post("/retrieve")(retrieve)
    router.post("/ingest", response_model=DocumentResponse)(ingest_alias)
    router.post("/answer", response_model=AnswerResponse)(answer_alias)

