from __future__ import annotations

from v2.rag.answering import _sources_from_chunks
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
        "brief_1min": "Here is a one-minute source-grounded brief.",
        "briefing_3min": "Here is a three-minute briefing based on the document sources.",
        "lecture": "This lecture-style script walks through the cited document evidence.",
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
                "text": f"On page {chunk.page}, the document says: {_clean_text(chunk.text)}",
                "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
            }
        )
    return script


def _podcast_script(chunks: list[Chunk]) -> list[dict]:
    script: list[dict] = []
    for index, chunk in enumerate(chunks, start=1):
        speaker = "host" if index % 2 else "guest"
        prefix = "Let's look at" if speaker == "host" else "The source supports this with"
        script.append(
            {
                "speaker": speaker,
                "text": f"{prefix} page {chunk.page}: {_clean_text(chunk.text)}",
                "sources": [source.to_dict() for source in _sources_from_chunks([chunk])],
            }
        )
    return script


def _clean_text(text: str) -> str:
    return " ".join(text.split())[:320]
