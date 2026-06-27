from __future__ import annotations

import re

from v2.providers.base import IndexProvider, LLMProvider
from v2.schemas import Chunk, SourceGroundedAnswer, SourceRef

NO_CONTEXT_WARNING = "No relevant context was found in the document. Answer generation was skipped."


def generate_source_grounded_answer(
    query: str,
    chunks: list[Chunk],
    index_provider: IndexProvider,
    llm_provider: LLMProvider | None = None,
    top_k: int = 4,
) -> SourceGroundedAnswer:
    selected_chunks = index_provider.search(query, chunks, top_k=top_k)
    if not selected_chunks:
        return SourceGroundedAnswer(answer="", sources=[], warnings=[NO_CONTEXT_WARNING])

    sources = _sources_from_chunks(selected_chunks)
    answer = _compose_grounded_answer(query, selected_chunks)
    if not answer.strip():
        return SourceGroundedAnswer(answer="", sources=[], warnings=[NO_CONTEXT_WARNING])
    return SourceGroundedAnswer(answer=answer, sources=sources, warnings=[])


def _compose_grounded_answer(query: str, chunks: list[Chunk]) -> str:
    sentences: list[str] = []
    for chunk in chunks:
        sentences.extend(_split_sentences(chunk.text))
    selected = sentences[:3] or [chunk.text.strip() for chunk in chunks if chunk.text.strip()]
    evidence = " ".join(selected).strip()
    if not evidence:
        return ""
    return f"Based on the retrieved source chunks, {evidence}"


def _sources_from_chunks(chunks: list[Chunk]) -> list[SourceRef]:
    sources: list[SourceRef] = []
    seen: set[tuple[int, str]] = set()
    for chunk in chunks:
        key = (chunk.page, chunk.chunk_id)
        if key in seen:
            continue
        sources.append(SourceRef(page=chunk.page, chunk_id=chunk.chunk_id))
        seen.add(key)
    return sources


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [part.strip() for part in parts if part.strip()]
