from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from v2.schemas import Chunk, PageMarkdown, WorkflowError


@dataclass(slots=True)
class BeePDFState:
    request_id: str
    doc_id: str
    pdf_path: str
    selected_mode: str = "qa_mode"
    pages: list[PageMarkdown] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
    vector_index_path: str | None = None
    graph_path: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    errors: list[WorkflowError] = field(default_factory=list)

    def add_error(self, node: str, error: Exception, retryable: bool = False) -> None:
        self.errors.append(
            WorkflowError(
                request_id=self.request_id,
                node=node,
                error_type=error.__class__.__name__,
                message=str(error),
                retryable=retryable,
            )
        )
