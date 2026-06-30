from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from pathlib import Path
from uuid import uuid4

try:
    from fastapi import HTTPException
except ImportError:  # pragma: no cover
    HTTPException = None  # type: ignore[assignment]

from v2.api import routes
from v2.api.schemas import (
    CoursePackAudioScriptRequest,
    CoursePackConceptMapRequest,
    CoursePackConceptMapExportRequest,
    CoursePackIngestRequest,
    CoursePackJobRequest,
    CoursePackQueryRequest,
    CoursePackStudyKitRequest,
    CoursePackSummaryRequest,
)


TEST_OUTPUT_ROOT = Path.cwd() / "outputs" / "_test_course_packs"


class CoursePackBehaviorTest(unittest.TestCase):
    def _case_dir(self) -> Path:
        path = TEST_OUTPUT_ROOT / uuid4().hex
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _create_pack(self) -> tuple[dict, Path]:
        root = self._case_dir()
        first = root / "week1.txt"
        second = root / "week2.md"
        first.write_text(
            "Week 1 explains OCR, PDF parsing, source citation, and RAG chunks.",
            encoding="utf-8",
        )
        second.write_text(
            "# Week 2\n\nGraphRAG-lite builds a concept map. OCR supports scanned PDF parsing.",
            encoding="utf-8",
        )
        pack = routes.ingest_course_pack(
            CoursePackIngestRequest(
                paths=[str(first), str(second)],
                output_root=str(root / "outputs"),
                max_chunk_chars=90,
            )
        )
        return pack, root

    def test_v2_course_pack_ingests_multiple_documents(self) -> None:
        pack, _ = self._create_pack()

        self.assertTrue(pack["pack_id"].startswith("pack_"))
        self.assertEqual(pack["document_count"], 2)
        self.assertGreaterEqual(pack["chunk_count"], 2)
        self.assertEqual(pack["warnings"], [])
        self.assertTrue((Path(pack["output_dir"]) / "course_pack.json").exists())
        self.assertTrue((Path(pack["output_dir"]) / "chunks.json").exists())

    def test_v2_course_pack_chunks_keep_document_source(self) -> None:
        pack, _ = self._create_pack()
        chunks = json.loads((Path(pack["output_dir"]) / "chunks.json").read_text(encoding="utf-8"))["chunks"]

        first_metadata = chunks[0]["metadata"]
        self.assertIn("doc_id", first_metadata)
        self.assertIn("filename", first_metadata)
        self.assertEqual(first_metadata["pack_id"], pack["pack_id"])
        self.assertIn("page", chunks[0])
        self.assertIn("chunk_id", chunks[0])

    def test_v2_course_pack_ask_returns_document_sources(self) -> None:
        pack, root = self._create_pack()
        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="OCR PDF parsing source citation",
                output_root=str(root / "outputs"),
                top_k=4,
            )
        )

        self.assertTrue(response["answer"])
        self.assertTrue(response["sources"])
        source = response["sources"][0]
        self.assertIn("doc_id", source)
        self.assertIn("filename", source)
        self.assertIn("page", source)
        self.assertIn("chunk_id", source)

    def test_v2_course_pack_sources_include_lecture_metadata(self) -> None:
        root = self._case_dir()
        first = root / "자연어처리_11주차_1차시.txt"
        second = root / "자연어처리_11주차_2차시.txt"
        first.write_text("BPE reduces OOV through subword tokenization.", encoding="utf-8")
        second.write_text("LSTM improves RNN sequence memory with gates.", encoding="utf-8")
        pack = routes.ingest_course_pack(
            CoursePackIngestRequest(
                paths=[str(first), str(second)],
                output_root=str(root / "outputs"),
                max_chunk_chars=90,
            )
        )

        chunks = json.loads((Path(pack["output_dir"]) / "chunks.json").read_text(encoding="utf-8"))["chunks"]
        first_metadata = chunks[0]["metadata"]
        self.assertEqual(first_metadata["week"], 11)
        self.assertEqual(first_metadata["lecture_no"], 1)

        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="BPE OOV",
                output_root=str(root / "outputs"),
            )
        )
        source = response["sources"][0]
        self.assertEqual(source["week"], 11)
        self.assertEqual(source["lecture_no"], 1)
    def test_v2_course_pack_ask_local_graph_uses_edge_evidence(self) -> None:
        root = self._case_dir()
        first = root / "자연어처리_11주차_1차시.txt"
        first.write_text("BPE reduces OOV through subword tokenization.", encoding="utf-8")
        pack = routes.ingest_course_pack(
            CoursePackIngestRequest(
                paths=[str(first)],
                output_root=str(root / "outputs"),
                max_chunk_chars=120,
            )
        )

        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="BPE와 OOV는 어떤 관계야?",
                output_root=str(root / "outputs"),
                top_k=4,
                mode="local_graph",
            )
        )

        self.assertEqual(response["mode"], "local_graph")
        self.assertEqual(response["retrieval_mode"], "local_graph")
        self.assertTrue(response["sources"])
        self.assertTrue(response["graph_context"])
        self.assertTrue(any(edge["source"] == "BPE" and edge["target"] == "OOV" for edge in response["graph_context"]))
        self.assertTrue(response["graph_context"][0]["evidence"])
    def test_v2_course_pack_local_graph_returns_prerequisite_path(self) -> None:
        root = self._case_dir()
        first = root / "자연어처리_11주차_1차시.txt"
        first.write_text(
            "Tokenizer and subword tokenization are prerequisites for BPE. BPE reduces OOV.",
            encoding="utf-8",
        )
        pack = routes.ingest_course_pack(
            CoursePackIngestRequest(
                paths=[str(first)],
                output_root=str(root / "outputs"),
                max_chunk_chars=180,
            )
        )

        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="BPE를 이해하려면 먼저 뭘 알아야 해?",
                output_root=str(root / "outputs"),
                top_k=4,
                mode="local_graph",
            )
        )

        self.assertEqual(response["mode"], "local_graph")
        self.assertEqual(response["retrieval_mode"], "course_graph_path")
        self.assertEqual(response["traversal_strategy"], "prerequisite")
        self.assertIn("BPE", response["matched_entities"])
        self.assertTrue(response["graph_paths"])
        self.assertTrue(response["evidence_chunks"])
        self.assertTrue(
            any(
                edge["relation"] == "prerequisite_of" and edge["target"] == "BPE"
                for edge in response["graph_context"]
            )
        )

    def test_v2_course_pack_local_graph_returns_pipeline_paths(self) -> None:
        root = self._case_dir()
        first = root / "자연어처리_11주차_2차시.txt"
        first.write_text(
            "RNN handles sequence data in the NLP pipeline. "
            "LSTM improves RNN long-term dependency. "
            "CNN captures local pattern for text classification in the NLP pipeline.",
            encoding="utf-8",
        )
        pack = routes.ingest_course_pack(
            CoursePackIngestRequest(
                paths=[str(first)],
                output_root=str(root / "outputs"),
                max_chunk_chars=260,
            )
        )

        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="RNN, LSTM, CNN은 NLP pipeline에서 어떻게 연결돼?",
                output_root=str(root / "outputs"),
                top_k=4,
                mode="local_graph",
            )
        )

        self.assertEqual(response["retrieval_mode"], "course_graph_path")
        self.assertEqual(response["traversal_strategy"], "path")
        self.assertTrue({"RNN", "LSTM", "CNN"}.issubset(set(response["matched_entities"])))
        self.assertTrue(response["graph_paths"])
        self.assertTrue(any(edge["relation"] == "used_in" for edge in response["graph_context"]))
    def test_v2_course_pack_auto_router_selects_vector_for_fact_question(self) -> None:
        pack, root = self._create_pack()
        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="OCR 정의가 뭐야?",
                output_root=str(root / "outputs"),
                top_k=4,
                mode="auto",
            )
        )

        self.assertEqual(response["mode"], "auto")
        self.assertEqual(response["question_type"], "fact_question")
        self.assertEqual(response["routed_mode"], "vector")
        self.assertEqual(response["retrieval_mode"], "vector")
        self.assertIn("vector", response["selected_retrievers"])
        self.assertTrue(response["retrieval_plan"])

    def test_v2_course_pack_auto_router_selects_graph_for_relation_question(self) -> None:
        root = self._case_dir()
        first = root / "자연어처리_11주차_1차시.txt"
        first.write_text("BPE reduces OOV through subword tokenization.", encoding="utf-8")
        pack = routes.ingest_course_pack(
            CoursePackIngestRequest(paths=[str(first)], output_root=str(root / "outputs"), max_chunk_chars=120)
        )

        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="BPE와 OOV는 어떤 관계야?",
                output_root=str(root / "outputs"),
                top_k=4,
                mode="auto",
            )
        )

        self.assertEqual(response["mode"], "auto")
        self.assertEqual(response["question_type"], "relation_question")
        self.assertEqual(response["routed_mode"], "local_graph")
        self.assertEqual(response["retrieval_mode"], "local_graph")
        self.assertIn("course_graph", response["selected_retrievers"])
        self.assertTrue(response["graph_context"])

    def test_v2_course_pack_auto_router_selects_hierarchical_for_overview_question(self) -> None:
        pack, root = self._create_pack()
        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="course pack 전체 흐름 요약해줘",
                output_root=str(root / "outputs"),
                top_k=4,
                mode="auto",
            )
        )

        self.assertEqual(response["mode"], "auto")
        self.assertEqual(response["question_type"], "overview_question")
        self.assertEqual(response["routed_mode"], "hierarchical")
        self.assertEqual(response["retrieval_mode"], "hierarchical_summary")
        self.assertIn("hierarchical_summary", response["selected_retrievers"])
        self.assertTrue(response["selected_summary_nodes"])

    def test_v2_course_pack_auto_router_selects_prerequisite_graph_for_learning_path(self) -> None:
        root = self._case_dir()
        first = root / "자연어처리_11주차_1차시.txt"
        first.write_text(
            "Tokenizer and subword tokenization are prerequisites for BPE. BPE reduces OOV.",
            encoding="utf-8",
        )
        pack = routes.ingest_course_pack(
            CoursePackIngestRequest(paths=[str(first)], output_root=str(root / "outputs"), max_chunk_chars=180)
        )

        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="BPE를 이해하려면 먼저 뭘 알아야 해?",
                output_root=str(root / "outputs"),
                top_k=4,
                mode="auto",
            )
        )

        self.assertEqual(response["mode"], "auto")
        self.assertEqual(response["question_type"], "learning_path_question")
        self.assertEqual(response["routed_mode"], "local_graph")
        self.assertEqual(response["traversal_strategy"], "prerequisite")
        self.assertTrue(response["graph_paths"])

    def test_v2_course_pack_auto_router_returns_trace(self) -> None:
        root = self._case_dir()
        first = root / "nlp_week11_lecture1.txt"
        first.write_text("BPE reduces OOV through subword tokenization.", encoding="utf-8")
        pack = routes.ingest_course_pack(
            CoursePackIngestRequest(paths=[str(first)], output_root=str(root / "outputs"), max_chunk_chars=120)
        )

        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="What is the relationship between BPE and OOV?",
                output_root=str(root / "outputs"),
                top_k=4,
                mode="auto",
            )
        )

        trace = response["trace"]
        self.assertTrue(trace["request_id"].startswith("req_"))
        self.assertTrue(trace["stages"])
        self.assertTrue(any(stage["name"] == "classify_question" for stage in trace["stages"]))
        self.assertTrue(any(stage["name"] == "retrieve_graph_context" for stage in trace["stages"]))
        self.assertGreaterEqual(trace["retrieval_debug"]["candidate_chunks"], 1)
        self.assertGreaterEqual(trace["retrieval_debug"]["selected_chunks"], 1)
        self.assertFalse(trace["retrieval_debug"]["fallback_used"])

    def test_v2_course_pack_writes_hierarchical_summary_index(self) -> None:
        pack, _ = self._create_pack()
        index_path = Path(pack["output_dir"]) / "hierarchical_summary_index.json"
        self.assertTrue(index_path.exists())
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["root_id"], "course_pack_summary")
        node_types = {node["type"] for node in index["nodes"]}
        self.assertIn("course_pack_summary", node_types)
        self.assertIn("lecture_summary", node_types)
        self.assertIn("chunk_summary", node_types)

    def test_v2_course_pack_ask_hierarchical_summary_uses_overview_level(self) -> None:
        pack, root = self._create_pack()
        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="11주차 전체 흐름 설명해줘",
                output_root=str(root / "outputs"),
                top_k=4,
                mode="hierarchical",
            )
        )

        self.assertEqual(response["mode"], "hierarchical")
        self.assertEqual(response["retrieval_mode"], "hierarchical_summary")
        self.assertEqual(response["abstraction_level"], "course_pack")
        self.assertTrue(response["selected_summary_nodes"])
        self.assertTrue(any(node["type"] == "course_pack_summary" for node in response["selected_summary_nodes"]))
        self.assertTrue(response["supporting_chunks"])
        self.assertGreater(response["hierarchical_summary_index"]["node_count"], 0)
    def test_v2_course_pack_overview_query_balances_document_sources(self) -> None:
        pack, root = self._create_pack()
        response = routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="course pack overview summary",
                output_root=str(root / "outputs"),
                top_k=4,
            )
        )

        filenames = {source["filename"] for source in response["sources"]}
        self.assertIn("week1.txt", filenames)
        self.assertIn("week2.md", filenames)

    def test_v2_course_pack_study_kit_has_document_sources(self) -> None:
        pack, root = self._create_pack()
        response = routes.study_kit_course_pack(
            CoursePackStudyKitRequest(
                pack_id=pack["pack_id"],
                query="GraphRAG-lite concept map",
                output_root=str(root / "outputs"),
                max_items=3,
            )
        )

        self.assertTrue(response["summary"]["sources"])
        self.assertIn("doc_id", response["summary"]["sources"][0])
        self.assertTrue(all(item["sources"] for item in response["key_points"]))

    def test_v2_course_pack_study_kit_is_course_pack_shaped(self) -> None:
        pack, root = self._create_pack()
        response = routes.study_kit_course_pack(
            CoursePackStudyKitRequest(
                pack_id=pack["pack_id"],
                query="course pack overview summary",
                output_root=str(root / "outputs"),
                max_items=3,
            )
        )

        self.assertTrue(response["overview"]["text"])
        self.assertTrue(response["lecture_summaries"])
        self.assertIn("connections", response)
        self.assertTrue(response["key_concepts"])
        self.assertTrue(response["expected_questions"])
        self.assertTrue(response["flashcards"])
        self.assertTrue(response["sources"])
        self.assertTrue((Path(pack["output_dir"]) / "study_kit.json").exists())
    def test_v2_course_pack_summary_has_sources(self) -> None:
        pack, root = self._create_pack()
        response = routes.summary_course_pack(
            CoursePackSummaryRequest(
                pack_id=pack["pack_id"],
                question="course pack overview summary",
                output_root=str(root / "outputs"),
                top_k=4,
                max_items=3,
            )
        )

        self.assertEqual(response["pack_id"], pack["pack_id"])
        self.assertTrue(response["overview"]["text"])
        self.assertTrue(response["overview"]["sources"])
        self.assertTrue(response["lecture_summaries"])
        self.assertTrue(all(item["sources"] for item in response["lecture_summaries"]))
        self.assertTrue(response["key_concepts"])
        self.assertTrue((Path(pack["output_dir"]) / "summary.json").exists())

    def test_v2_course_pack_summary_openai_without_key_falls_back(self) -> None:
        pack, root = self._create_pack()
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            response = routes.summary_course_pack(
                CoursePackSummaryRequest(
                    pack_id=pack["pack_id"],
                    output_root=str(root / "outputs"),
                    llm_provider="openai",
                    llm_model="gpt-5.4-mini",
                )
            )

        self.assertEqual(response["llm"]["provider"], "openai")
        self.assertEqual(response["llm"]["status"], "fallback")
        self.assertTrue(response["overview"]["sources"])
        self.assertTrue(any("OPENAI_API_KEY" in warning for warning in response["warnings"]))

    def test_v2_course_pack_summary_openai_grounded_refine_passes_citation_check(self) -> None:
        pack, root = self._create_pack()
        refined = "OCR와 PDF parsing, source citation, RAG chunks, GraphRAG-lite concept map을 정리합니다."
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            with patch("v2.course_summary.OpenAIProvider.summarize", return_value=refined):
                response = routes.summary_course_pack(
                    CoursePackSummaryRequest(
                        pack_id=pack["pack_id"],
                        output_root=str(root / "outputs"),
                        llm_provider="openai",
                        llm_model="gpt-5.4-mini",
                    )
                )

        self.assertEqual(response["llm"]["status"], "used")
        self.assertEqual(response["overview"]["text"], refined)
        self.assertTrue(response["citation_check"]["checked"])
        self.assertTrue(response["citation_check"]["passed"])

    def test_v2_course_pack_summary_openai_ungrounded_refine_falls_back(self) -> None:
        pack, root = self._create_pack()
        ungrounded = "양자역학과 르네상스 미술사를 중심으로 설명합니다."
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            with patch("v2.course_summary.OpenAIProvider.summarize", return_value=ungrounded):
                response = routes.summary_course_pack(
                    CoursePackSummaryRequest(
                        pack_id=pack["pack_id"],
                        output_root=str(root / "outputs"),
                        llm_provider="openai",
                        llm_model="gpt-5.4-mini",
                    )
                )

        self.assertEqual(response["llm"]["status"], "fallback")
        self.assertNotEqual(response["overview"]["text"], ungrounded)
        self.assertTrue(response["citation_check"]["checked"])
        self.assertFalse(response["citation_check"]["passed"])
        self.assertTrue(response["citation_check"]["unsupported_terms"])
        self.assertTrue(any("citation_check" in warning for warning in response["warnings"]))


    def test_v2_course_pack_audio_script_has_document_sources(self) -> None:
        pack, root = self._create_pack()
        response = routes.audio_script_course_pack(
            CoursePackAudioScriptRequest(
                pack_id=pack["pack_id"],
                query="OCR",
                output_root=str(root / "outputs"),
                mode="briefing_3min",
            )
        )

        self.assertEqual(response["tts_status"], "mock")
        self.assertTrue(response["script"])
        self.assertTrue(all(item["sources"] for item in response["script"]))
        self.assertIn("filename", response["script"][0]["sources"][0])

    def test_v2_course_pack_audio_script_can_include_background_rag(self) -> None:
        pack, root = self._create_pack()
        response = routes.audio_script_course_pack(
            CoursePackAudioScriptRequest(
                pack_id=pack["pack_id"],
                query="BPE OOV CNN podcast background",
                output_root=str(root / "outputs"),
                mode="podcast",
                knowledge_scope="course_pack_plus_background",
            )
        )

        self.assertEqual(response["knowledge_scope"], "course_pack_plus_background")
        self.assertTrue(response["background_sources"])
        self.assertTrue(any(source.get("filename") == "background_nlp_reference.md" for item in response["script"] for source in item["sources"]))
    def test_v2_course_pack_concept_map_links_documents(self) -> None:
        pack, root = self._create_pack()
        response = routes.concept_map_course_pack(
            CoursePackConceptMapRequest(pack_id=pack["pack_id"], output_root=str(root / "outputs"))
        )

        self.assertIn("nodes", response)
        self.assertIn("edges", response)
        self.assertTrue(any(node.get("type") == "document" for node in response["nodes"]))
        self.assertTrue(any(edge.get("relation") == "appears_in" for edge in response["edges"]))
        self.assertTrue(all(edge["evidence"] for edge in response["edges"]))
        self.assertTrue(any("doc_id" in edge["evidence"][0] for edge in response["edges"] if edge["evidence"]))

    def test_v2_course_pack_artifacts_preview_returns_generated_outputs(self) -> None:
        pack, root = self._create_pack()
        routes.ask_course_pack(
            CoursePackQueryRequest(
                pack_id=pack["pack_id"],
                question="OCR source citation",
                output_root=str(root / "outputs"),
            )
        )
        routes.summary_course_pack(
            CoursePackSummaryRequest(pack_id=pack["pack_id"], output_root=str(root / "outputs"))
        )

        response = routes.get_course_pack_artifacts(
            pack["pack_id"],
            output_root=str(root / "outputs"),
            include_content=True,
        )

        self.assertEqual(response["pack_id"], pack["pack_id"])
        self.assertTrue(response["artifacts"]["course_pack"]["exists"])
        self.assertEqual(response["artifacts"]["course_pack"]["data"]["pack_id"], pack["pack_id"])
        self.assertTrue(response["artifacts"]["summary"]["exists"])
        self.assertTrue(response["artifacts"]["graph"]["exists"])
        self.assertTrue(response["answers"])

    def test_v2_course_pack_concept_map_export_writes_mermaid_and_html(self) -> None:
        pack, root = self._create_pack()
        response = routes.export_concept_map_course_pack(
            CoursePackConceptMapExportRequest(
                pack_id=pack["pack_id"],
                output_root=str(root / "outputs"),
                max_nodes=20,
                max_edges=40,
            )
        )

        mermaid_path = Path(response["mermaid_path"])
        html_path = Path(response["html_path"])
        self.assertTrue(mermaid_path.exists())
        self.assertTrue(html_path.exists())
        self.assertIn("flowchart LR", response["mermaid"])
        self.assertGreater(response["exported_node_count"], 0)
        self.assertGreater(response["exported_edge_count"], 0)
        self.assertIn("mermaid", html_path.read_text(encoding="utf-8"))



    def test_v2_course_pack_job_records_status_and_pack(self) -> None:
        root = self._case_dir()
        first = root / "nlp_week11_lecture1.txt"
        second = root / "nlp_week11_lecture2.txt"
        first.write_text("BPE reduces OOV through subword tokenization.", encoding="utf-8")
        second.write_text("LSTM improves RNN sequence memory with gates.", encoding="utf-8")

        job = routes.create_course_pack_job(
            CoursePackJobRequest(
                paths=[str(first), str(second)],
                output_root=str(root / "outputs"),
                max_chunk_chars=120,
                pack_id="pack_job_test",
            )
        )

        self.assertTrue(job["job_id"].startswith("job_"))
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["stage"], "completed")
        self.assertEqual(job["progress"], 1.0)
        self.assertEqual(job["processed_documents"], 2)
        self.assertEqual(job["total_documents"], 2)
        self.assertEqual(job["pack_id"], "pack_job_test")
        self.assertEqual(job["course_pack"]["pack_id"], "pack_job_test")

        loaded = routes.get_course_pack_job(job["job_id"], output_root=str(root / "outputs"))
        self.assertEqual(loaded["job_id"], job["job_id"])
        self.assertEqual(loaded["status"], "succeeded")
        self.assertTrue((root / "outputs" / "course_pack_jobs" / f"{job['job_id']}.json").exists())
        self.assertTrue((root / "outputs" / "course_packs" / "pack_job_test" / "course_pack.json").exists())

    def test_v2_missing_course_pack_returns_404(self) -> None:
        missing_id = f"missing-{uuid4().hex}"
        if HTTPException is None:
            with self.assertRaises(FileNotFoundError):
                routes.get_course_pack(missing_id, output_root=str(TEST_OUTPUT_ROOT))
        else:
            with self.assertRaises(HTTPException) as context:
                routes.get_course_pack(missing_id, output_root=str(TEST_OUTPUT_ROOT))
            self.assertEqual(context.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()





