from __future__ import annotations

import re

from v2.providers.ollama import OllamaProvider, OllamaProviderError
from v2.rag.answering import _best_sentence, _keyword_terms, _source_label, _sources_from_chunks
from v2.schemas import Chunk

SUPPORTED_AUDIO_MODES = {"brief_1min", "briefing_3min", "briefing_5min", "lecture", "podcast"}
MODE_LIMITS = {
    "brief_1min": 1,
    "briefing_3min": 3,
    "briefing_5min": 5,
    "lecture": 6,
    "podcast": 6,
}
MODE_MINUTES = {
    "brief_1min": 1,
    "briefing_3min": 3,
    "briefing_5min": 5,
    "lecture": 8,
    "podcast": 6,
}


def generate_audio_script(
    chunks: list[Chunk],
    mode: str = "briefing_3min",
    llm_provider: str = "mock",
    llm_model: str | None = None,
    grounding: str = "creative",
    target_minutes: int | None = None,
    target_chars: int | None = None,
) -> dict:
    warnings: list[str] = []
    if grounding not in {"creative", "strict"}:
        warnings.append(f"unsupported grounding mode: {grounding}; using creative")
        grounding = "creative"
    if mode not in SUPPORTED_AUDIO_MODES:
        warnings.append(f"unsupported audio script mode: {mode}; using briefing_3min")
        mode = "briefing_3min"

    if not chunks:
        return {
            "mode": mode,
            "script": [],
            "tts_status": "mock",
            "audio_path": None,
            "llm": {"provider": llm_provider, "model": llm_model, "status": "skipped"},
            "grounding": grounding,
            "warnings": ["No source chunks were provided. Audio script generation was skipped.", *warnings],
        }

    selected = chunks[: MODE_LIMITS[mode]]
    minutes = target_minutes if target_minutes and target_minutes > 0 else MODE_MINUTES[mode]
    if llm_provider in {"ollama", "qwen"}:
        llm_payload = _ollama_script(selected, mode=mode, model=llm_model, grounding=grounding, minutes=minutes, target_chars=target_chars)
        warnings.extend(llm_payload["warnings"])
        if llm_payload["script"]:
            return {
                "mode": mode,
                "script": llm_payload["script"],
                "tts_status": "mock",
                "audio_path": None,
                "llm": llm_payload["llm"],
                "grounding": grounding,
                "warnings": warnings,
            }
    elif llm_provider not in {"mock", "rule", "local"}:
        warnings.append(f"unsupported audio script llm_provider: {llm_provider}; using rule-based fallback")

    if mode == "podcast":
        script = _podcast_script(selected)
    else:
        script = _single_speaker_script(selected, mode)

    return {
        "mode": mode,
        "script": script,
        "tts_status": "mock",
        "audio_path": None,
        "llm": {"provider": llm_provider, "model": llm_model, "status": "mock"},
        "grounding": grounding,
        "warnings": warnings,
    }


def _ollama_script(chunks: list[Chunk], mode: str, model: str | None, grounding: str = "creative", minutes: int | None = None, target_chars: int | None = None) -> dict:
    provider = OllamaProvider(model=model)
    try:
        text = provider.generate_script(chunks, minutes=minutes or MODE_MINUTES[mode], style=mode, grounding=grounding, target_chars=target_chars)
    except OllamaProviderError as exc:
        return {
            "script": [],
            "llm": {"provider": "ollama", "model": provider.model, "status": "fallback"},
            "warnings": [f"OllamaProvider failed. Falling back to rule-based audio script: {exc}"],
        }

    return {
        "script": _script_segments_from_llm_text(text, chunks, mode=mode),
        "llm": {"provider": "ollama", "model": provider.model, "status": "used", "grounding": grounding, "target_minutes": minutes or MODE_MINUTES[mode], "target_chars": target_chars},
        "warnings": [],
    }


def _script_segments_from_llm_text(text: str, chunks: list[Chunk], mode: str = "briefing_3min") -> list[dict]:
    if mode == "podcast":
        podcast_segments = _podcast_segments_from_llm_text(text, chunks)
        if podcast_segments:
            return podcast_segments

    paragraphs = [paragraph.strip(" -\t") for paragraph in re.split(r"\n\s*\n+", text) if paragraph.strip(" -\t")]
    if len(paragraphs) <= 1:
        paragraphs = [paragraph.strip(" -\t") for paragraph in text.splitlines() if paragraph.strip(" -\t")]
    if not paragraphs:
        paragraphs = [text.strip()]
    segments: list[dict] = []
    source_pool = chunks or []
    for index, paragraph in enumerate(paragraphs[:12]):
        source_chunk = source_pool[min(index, len(source_pool) - 1)] if source_pool else None
        sources = [source.to_dict() for source in _sources_from_chunks([source_chunk])] if source_chunk else []
        segments.append({"speaker": "narrator", "text": paragraph, "sources": sources})
    return segments


def _podcast_segments_from_llm_text(text: str, chunks: list[Chunk]) -> list[dict]:
    turns: list[tuple[str, str]] = []
    current_speaker: str | None = None
    current_lines: list[str] = []
    speaker_pattern = re.compile(r"^(HOST|GUEST|\uc9c4\ud589\uc790|\uac8c\uc2a4\ud2b8)\s*[:\uff1a]\s*(.*)$", re.IGNORECASE)
    inline_speaker_pattern = re.compile(r"\s+(HOST|GUEST|\uc9c4\ud589\uc790|\uac8c\uc2a4\ud2b8)\s*[:\uff1a]", re.IGNORECASE)
    normalized_text = inline_speaker_pattern.sub(r"\n\1: ", text.strip())

    for raw_line in normalized_text.splitlines():
        line = raw_line.strip().strip("*- ")
        if not line:
            continue
        match = speaker_pattern.match(line)
        if match:
            if current_speaker and current_lines:
                turns.append((current_speaker, " ".join(current_lines).strip()))
            label = match.group(1).lower()
            current_speaker = "host" if label in {"host", "\uc9c4\ud589\uc790"} else "guest"
            current_lines = [match.group(2).strip()] if match.group(2).strip() else []
        elif current_speaker:
            current_lines.append(line)

    if current_speaker and current_lines:
        turns.append((current_speaker, " ".join(current_lines).strip()))

    segments: list[dict] = []
    source_pool = chunks or []
    for index, (speaker, turn_text) in enumerate(turns[:40]):
        if not turn_text:
            continue
        source_chunk = source_pool[min(index // 2, len(source_pool) - 1)] if source_pool else None
        sources = [source.to_dict() for source in _sources_from_chunks([source_chunk])] if source_chunk else []
        segments.append({"speaker": speaker, "text": turn_text, "sources": sources})
    return segments

def _single_speaker_script(chunks: list[Chunk], mode: str) -> list[dict]:
    opening = {
        "brief_1min": "지금부터 문서 근거에 기반한 1분 핵심 브리핑을 시작합니다.",
        "briefing_3min": "지금부터 검색된 문서 출처를 기준으로 3분 브리핑을 진행합니다.",
        "briefing_5min": "지금부터 검색된 문서 출처를 기준으로 5분 심화 브리핑을 진행합니다.",
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
