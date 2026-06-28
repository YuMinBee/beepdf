from __future__ import annotations

import unittest

from v2.providers.base import IndexProvider, LLMProvider, ParserProvider, StorageProvider, TTSProvider
from v2.providers.local import LocalIndexProvider, LocalParserProvider, LocalStorageProvider, MockLLMProvider, MockTTSProvider, SimpleRetriever


class ProviderStructureTest(unittest.TestCase):
    def test_cloud_ready_provider_classes_exist(self) -> None:
        self.assertIsNotNone(StorageProvider)
        self.assertIsNotNone(LLMProvider)
        self.assertIsNotNone(TTSProvider)
        self.assertIsNotNone(IndexProvider)
        self.assertIsNotNone(ParserProvider)
        self.assertTrue(hasattr(LocalStorageProvider(), "save_json"))
        self.assertTrue(hasattr(MockLLMProvider(), "answer"))
        self.assertTrue(hasattr(MockTTSProvider(), "synthesize"))
        self.assertTrue(hasattr(LocalIndexProvider(), "search"))
        self.assertTrue(hasattr(SimpleRetriever(), "search"))
        self.assertTrue(hasattr(LocalParserProvider(), "parse"))

    def test_mock_tts_provider_is_non_generating(self) -> None:
        self.assertIsNone(MockTTSProvider().synthesize("doc", "script"))


if __name__ == "__main__":
    unittest.main()
