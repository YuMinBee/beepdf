from __future__ import annotations

import unittest

from v2.providers.base import IndexProvider, LLMProvider, ParserProvider, RetrieverProvider, StorageProvider, TTSProvider
from v2.providers.local import LexicalRetriever, LocalIndexProvider, LocalParserProvider, LocalStorageProvider, MockLLMProvider, MockTTSProvider, SimpleRetriever


class ProviderStructureTest(unittest.TestCase):
    def test_cloud_ready_provider_classes_exist(self) -> None:
        self.assertIsNotNone(StorageProvider)
        self.assertIsNotNone(LLMProvider)
        self.assertIsNotNone(TTSProvider)
        self.assertIsNotNone(RetrieverProvider)
        self.assertIsNotNone(IndexProvider)
        self.assertIsNotNone(ParserProvider)
        self.assertTrue(hasattr(LocalStorageProvider(), "save_json"))
        self.assertTrue(hasattr(MockLLMProvider(), "answer"))
        self.assertTrue(hasattr(MockTTSProvider(), "synthesize"))
        self.assertTrue(hasattr(LocalIndexProvider(), "search"))
        self.assertTrue(hasattr(LexicalRetriever(), "search"))
        self.assertTrue(hasattr(SimpleRetriever(), "search"))
        self.assertTrue(hasattr(LocalParserProvider(), "parse"))


    def test_lexical_retriever_returns_ranked_chunks(self) -> None:
        from v2.rag.chunking import chunk_pages
        from v2.schemas import PageMarkdown

        chunks = chunk_pages(
            [
                PageMarkdown(page_number=1, markdown="BPE reduces OOV", parser="txt"),
                PageMarkdown(page_number=2, markdown="CNN captures local pattern", parser="txt"),
            ],
            max_chars=100,
            filename="sample.txt",
        )

        result = LexicalRetriever().search("CNN local pattern", chunks, top_k=1)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].page, 2)
        self.assertEqual(result[0].metadata["filename"], "sample.txt")

    def test_mock_tts_provider_is_non_generating(self) -> None:
        self.assertIsNone(MockTTSProvider().synthesize("doc", "script"))


if __name__ == "__main__":
    unittest.main()
