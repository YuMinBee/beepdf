from __future__ import annotations

from v2.rag.answering import _best_sentence, _keyword_terms, _source_label, _sources_from_chunks
from v2.schemas import Chunk

SUPPORTED_AUDIO_MODES = {"brief_1min", "briefing_3min", "lecture", "podcast"}
MODE_LIMITS = {
    "brief_1min": 1,
    "briefing_3min": 3,
    "lecture": 6,
    "podcast": 6,
}


def generate_audio_script(chunks: list[Chunk], mode: str = "briefing_3min") -> dict:
    warnings: list[str] = []
    if mode not in SUPPORTED_AUDIO_MODES:
        warnings.append(f"unsupported audio script mode: {mode}; using briefing_3min")
        mode = "briefing_3min"

    if not chunks:
        return {
            "mode": mode,
            "script": [],
            "tts_status": "mock",
            "audio_path": None,
            "warnings": ["No source chunks were provided. Audio script generation was skipped.", *warnings],
        }

    selected = chunks[: MODE_LIMITS[mode]]
    if mode == "podcast":
        script = _podcast_script(selected)
    else:
        script = _single_speaker_script(selected, mode)

    return {
        "mode": mode,
        "script": script,
        "tts_status": "mock",
        "audio_path": None,
        "warnings": warnings,
    }


def _single_speaker_script(chunks: list[Chunk], mode: str) -> list[dict]:
    opening = {
        "brief_1min": "지금부터 문서 근거에 기반한 1분 핵심 브리핑을 시작합니다.",
        "briefing_3min": "지금부터 검색된 문서 출처를 기준으로 3분 브리핑을 진행합니다.",
        "lecture": "이 강의형 대본은 각 페이지의 근거를 따라 핵심 개념을 차례대로 설명합니다.",
    }[mode]
    script = [
        {
            "speaker": "narrator",
            "text": opening,
            "sources": [source.to_dict() for source in _sources_from_chunks([chunks[0]])],
        }
    ]
    for chunk in chunks:
        script.append(
            {
                "speaker": "narrator",
                "text": f"{_source_label(chunk)}의 근거를 보면, {_script_sentence(chunk)}",
                "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
            }
        )
    return script


def _podcast_script(chunks: list[Chunk]) -> list[dict]:
    script: list[dict] = []
    for index, chunk in enumerate(chunks, start=1):
        if index % 2:
            speaker = "host"
            text = f"이번 근거는 {_source_label(chunk)}입니다. 핵심 문장은 '{_script_sentence(chunk)}'입니다."
        else:
            speaker = "guest"
            text = f"네, 이 출처는 질문과 관련해 '{_script_sentence(chunk)}'라는 내용을 뒷받침합니다."
        script.append(
            {
                "speaker": speaker,
                "text": text,
                "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
            }
        )
    return script


def _script_sentence(chunk: Chunk) -> str:
    terms = _keyword_terms(chunk.text)
    return _best_sentence(chunk.text, terms)[:320]
