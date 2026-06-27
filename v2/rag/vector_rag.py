from __future__ import annotations

from v2.providers.base import IndexProvider, LLMProvider
from v2.rag.retrieval import retrieve_contexts
from v2.schemas import AnswerWithSources, Chunk, RelationTriple, VectorSource

NO_CONTEXT_ANSWER = ""


def answer_with_sources(
    question: str,
    chunks: list[Chunk],
    index_provider: IndexProvider,
    llm_provider: LLMProvider,
    graph_context: list[RelationTriple] | None = None,
    top_k: int = 4,
) -> AnswerWithSources:
    selected_chunks = index_provider.search(question, chunks, top_k=top_k)
    if not selected_chunks:
        return AnswerWithSources(answer=NO_CONTEXT_ANSWER, vector_sources=[], graph_context=graph_context or [])
    return llm_provider.answer(question, selected_chunks, graph_context or [])


def retrieve_only(question: str, chunks: list[Chunk], top_k: int = 4) -> dict:
    return retrieve_contexts(question, chunks, top_k=top_k).to_dict()


def sources_from_chunks(chunks: list[Chunk]) -> list[VectorSource]:
    return [
        VectorSource(page=chunk.page, chunk_id=chunk.chunk_id, score=chunk.metadata.get("retrieval_score"))
        for chunk in chunks
    ]

