from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from v2.schemas import Chunk


@dataclass(slots=True)
class CitationCheckResult:
    checked: bool
    passed: bool
    coverage: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    unsupported_terms: list[str] = field(default_factory=list)
    source_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


GENERIC_TERMS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "into",
    "about",
    "course",
    "pack",
    "summary",
    "overview",
    "document",
    "source",
    "sources",
    "chunk",
    "chunks",
    "page",
    "pages",
    "강의",
    "강의자료",
    "자료",
    "문서",
    "근거",
    "요약",
    "전체",
    "흐름",
    "학습",
    "정리",
    "중심",
    "내용",
    "설명",
    "다룹니다",
    "제공합니다",
    "기준",
    "포인트",
    "핵심",
    "개념",
    "파일명",
    "페이지",
}


def check_text_grounding(
    text: str,
    source_chunks: list[Chunk],
    min_coverage: float = 0.35,
    min_matched_terms: int = 2,
    max_terms: int = 40,
) -> CitationCheckResult:
    if not text.strip():
        return CitationCheckResult(
            checked=True,
            passed=False,
            source_count=len(source_chunks),
            warnings=["Citation check failed because the generated text is empty."],
        )
    if not source_chunks:
        return CitationCheckResult(
            checked=True,
            passed=False,
            warnings=["Citation check failed because no source chunks were provided."],
        )

    claim_terms = _unique_terms(text)[:max_terms]
    if not claim_terms:
        return CitationCheckResult(
            checked=True,
            passed=True,
            coverage=1.0,
            source_count=len(source_chunks),
            warnings=["Citation check found no non-generic claim terms to verify."],
        )

    source_terms = set(_unique_terms(" ".join(chunk.text for chunk in source_chunks), keep_generic=True))
    matched_terms = [term for term in claim_terms if term in source_terms]
    unsupported_terms = [term for term in claim_terms if term not in source_terms]
    coverage = len(matched_terms) / len(claim_terms)
    required_matches = min(min_matched_terms, len(claim_terms))
    passed = coverage >= min_coverage and len(matched_terms) >= required_matches

    warnings: list[str] = []
    if not passed:
        warnings.append(
            "Citation check failed because generated text introduced terms not supported by retrieved chunks."
        )

    return CitationCheckResult(
        checked=True,
        passed=passed,
        coverage=round(coverage, 3),
        matched_terms=matched_terms[:12],
        unsupported_terms=unsupported_terms[:12],
        source_count=len(source_chunks),
        warnings=warnings,
    )


def skipped_citation_check(reason: str, source_chunks: list[Chunk] | None = None) -> CitationCheckResult:
    return CitationCheckResult(
        checked=False,
        passed=True,
        source_count=len(source_chunks or []),
        warnings=[reason] if reason else [],
    )


def _unique_terms(text: str, keep_generic: bool = False) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"[A-Za-z0-9가-힣][A-Za-z0-9가-힣_-]{1,}", text):
        normalized = raw.lower().strip("_-")
        if len(normalized) < 2 or normalized in seen:
            continue
        if not keep_generic and normalized in GENERIC_TERMS:
            continue
        if normalized.isdigit() and len(normalized) < 3:
            continue
        terms.append(normalized)
        seen.add(normalized)
    return terms
