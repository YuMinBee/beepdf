from __future__ import annotations

LEARNING_PATH_TERMS = {
    "먼저",
    "이해하려면",
    "선수",
    "기초",
    "순서",
    "prerequisite",
    "before",
    "learning path",
}
OVERVIEW_TERMS = {
    "전체",
    "흐름",
    "개요",
    "요약",
    "정리",
    "주차",
    "course pack",
    "overview",
    "summary",
    "summarize",
}
RELATION_TERMS = {
    "관계",
    "연결",
    "관련",
    "이어",
    "차이",
    "비교",
    "대조",
    "pipeline",
    "connect",
    "relationship",
    "relation",
    "contrast",
    "compare",
}
FACT_TERMS = {
    "정의",
    "뜻",
    "뭐야",
    "무엇",
    "설명",
    "definition",
    "what is",
    "explain",
}


def classify_course_pack_question(question: str) -> dict:
    normalized = _normalize(question)
    has_learning_path = _has_any(normalized, LEARNING_PATH_TERMS)
    has_overview = _has_any(normalized, OVERVIEW_TERMS)
    has_relation = _has_any(normalized, RELATION_TERMS)
    has_fact = _has_any(normalized, FACT_TERMS)

    if has_learning_path:
        question_type = "learning_path_question"
        selected_mode = "local_graph"
        plan = [
            _plan("high", "course_graph", "Question asks for prerequisite or learning path traversal."),
            _plan("low", "evidence_chunks", "Ground the graph path in source chunks."),
        ]
    elif has_overview and has_relation:
        question_type = "mixed_question"
        selected_mode = "hierarchical"
        plan = [
            _plan("high", "hierarchical_summary", "Question asks for cross-lecture flow or overview."),
            _plan("high", "course_graph", "Relation terms indicate concepts may need graph follow-up."),
            _plan("low", "evidence_chunks", "Return supporting chunks for provenance."),
        ]
    elif has_overview:
        question_type = "overview_question"
        selected_mode = "hierarchical"
        plan = [
            _plan("high", "hierarchical_summary", "Question asks for course-level or lecture-level overview."),
            _plan("low", "supporting_chunks", "Attach representative source chunks."),
        ]
    elif has_relation:
        question_type = "relation_question"
        selected_mode = "local_graph"
        plan = [
            _plan("high", "course_graph", "Question asks about concept relationships or paths."),
            _plan("low", "evidence_chunks", "Use evidence chunks attached to graph edges."),
        ]
    else:
        question_type = "fact_question" if has_fact or normalized else "fact_question"
        selected_mode = "vector"
        plan = [
            _plan("low", "vector", "Question can be answered from local chunk-level evidence."),
        ]

    return {
        "question_type": question_type,
        "selected_mode": selected_mode,
        "selected_retrievers": [item["strategy"] for item in plan],
        "retrieval_plan": plan,
    }


def _plan(level: str, strategy: str, reason: str) -> dict:
    return {"level": level, "strategy": strategy, "reason": reason}


def _has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())
