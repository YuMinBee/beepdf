from __future__ import annotations

import re
from collections import Counter

from v2.rag.answering import _best_sentence, _keyword_terms, _source_label, _sources_from_chunks
from v2.schemas import Chunk

KNOWN_TERMS = {
    "OCR": "이미지나 스캔 문서 안의 문자를 인식해 텍스트로 바꾸는 기술입니다.",
    "RAG": "검색된 문서 근거를 먼저 찾고, 그 근거를 바탕으로 답변을 생성하는 방식입니다.",
    "GraphRAG": "문서의 개념과 관계 그래프를 검색 문맥에 함께 활용하는 검색 증강 생성 방식입니다.",
    "GraphRAG-lite": "가벼운 규칙 기반 개념/관계 그래프로 문서 간 연결을 보조하는 방식입니다.",
    "sha256": "파일 내용을 식별하고 같은 입력의 반복 처리를 줄이기 위한 해시값입니다.",
    "request_id": "요청별 처리 과정과 실패 지점을 추적하기 위한 식별자입니다.",
    "cache": "이미 처리한 결과를 재사용해 반복 비용을 줄이는 저장 구조입니다.",
    "OOV": "모델의 단어 집합에 없는 단어가 입력으로 들어오는 문제를 뜻합니다.",
    "Out-Of-Vocabulary": "모델이 학습한 어휘 목록 밖에 있는 단어를 의미합니다.",
    "BPE": "자주 함께 등장하는 문자 또는 문자열 쌍을 병합해 서브워드 단위를 만드는 알고리즘입니다.",
    "Byte Pair Encoding": "BPE의 전체 이름으로, 서브워드 토크나이징에 자주 쓰이는 압축 기반 병합 방식입니다.",
    "WordPiece": "단어를 더 작은 서브워드 단위로 나누는 토크나이저 계열입니다.",
    "Tokenizer": "문장을 모델이 처리할 수 있는 토큰 단위로 나누는 구성 요소입니다.",
    "subword": "단어보다 작고 문자보다 큰 의미 단위로, OOV 문제를 완화하는 데 쓰입니다.",
    "CNN": "합성곱 연산을 이용해 지역 패턴을 추출하는 신경망 구조입니다.",
    "RNN": "순차 데이터를 시간 순서대로 처리하는 순환 신경망 구조입니다.",
    "LSTM": "장기 의존성 문제를 완화하도록 게이트 구조를 둔 RNN 계열 모델입니다.",
    "GRU": "LSTM보다 단순한 게이트 구조로 순차 정보를 처리하는 RNN 계열 모델입니다.",
    "Transformer": "attention 구조를 중심으로 문맥 관계를 병렬적으로 처리하는 모델 구조입니다.",
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
    return f"{_source_label(chunk)} 근거에 따르면, 이 부분은 '{sentence}'를 중심으로 설명합니다."


def _key_point_from_chunk(chunk: Chunk) -> dict:
    sentence = _first_sentence(chunk.text)
    return {
        "text": f"{_source_label(chunk)}에서 확인되는 핵심 내용: {sentence}",
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
            "definition": f"검색된 문서 근거에서 반복적으로 등장하는 주요 표현입니다: {term}.",
            "sources": [source.to_dict() for source in _sources_from_chunks([chunks[0]])],
        }
    ]


def _quiz_from_chunk(chunk: Chunk) -> dict:
    source = [source.to_dict() for source in _sources_from_chunks([chunk])]
    supported = _first_sentence(chunk.text)
    return {
        "question": "다음 중 인용된 문서 근거가 직접 뒷받침하는 설명은 무엇인가요?",
        "choices": [
            supported,
            "검색된 문서 근거가 없어도 답변을 생성할 수 있다.",
            "출처 페이지와 chunk_id는 답변에서 생략해야 한다.",
            "현재 로컬 데모는 반드시 유료 LLM API를 호출해야 한다.",
        ],
        "answer": "A",
        "sources": source,
    }


def _expected_question_from_chunk(chunk: Chunk) -> dict:
    term = _most_common_term(chunk.text) or "이 부분"
    return {
        "question": f"{term}에 대해 이 자료가 설명하는 핵심은 무엇인가요?",
        "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
    }


def _first_sentence(text: str) -> str:
    sentence = _best_sentence(text, _keyword_terms(text))
    return sentence[:240]


def _most_common_term(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9가-힣_-]{3,}", text.lower())
    if not tokens:
        return ""
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "document",
        "source",
        "으로",
        "에서",
        "대한",
        "한다",
        "있다",
        "자료",
        "문서",
        "설명",
        "처리",
    }
    counts = Counter(token for token in tokens if token not in stopwords)
    return counts.most_common(1)[0][0] if counts else ""
