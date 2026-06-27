from __future__ import annotations

import re
from collections import Counter

from v2.rag.answering import _sources_from_chunks
from v2.schemas import Chunk

KNOWN_TERMS = {
    "OCR": "Optical character recognition for extracting text from scanned or image-based documents.",
    "RAG": "Retrieval augmented generation using retrieved document context before answering.",
    "GraphRAG": "A retrieval pattern that combines graph relationships with document context.",
    "GraphRAG-lite": "A lightweight graph retrieval design for entity and relation context.",
    "sha256": "A hash value used to identify identical files and reuse cached results.",
    "request_id": "A request identifier used to trace processing and failures.",
    "cache": "Stored processing results reused to reduce repeated work.",
}


def generate_study_kit(chunks: list[Chunk], max_items: int = 4) -> dict:
    if not chunks:
        return {
            "summary": {"text": "", "sources": []},
            "key_points": [],
            "glossary": [],
            "quiz": [],
            "expected_questions": [],
            "warnings": ["No source chunks were provided. Study kit generation was skipped."],
        }

    selected = chunks[:max_items]
    summary_chunk = selected[0]
    key_chunks = selected[:max_items]
    source_dicts = [source.to_dict() for source in _sources_from_chunks([summary_chunk])]

    return {
        "summary": {
            "text": _summarize_chunk(summary_chunk),
            "sources": source_dicts,
        },
        "key_points": [_key_point_from_chunk(chunk) for chunk in key_chunks],
        "glossary": _glossary_from_chunks(selected),
        "quiz": [_quiz_from_chunk(selected[0])],
        "expected_questions": [_expected_question_from_chunk(chunk) for chunk in key_chunks[:3]],
        "warnings": [],
    }


def _summarize_chunk(chunk: Chunk) -> str:
    sentence = _first_sentence(chunk.text)
    return f"This section explains: {sentence}"


def _key_point_from_chunk(chunk: Chunk) -> dict:
    return {
        "text": _first_sentence(chunk.text),
        "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
    }


def _glossary_from_chunks(chunks: list[Chunk]) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for chunk in chunks:
        lowered = chunk.text.lower()
        for term, definition in KNOWN_TERMS.items():
            if term.lower() not in lowered or term.lower() in seen:
                continue
            items.append(
                {
                    "term": term,
                    "definition": definition,
                    "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
                }
            )
            seen.add(term.lower())
    if items:
        return items

    term = _most_common_term(" ".join(chunk.text for chunk in chunks))
    if not term:
        return []
    return [
        {
            "term": term,
            "definition": f"A recurring term in the retrieved document context: {term}.",
            "sources": [source.to_dict() for source in _sources_from_chunks([chunks[0]])],
        }
    ]


def _quiz_from_chunk(chunk: Chunk) -> dict:
    source = [source.to_dict() for source in _sources_from_chunks([chunk])]
    return {
        "question": "Which statement is supported by the cited source chunk?",
        "choices": [
            _first_sentence(chunk.text),
            "The document has no retrievable source context.",
            "The answer should ignore page citations.",
            "The workflow must call a paid LLM API.",
        ],
        "answer": "A",
        "sources": source,
    }


def _expected_question_from_chunk(chunk: Chunk) -> dict:
    term = _most_common_term(chunk.text) or "this section"
    return {
        "question": f"What does the document say about {term}?",
        "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
    }


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return (parts[0] if parts and parts[0].strip() else text.strip())[:240]


def _most_common_term(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9가-힣_]{3,}", text.lower())
    if not tokens:
        return ""
    stopwords = {"the", "and", "for", "with", "this", "that", "from", "document", "source"}
    counts = Counter(token for token in tokens if token not in stopwords)
    return counts.most_common(1)[0][0] if counts else ""
