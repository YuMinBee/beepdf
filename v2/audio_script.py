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
    script = _expand_script_to_target_chars(script, selected, mode=mode, target_chars=target_chars)

    return {
        "mode": mode,
        "script": script,
        "tts_status": "mock",
        "audio_path": None,
        "llm": {"provider": llm_provider, "model": llm_model, "status": "mock", "target_chars": target_chars},
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
        "brief_1min": "지금부터 핵심 개념을 1분 브리핑으로 빠르게 정리합니다.",
        "briefing_3min": "지금부터 강의자료의 핵심 흐름을 3분 브리핑으로 정리합니다.",
        "briefing_5min": "지금부터 강의자료의 핵심 흐름을 5분 심화 브리핑으로 정리합니다.",
        "lecture": "이 강의형 대본은 핵심 개념을 차례대로 연결해서 설명합니다.",
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
                "text": f"다음으로 살펴볼 내용은 {_script_sentence(chunk)} 입니다.",
                "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
            }
        )
    return script


def _podcast_script(chunks: list[Chunk]) -> list[dict]:
    script: list[dict] = [
        {
            "speaker": "host",
            "text": "오늘은 자연어처리 11주차의 핵심 흐름을 오디오 오버뷰처럼 정리해볼게요. BPE로 입력 표현을 안정화하고, RNN과 LSTM으로 순서 정보를 다루며, CNN으로 지역 패턴을 잡는 흐름을 중심으로 보면 됩니다.",
            "sources": [source.to_dict() for source in _sources_from_chunks([chunks[0]])],
        }
    ]
    for index, chunk in enumerate(chunks, start=1):
        sentence = _script_sentence(chunk)
        if index % 2:
            speaker = "host"
            text = f"먼저 살펴볼 포인트는 {sentence} 이 부분입니다. 여기서는 개념을 외우기보다 왜 이 방법이 필요한지에 집중하면 이해가 훨씬 쉬워집니다."
        else:
            speaker = "guest"
            text = f"맞아요. 이어서 보면 {sentence} 라는 흐름으로 연결됩니다. 앞에서 나온 개념이 다음 모델 구조나 학습 방식으로 어떻게 이어지는지 생각해보면 좋습니다."
        script.append(
            {
                "speaker": speaker,
                "text": text,
                "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
            }
        )
    script.append(
        {
            "speaker": "host",
            "text": "정리하면, BPE는 모르는 단어 문제를 줄이기 위한 입력 표현 전략이고, RNN과 LSTM은 순차적인 문맥을 처리하는 모델이며, CNN은 문장 안의 짧은 패턴을 빠르게 포착하는 방식입니다. 이 세 축을 하나의 파이프라인으로 보면 11주차 내용이 훨씬 자연스럽게 연결됩니다.",
            "sources": [source.to_dict() for source in _sources_from_chunks([chunks[-1]])],
        }
    )
    return script


def _script_char_count(script: list[dict]) -> int:
    return sum(len(str(segment.get("text") or "")) for segment in script)


def _source_dicts(chunk: Chunk | None) -> list[dict]:
    return [source.to_dict() for source in _sources_from_chunks([chunk])] if chunk else []


def _terms_for_audio(chunk: Chunk | None) -> str:
    if not chunk:
        return "핵심 개념"
    terms = _keyword_terms(chunk.text)[:4]
    return ", ".join(terms) if terms else "핵심 개념"


def _expand_script_to_target_chars(script: list[dict], chunks: list[Chunk], mode: str, target_chars: int | None) -> list[dict]:
    if not target_chars or target_chars <= 0:
        return script
    minimum_chars = int(target_chars * 0.9)
    if _script_char_count(script) >= minimum_chars:
        return script
    if not chunks:
        return script

    expanded = list(script)
    podcast_templates = [
        "여기서 {terms}를 한 번 더 풀어보면, {sentence} 이 내용은 단순한 정의라기보다 다음 단계의 모델이 입력을 어떻게 받아들이는지를 결정하는 출발점입니다. 그래서 학습할 때는 용어만 외우기보다 어떤 문제를 줄이기 위해 등장했는지 같이 보는 편이 좋습니다.",
        "조금 현실적인 예로 생각해보면, 문장이 들어왔을 때 모델은 바로 의미를 이해하는 것이 아니라 먼저 표현 단위를 만들고, 그 표현의 순서와 주변 패턴을 처리합니다. {sentence} 이 포인트는 바로 그 과정에서 어느 위치에 놓이는지 보여줍니다.",
        "학습자가 자주 헷갈리는 부분은 {terms}를 서로 독립된 암기 항목처럼 보는 것입니다. 하지만 Course Pack 흐름에서는 앞 개념이 뒤 개념의 입력 조건이나 비교 기준이 됩니다. 그래서 이 부분을 연결해서 보면 전체 파이프라인이 훨씬 선명해집니다.",
        "다시 말해 핵심은 ‘무엇을 계산하느냐’와 ‘어떤 정보를 보존하느냐’입니다. {sentence} 이 설명은 모델이 단어 조각, 순서 정보, 지역 패턴 중 어디에 초점을 맞추는지 구분하게 해줍니다.",
        "정리 관점에서 보면 {terms}는 시험 문제에서도 관계형으로 자주 물을 수 있습니다. 하나의 개념을 설명하라는 질문보다, 왜 필요한지, 어떤 한계를 줄이는지, 다음 모델과 어떻게 이어지는지를 말할 수 있어야 합니다.",
        "마지막으로 이 내용을 복습할 때는 세 문장으로 압축해보면 좋습니다. 첫째, 입력 표현을 안정화한다. 둘째, 순서와 문맥을 따라간다. 셋째, 짧은 패턴을 잡아낸다. {sentence} 이 문장은 그 중 한 축을 채워주는 단서입니다.",
    ]
    narrator_templates = [
        "다음 포인트는 {terms}입니다. {sentence} 이 내용은 앞뒤 개념과 함께 이해해야 하며, 단독 정의보다 학습 흐름 속 역할을 보는 것이 중요합니다.",
        "조금 더 풀어 설명하면, {sentence} 이 부분은 모델이 입력을 처리하고 특징을 만드는 과정에서 중요한 단서가 됩니다.",
    ]

    index = 0
    while _script_char_count(expanded) < minimum_chars and index < 40:
        chunk = chunks[index % len(chunks)]
        sentence = _script_sentence(chunk)
        terms = _terms_for_audio(chunk)
        if mode == "podcast":
            speaker = "guest" if index % 2 else "host"
            template = podcast_templates[index % len(podcast_templates)]
        else:
            speaker = "narrator"
            template = narrator_templates[index % len(narrator_templates)]
        expanded.append(
            {
                "speaker": speaker,
                "text": template.format(terms=terms, sentence=sentence),
                "sources": _source_dicts(chunk),
            }
        )
        index += 1
    return expanded


def _script_sentence(chunk: Chunk) -> str:
    terms = _keyword_terms(chunk.text)
    return _best_sentence(chunk.text, terms)[:320]
