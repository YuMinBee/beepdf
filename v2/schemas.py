from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PageMarkdown:
    page_number: int
    markdown: str
    parser: str = "mock"


@dataclass(slots=True)
class Chunk:
    chunk_id: str
    page_number: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VectorSource:
    page: int
    chunk_id: str
    score: float | None = None


@dataclass(slots=True)
class RelationTriple:
    subject: str
    predicate: str
    object: str

    def as_list(self) -> list[str]:
        return [self.subject, self.predicate, self.object]


@dataclass(slots=True)
class AnswerWithSources:
    answer: str
    vector_sources: list[VectorSource] = field(default_factory=list)
    graph_context: list[RelationTriple] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "vector_sources": [source.__dict__ for source in self.vector_sources],
            "graph_context": [triple.as_list() for triple in self.graph_context],
        }


@dataclass(slots=True)
class WorkflowError:
    request_id: str
    node: str
    error_type: str
    message: str
    retryable: bool = False
