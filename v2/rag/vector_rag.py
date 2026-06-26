from __future__ import annotations

from v2.providers.base import IndexProvider, LLMProvider
from v2.schemas import AnswerWithSources, Chunk, RelationTriple


def answer_with_sources(
    question: str,
    chunks: list[Chunk],
    index_provider: IndexProvider,
    llm_provider: LLMProvider,
    graph_context: list[RelationTriple] | None = None,
    top_k: int = 4,
) -> AnswerWithSources:
    selected_chunks = index_provider.search(question, chunks, top_k=top_k)
    return llm_provider.answer(question, selected_chunks, graph_context or [])
