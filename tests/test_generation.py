from __future__ import annotations

import unittest

from v2.audio_script import generate_audio_script
from v2.graph.concept_map import build_concept_map
from v2.providers.mock import MockIndexProvider, MockLLMProvider
from v2.rag.answering import NO_CONTEXT_WARNING, generate_source_grounded_answer
from v2.rag.chunking import chunk_pages
from v2.schemas import PageMarkdown
from v2.study_kit import generate_study_kit


class SourceGroundedGenerationTest(unittest.TestCase):
    def _chunks(self):
        return chunk_pages(
            [
                PageMarkdown(
                    page_number=1,
                    markdown="BeePDF structures PDF processing and keeps page citations for RAG answers.",
                    parser="txt",
                ),
                PageMarkdown(
                    page_number=2,
                    markdown="OCR fallback handles scanned PDFs. sha256 cache reduces repeated processing cost.",
                    parser="txt",
                ),
            ],
            max_chars=120,
            filename="sample.txt",
        )

    def test_source_grounded_answer_has_real_sources(self) -> None:
        result = generate_source_grounded_answer(
            query="PDF page citations",
            chunks=self._chunks(),
            index_provider=MockIndexProvider(),
            llm_provider=MockLLMProvider(),
            top_k=2,
        )

        payload = result.to_dict()
        self.assertTrue(payload["answer"])
        self.assertGreaterEqual(len(payload["sources"]), 1)
        self.assertEqual(payload["sources"][0]["page"], 1)
        self.assertEqual(payload["sources"][0]["chunk_id"], "p1_c1")
        self.assertEqual(payload["warnings"], [])

    def test_source_grounded_answer_skips_when_no_context(self) -> None:
        result = generate_source_grounded_answer(
            query="unrelated banana",
            chunks=self._chunks(),
            index_provider=MockIndexProvider(),
            llm_provider=MockLLMProvider(),
        )

        self.assertEqual(result.answer, "")
        self.assertEqual(result.sources, [])
        self.assertEqual(result.warnings, [NO_CONTEXT_WARNING])

    def test_study_kit_preserves_sources_for_all_items(self) -> None:
        kit = generate_study_kit(self._chunks())

        self.assertTrue(kit["summary"]["sources"])
        self.assertTrue(kit["key_points"])
        self.assertTrue(kit["glossary"])
        self.assertTrue(kit["quiz"])
        self.assertTrue(kit["expected_questions"])
        self.assertTrue(all(item["sources"] for item in kit["key_points"]))
        self.assertTrue(all(item["sources"] for item in kit["glossary"]))
        self.assertTrue(all(item["sources"] for item in kit["quiz"]))
        self.assertTrue(all(item["sources"] for item in kit["expected_questions"]))
        self.assertEqual(kit["warnings"], [])

    def test_audio_script_modes_preserve_sources(self) -> None:
        for mode in ("brief_1min", "briefing_3min", "lecture", "podcast"):
            script = generate_audio_script(self._chunks(), mode=mode)

            self.assertEqual(script["mode"], mode)
            self.assertTrue(script["script"])
            self.assertEqual(script["tts_status"], "mock")
            self.assertIsNone(script["audio_path"])
            self.assertTrue(all(segment["sources"] for segment in script["script"]))
            self.assertEqual(script["warnings"], [])

    def test_concept_map_edges_have_evidence(self) -> None:
        graph = build_concept_map(self._chunks())

        self.assertTrue(graph["nodes"])
        self.assertTrue(graph["edges"])
        self.assertTrue(all(edge["evidence"] for edge in graph["edges"]))
        self.assertEqual(graph["warnings"], [])

    def test_empty_concept_map_returns_warning(self) -> None:
        graph = build_concept_map([])

        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["edges"], [])
        self.assertTrue(graph["warnings"])


if __name__ == "__main__":
    unittest.main()
