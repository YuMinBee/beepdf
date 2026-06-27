from __future__ import annotations

import unittest

from v2.api.routes import router
from v2.api.schemas import AudioScriptRequest, IngestRequest, QueryRequest


class ApiSchemaTest(unittest.TestCase):
    def test_pydantic_requests_validate_defaults(self) -> None:
        ingest = IngestRequest(path="sample.txt")
        query = QueryRequest(doc_id="abc123", question="What is this document about?")
        audio = AudioScriptRequest(doc_id="abc123", query="OCR", mode="briefing_3min")

        self.assertEqual(ingest.output_root, "outputs")
        self.assertEqual(query.top_k, 4)
        self.assertEqual(audio.mode, "briefing_3min")

    def test_router_is_defined_when_fastapi_is_available(self) -> None:
        if router is not None:
            paths = {getattr(route, "path", None) for route in router.routes}
            self.assertIn("/v2/documents/ingest", paths)
            self.assertIn("/v2/documents/{doc_id}", paths)
            self.assertIn("/v2/ask", paths)
            self.assertIn("/v2/study-kit", paths)
            self.assertIn("/v2/audio-script", paths)
            self.assertIn("/v2/concept-map", paths)


if __name__ == "__main__":
    unittest.main()

