from __future__ import annotations

import math
import re
from collections import Counter

from v2.schemas import Chunk, RetrievalContext, RetrievalResult

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\uac00-\ud7a3]+")


def retrieve_contexts(query: str, chunks: list[Chunk], top_k: int = 4) -> RetrievalResult:
    query_terms = _tokenize(query)
    if not query_terms or top_k <= 0:
        return RetrievalResult(query=query, top_k=top_k, contexts=[])

    document_frequency = _document_frequency(chunks)
    total_docs = max(len(chunks), 1)
    scored: list[tuple[float, Chunk]] = []

    for chunk in chunks:
        chunk_terms = _tokenize(chunk.text)
        if not chunk_terms:
            continue
        term_counts = Counter(chunk_terms)
        score = 0.0
        for term in query_terms:
            if term not in term_counts:
                continue
            tf = term_counts[term] / len(chunk_terms)
            idf = math.log((1 + total_docs) / (1 + document_frequency.get(term, 0))) + 1
            score += tf * idf
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    contexts = [
        RetrievalContext(
            chunk_id=chunk.chunk_id,
            page=chunk.page,
            score=round(score, 4),
            text=chunk.text,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            metadata=chunk.metadata,
        )
        for score, chunk in scored[:top_k]
    ]
    return RetrievalResult(query=query, top_k=top_k, contexts=contexts)


def chunks_from_contexts(contexts: list[RetrievalContext]) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=context.chunk_id,
            page=context.page,
            text=context.text,
            char_start=context.char_start or 0,
            char_end=context.char_end or len(context.text),
            metadata={**context.metadata, "retrieval_score": context.score},
        )
        for context in contexts
    ]


def _document_frequency(chunks: list[Chunk]) -> dict[str, int]:
    frequency: dict[str, int] = {}
    for chunk in chunks:
        for term in set(_tokenize(chunk.text)):
            frequency[term] = frequency.get(term, 0) + 1
    return frequency


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text)]
