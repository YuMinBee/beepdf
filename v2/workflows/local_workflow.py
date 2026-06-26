from __future__ import annotations

from v2.providers.mock import LocalStorageProvider, MockDocumentParser, MockIndexProvider, MockLLMProvider
from v2.workflows.nodes import (
    chunk_node,
    citation_check_node,
    export_node,
    graph_index_node,
    graphrag_answer_node,
    parse_pdf_node,
    vector_index_node,
)
from v2.workflows.state import BeePDFState


def run_local_graphrag_demo(pdf_path: str, question: str, request_id: str = "req_demo") -> BeePDFState:
    state = BeePDFState(request_id=request_id, doc_id="demo_doc", pdf_path=pdf_path, selected_mode="graphrag_mode")
    parser = MockDocumentParser()
    storage = LocalStorageProvider()
    index = MockIndexProvider()
    llm = MockLLMProvider()

    state = parse_pdf_node(state, parser)
    state = chunk_node(state)
    state = vector_index_node(state, index)
    state = graph_index_node(state, llm, storage)
    state = graphrag_answer_node(state, question, index, llm)
    state = citation_check_node(state)
    state = export_node(state, storage)
    return state
