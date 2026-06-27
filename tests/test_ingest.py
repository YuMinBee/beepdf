from __future__ import annotations

import json
import unittest
from pathlib import Path
from uuid import uuid4

from v2.ingest import ingest_local_document


TEST_TMP_ROOT = Path.cwd() / "outputs" / "_test_ingest"


class LocalDocumentIngestTest(unittest.TestCase):
    def _case_dir(self) -> Path:
        path = TEST_TMP_ROOT / uuid4().hex
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_ingest_txt_writes_expected_artifacts_and_page_chunks(self) -> None:
        root = self._case_dir()
        source = root / "sample.txt"
        source.write_text("BeePDF uses sha256 cache.\nrequest_id enables tracking.", encoding="utf-8")

        result = ingest_local_document(str(source), output_root=str(root / "outputs"), max_chunk_chars=30)

        self.assertEqual(result.filename, "sample.txt")
        self.assertEqual(result.page_count, 1)
        self.assertGreaterEqual(result.chunk_count, 1)
        self.assertEqual(result.warnings, [])

        output_dir = Path(result.output_dir)
        self.assertTrue((output_dir / "document.json").exists())
        self.assertTrue((output_dir / "pages.json").exists())
        self.assertTrue((output_dir / "chunks.json").exists())
        self.assertTrue((output_dir / "graph.json").exists())
        self.assertTrue((output_dir / "answers").is_dir())
        self.assertTrue((output_dir / "study_kit.json").exists())
        self.assertTrue((output_dir / "audio_script.json").exists())

        document = json.loads((output_dir / "document.json").read_text(encoding="utf-8"))
        chunks = json.loads((output_dir / "chunks.json").read_text(encoding="utf-8"))["chunks"]
        self.assertEqual(document["doc_id"], result.doc_id)
        self.assertEqual(chunks[0]["chunk_id"], "p1_c1")
        self.assertEqual(chunks[0]["page"], 1)
        self.assertEqual(chunks[0]["char_start"], 0)
        self.assertGreater(chunks[0]["char_end"], chunks[0]["char_start"])
        self.assertEqual(chunks[0]["metadata"]["filename"], "sample.txt")

    def test_ingest_md_writes_one_page_without_dependency(self) -> None:
        root = self._case_dir()
        source = root / "sample.md"
        source.write_text("# BeePDF\n\nGraphRAG-lite keeps relation context.", encoding="utf-8")

        result = ingest_local_document(str(source), output_root=str(root / "outputs"))

        self.assertEqual(result.filename, "sample.md")
        self.assertEqual(result.page_count, 1)
        self.assertGreaterEqual(result.chunk_count, 1)
        self.assertEqual(result.warnings, [])

    def test_missing_file_returns_warning_without_raising(self) -> None:
        root = self._case_dir()
        result = ingest_local_document(str(root / "missing.pdf"), output_root=str(root / "outputs"))

        self.assertEqual(result.page_count, 0)
        self.assertEqual(result.chunk_count, 0)
        self.assertTrue(result.warnings)

    def test_pdf_parser_failure_returns_warning_without_raising(self) -> None:
        root = self._case_dir()
        source = root / "sample.pdf"
        source.write_bytes(b"not a real pdf")

        result = ingest_local_document(str(source), output_root=str(root / "outputs"))

        self.assertEqual(result.page_count, 0)
        self.assertEqual(result.chunk_count, 0)
        self.assertTrue(result.warnings)

    def test_unsupported_extension_returns_warning_without_raising(self) -> None:
        root = self._case_dir()
        source = root / "sample.csv"
        source.write_text("a,b\n1,2", encoding="utf-8")

        result = ingest_local_document(str(source), output_root=str(root / "outputs"))

        self.assertEqual(result.page_count, 0)
        self.assertEqual(result.chunk_count, 0)
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
