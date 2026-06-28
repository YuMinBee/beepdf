from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AudioMode = Literal["brief_1min", "briefing_3min", "lecture", "podcast"]


class ChunkModel(BaseModel):
    chunk_id: str
    page: int = 1
    text: str
    char_start: int = 0
    char_end: int | None = None
    doc_id: str | None = None
    filename: str | None = None
    pack_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    path: str
    output_root: str = "outputs"
    max_chunk_chars: int = 900


class DocumentResponse(BaseModel):
    doc_id: str
    filename: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    output_dir: str | None = None
    warnings: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    doc_id: str | None = None
    question: str | None = None
    query: str | None = None
    top_k: int = 4
    output_root: str = "outputs"
    output_dir: str | None = None
    chunks: list[ChunkModel] | None = None


class AnswerResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StudyKitRequest(QueryRequest):
    max_items: int = 4


class AudioScriptRequest(QueryRequest):
    mode: AudioMode = "briefing_3min"


class AudioScriptResponse(BaseModel):
    mode: AudioMode | str
    script: list[dict[str, Any]] = Field(default_factory=list)
    tts_status: str = "mock"
    audio_path: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ConceptMapRequest(QueryRequest):
    pass


class ConceptMapResponse(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CoursePackIngestRequest(BaseModel):
    paths: list[str]
    output_root: str = "outputs"
    max_chunk_chars: int = 900
    pack_id: str | None = None


class CoursePackResponse(BaseModel):
    pack_id: str
    document_count: int | None = None
    chunk_count: int | None = None
    documents: list[dict[str, Any]] = Field(default_factory=list)
    output_dir: str | None = None
    warnings: list[str] = Field(default_factory=list)


class CoursePackQueryRequest(BaseModel):
    pack_id: str
    question: str | None = None
    query: str | None = None
    top_k: int = 4
    output_root: str = "outputs"


class CoursePackStudyKitRequest(CoursePackQueryRequest):
    max_items: int = 4


class CoursePackSummaryRequest(CoursePackQueryRequest):
    max_items: int = 5
    llm_provider: str = "mock"
    llm_model: str | None = None


class CoursePackSummaryResponse(BaseModel):
    pack_id: str | None = None
    overview: dict[str, Any] = Field(default_factory=dict)
    lecture_summaries: list[dict[str, Any]] = Field(default_factory=list)
    key_concepts: list[dict[str, Any]] = Field(default_factory=list)
    connections: list[dict[str, Any]] = Field(default_factory=list)
    review_points: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    llm: dict[str, Any] = Field(default_factory=dict)
    citation_check: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class CoursePackAudioScriptRequest(CoursePackQueryRequest):
    mode: AudioMode = "briefing_3min"


class CoursePackArtifactsResponse(BaseModel):
    pack_id: str
    output_dir: str | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)
    answers: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CoursePackConceptMapExportRequest(BaseModel):
    pack_id: str
    output_root: str = "outputs"
    max_nodes: int = 60
    max_edges: int = 120


class CoursePackConceptMapExportResponse(BaseModel):
    pack_id: str
    output_dir: str | None = None
    format: str = "mermaid"
    mermaid_path: str | None = None
    html_path: str | None = None
    mermaid: str | None = None
    node_count: int = 0
    edge_count: int = 0
    exported_node_count: int = 0
    exported_edge_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class CoursePackConceptMapRequest(BaseModel):
    pack_id: str
    output_root: str = "outputs"

