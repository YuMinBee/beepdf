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
