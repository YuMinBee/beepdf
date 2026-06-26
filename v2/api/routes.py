from __future__ import annotations

try:
    from fastapi import APIRouter
except ImportError:  # Keeps the scaffold importable without FastAPI installed.
    APIRouter = None  # type: ignore[assignment]

from v2.workflows.local_workflow import run_local_graphrag_demo

router = APIRouter(prefix="/v2", tags=["v2"]) if APIRouter else None

if router:

    @router.post("/ask")
    def ask(payload: dict) -> dict:
        state = run_local_graphrag_demo(
            pdf_path=payload.get("pdf_path", "demo.pdf"),
            question=payload.get("question", "BeePDF는 비용을 어떻게 줄이나요?"),
            request_id=payload.get("request_id", "req_demo"),
        )
        return {
            "request_id": state.request_id,
            "doc_id": state.doc_id,
            "answer": state.outputs.get("answer"),
            "citation_check": state.outputs.get("citation_check"),
            "errors": [error.__dict__ for error in state.errors],
        }

    @router.post("/graph/build")
    def build_graph(payload: dict) -> dict:
        state = run_local_graphrag_demo(
            pdf_path=payload.get("pdf_path", "demo.pdf"),
            question=payload.get("question", "BeePDF graph context"),
            request_id=payload.get("request_id", "req_demo"),
        )
        return {"graph_path": state.graph_path, "errors": [error.__dict__ for error in state.errors]}

    @router.post("/graph/query")
    def query_graph(payload: dict) -> dict:
        state = run_local_graphrag_demo(
            pdf_path=payload.get("pdf_path", "demo.pdf"),
            question=payload.get("question", "sha256 cache"),
            request_id=payload.get("request_id", "req_demo"),
        )
        return state.outputs.get("answer", {})

    @router.post("/summary")
    def summary(payload: dict) -> dict:
        state = run_local_graphrag_demo(
            pdf_path=payload.get("pdf_path", "demo.pdf"),
            question="summary",
            request_id=payload.get("request_id", "req_demo"),
        )
        return {"doc_id": state.doc_id, "chunks": len(state.chunks), "errors": [error.__dict__ for error in state.errors]}

    @router.post("/concept-map")
    def concept_map(payload: dict) -> dict:
        state = run_local_graphrag_demo(
            pdf_path=payload.get("pdf_path", "demo.pdf"),
            question="concept map",
            request_id=payload.get("request_id", "req_demo"),
        )
        return {"graph_path": state.graph_path, "graph_context": [triple.as_list() for triple in state.outputs.get("graph_context", [])]}
