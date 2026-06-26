from __future__ import annotations

import json
from pathlib import Path

from v2.providers.base import DocumentParser
from v2.schemas import AnswerWithSources, Chunk, PageMarkdown, RelationTriple, VectorSource


class LocalStorageProvider:
    def __init__(self, root: str = "outputs") -> None:
        self.root = Path(root)

    def save_json(self, doc_id: str, name: str, payload: dict) -> str:
        path = self.root / doc_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def save_bytes(self, doc_id: str, name: str, payload: bytes) -> str:
        path = self.root / doc_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return str(path)


class MockDocumentParser(DocumentParser):
    def parse(self, pdf_path: str) -> list[PageMarkdown]:
        return [
            PageMarkdown(
                page_number=1,
                markdown=(
                    "# BeePDF\n"
                    "sha256 cache reduces repeated processing cost. "
                    "request_id enables failure tracking. "
                    "OCR fallback handles scanned PDFs."
                ),
            )
        ]


class MockLLMProvider:
    def summarize(self, chunks: list[Chunk]) -> str:
        return "BeePDF는 PDF 처리 비용 절감, 장애 추적, 근거 기반 질의응답을 목표로 합니다."

    def answer(self, question: str, chunks: list[Chunk], graph_context: list[RelationTriple]) -> AnswerWithSources:
        sources = [VectorSource(page=chunk.page_number, chunk_id=chunk.chunk_id) for chunk in chunks]
        return AnswerWithSources(
            answer="BeePDF의 비용 절감은 OCR 호출 최소화와 sha256 캐시를 중심으로 설계됩니다.",
            vector_sources=sources,
            graph_context=graph_context,
        )

    def extract_relations(self, chunks: list[Chunk]) -> list[RelationTriple]:
        return [
            RelationTriple("sha256 cache", "reduces", "repeated processing cost"),
            RelationTriple("request_id", "enables", "failure tracking"),
            RelationTriple("OCR fallback", "handles", "scanned PDFs"),
        ]

    def generate_script(self, chunks: list[Chunk], minutes: int) -> str:
        return f"BeePDF v2 발표 대본입니다. 목표 길이는 {minutes}분입니다."


class MockTTSProvider:
    def synthesize(self, doc_id: str, script: str) -> str:
        return f"outputs/{doc_id}/mock-audio.mp3"


class MockIndexProvider:
    def build(self, doc_id: str, chunks: list[Chunk]) -> str:
        return f"outputs/{doc_id}/vector_index.json"

    def search(self, question: str, chunks: list[Chunk], top_k: int = 4) -> list[Chunk]:
        terms = {term.lower() for term in question.split() if len(term) > 1}
        scored = []
        for chunk in chunks:
            text = chunk.text.lower()
            score = sum(1 for term in terms if term in text)
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored[:top_k] if score > 0] or chunks[:top_k]
