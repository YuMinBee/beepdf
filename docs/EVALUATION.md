# Evaluation

CourseBee v2 treats retrieval as a behavior that should be checked, not only described. The evaluation harness validates whether `mode="auto"` chooses the expected retrieval strategy, returns source evidence, uses graph context when appropriate, and falls back clearly when course graph evidence is missing.

## Files

```text
eval/
- golden_questions.jsonl
- expected_routes.json
- expected_sources.json
- run_eval.py
- results/latest_eval.md
```

The fixture used by `run_eval.py` is synthetic and public. It does not depend on private lecture materials.

## Run

```bash
python eval/run_eval.py
```

The command creates a temporary synthetic Course Pack under `outputs/_eval_runtime`, runs the golden questions through the same v2 API/service path used by the app, and writes the latest Markdown report to `eval/results/latest_eval.md`.

## Citation Quality

Citation quality is evaluated separately from answer style. The important question is whether generated claims remain tied to retrieved source chunks.

Tracked signals:

- source coverage
- unsupported claim detection
- source/chunk preview readiness
- answer sentence to supporting chunk mapping through preserved `sources`

`check_text_grounding` compares generated claim terms with source chunk terms and returns `coverage`, `matched_terms`, `unsupported_terms`, and warnings. API-refined Course Pack summaries must pass this check or CourseBee falls back to rule-based grounded output.

See [Citation and Grounding](CITATION_GROUNDING.md) for the source metadata flow.

## Current Snapshot

| Metric | Result |
| --- | --- |
| Overall pass rate | 10 / 10 |
| Router accuracy | 10 / 10 |
| Source recall@5 | 10 / 10 |
| Citation coverage | 0.90 |
| No-context fallback pass | 1 / 1 |
| Graph route useful cases | 4 / 4 |

## Metrics

- Router accuracy: checks `question_type`, `routed_mode`, and final `retrieval_mode` against `expected_routes.json`.
- Source recall@5: checks whether required filenames appear in answer sources, graph evidence, or hierarchical supporting chunks.
- Citation coverage: measures whether each answer returns at least one source-like evidence reference.
- Graph route useful cases: checks that graph-routed questions return graph context or graph paths and required concepts.
- No-context fallback pass: checks that relation questions without matching course graph evidence fall back with a warning instead of silently pretending graph evidence exists.

## Example Golden Case

```json
{
  "question": "BPE와 OOV는 어떤 관계야?",
  "expected_question_type": "relation_question",
  "expected_route": "local_graph",
  "must_include_sources": ["자연어처리_11주차_1차시.txt"],
  "must_include_concepts": ["BPE", "OOV"]
}
```

## Related Graph Evaluation

For a focused comparison of vector retrieval vs concept graph-assisted retrieval, see [Concept Graph Retrieval Evaluation](GRAPH_RAG_EVALUATION.md).

## Why It Matters

This makes CourseBee easier to judge as an engineering system. The router, provenance handling, concept graph-assisted path, multi-level summary path, and fallback behavior can be checked with repeatable data instead of only being explained in prose.
