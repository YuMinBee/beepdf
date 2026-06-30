# Concept Graph Retrieval Evaluation

CourseBee v2 uses concept graph-assisted retrieval as a retrieval improvement device, not as a graph visualization feature. The goal is to decide when course graph context improves retrieval over the local lexical retriever, and when vector/lexical chunk retrieval is already sufficient.

This document is intentionally conservative: CourseBee does not claim a full graph indexing system. It evaluates a lightweight concept graph-assisted retrieval layer built from course structure nodes, concept edges, and evidence chunks.

## Evaluation Question

```text
Does the graph add retrieval value beyond chunk retrieval for this question shape?
```

CourseBee answers this by comparing three signals:

- vector/lexical result: which chunks are retrieved by term scoring
- graph result: which concept edges, graph paths, and evidence chunks are retrieved
- decision: whether the graph should be used, skipped, or treated as a fallback case

## Case Matrix

### Case 1. 단순 사실 질문

- Question: `OCR 정의가 뭐야?`
- Vector result: enough; direct source chunk is sufficient
- Graph result: not necessary
- Decision: `vector`

Why: fact questions usually need the most relevant evidence chunk, not a graph traversal.

### Case 2. 관계 질문

- Question: `BPE와 OOV는 어떤 관계야?`
- Vector result: may retrieve a BPE/OOV chunk, but relation direction can be implicit
- Graph result: `BPE --reduces--> OOV` edge plus evidence chunk
- Decision: `graph` explains the relationship more explicitly

Why: the graph stores relation direction and evidence together, so the answer can show not only that two concepts co-occur, but how they are connected.

### Case 3. 선수 개념 질문

- Question: `BPE를 이해하려면 먼저 뭘 알아야 해?`
- Vector result: often centers on BPE chunks
- Graph result: `subword tokenization -> BPE` prerequisite path
- Decision: `graph` provides a learning path

Why: prerequisite questions are path questions. A graph traversal can answer what comes before the target concept.

### Case 4. 개념 연결 질문

- Question: `RNN, LSTM, CNN은 NLP pipeline에서 어떻게 연결돼?`
- Vector result: retrieves separate chunks about each model
- Graph result: finds paths through `NLP pipeline`, `sequence data`, and `local pattern`
- Decision: `graph` helps organize cross-concept connections

Why: multi-concept relationship questions benefit from explicit paths between concept nodes.

### Case 5. No-context Graph Fallback

- Question: `Transformer와 Attention은 어떤 관계야?`
- Vector result: no strong matching source in the demo Course Pack
- Graph result: no matching concept edge
- Decision: fallback with warning instead of pretending graph evidence exists

Why: a graph retriever must expose failure clearly. CourseBee returns `local_graph_fallback_vector` with warnings when graph evidence is missing.

## Current Coverage

The current codebase already checks these behaviors.

Unit tests:

- `test_v2_course_pack_ask_local_graph_uses_edge_evidence`
- `test_v2_course_pack_local_graph_returns_prerequisite_path`
- `test_v2_course_pack_local_graph_returns_pipeline_paths`
- `test_v2_course_pack_auto_router_selects_graph_for_relation_question`
- `test_v2_course_pack_auto_router_selects_prerequisite_graph_for_learning_path`

Evaluation harness:

```bash
python eval/run_eval.py
```

Current snapshot:

| Metric | Result |
| --- | --- |
| Graph route useful cases | 4 / 4 |
| No-context fallback pass | 1 / 1 |
| Router accuracy | 10 / 10 |
| Source recall@5 | 10 / 10 |

## When Concept Graph Retrieval Should Not Be Used

Graph retrieval is not always better. CourseBee should prefer vector/lexical retrieval when:

- the question asks for a direct definition
- the answer is localized in one obvious source chunk
- no course graph entity is matched
- graph evidence would only add noise

This is why `mode="auto"` can route fact questions to `vector`, relation questions to `local_graph`, overview questions to `hierarchical`, and learning path questions to prerequisite graph traversal.

## Honest Limitations

This is concept graph-assisted retrieval, not full graph indexing.

Not implemented:

- global community detection
- graph community summarization
- large-scale entity resolution
- learned graph construction
- graph/vector answer quality benchmarking with human labels

Implemented:

- course structure nodes: document, lecture, page, chunk, concept
- evidence-backed concept edges
- direct relation lookup
- prerequisite path traversal
- multi-concept path search
- graph fallback with warnings
- evaluation cases for graph usefulness

## Next Improvements

Good next steps:

- Add `expected_graph_paths.json` to the evaluation harness.
- Compare vector-only and concept graph-assisted answers side by side in `eval/results`.
- Track graph precision by checking whether returned edges include required relation labels.
- Add hybrid retrieval fusion so graph evidence and vector evidence can be merged instead of routed exclusively.
