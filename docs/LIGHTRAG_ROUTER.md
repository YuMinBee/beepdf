# LightRAG-style Retrieval Router

CourseBee v2 uses a LightRAG-style routing idea to combine low-level factual retrieval with high-level relationship and overview retrieval. This is not a full LightRAG implementation. It is a deterministic Course Pack retrieval router that chooses among existing retrieval strategies.

## Retrieval Levels

| Level | Retriever | Best for |
| --- | --- | --- |
| Low-level | Vector chunk retrieval | factual/detail questions, exact source chunks |
| High-level | Course graph retrieval | relationships, prerequisite paths, concept connections |
| High-level | Hierarchical summary retrieval | week/course overview, lecture flow |

## Question Types

```text
fact_question          -> vector retrieval
relation_question      -> course graph retrieval
overview_question      -> hierarchical summary retrieval
learning_path_question -> prerequisite graph traversal
mixed_question         -> hierarchical summary first, graph noted in plan
```

## Example Request

```json
{
  "pack_id": "pack_static_nlp_11week_demo",
  "question": "BPE를 이해하려면 먼저 뭘 알아야 해?",
  "mode": "auto"
}
```

## Example Response Fields

```json
{
  "mode": "auto",
  "question_type": "learning_path_question",
  "routed_mode": "local_graph",
  "retrieval_plan": [
    {
      "level": "high",
      "strategy": "course_graph",
      "reason": "Question asks for prerequisite or learning path traversal."
    },
    {
      "level": "low",
      "strategy": "evidence_chunks",
      "reason": "Ground the graph path in source chunks."
    }
  ],
  "selected_retrievers": ["course_graph", "evidence_chunks"]
}
```

## Why It Matters

Without routing, users must know whether to choose vector, graph, or hierarchical retrieval. With `mode="auto"`, CourseBee chooses a retrieval strategy based on the question shape and still exposes the decision through `question_type`, `routed_mode`, and `retrieval_plan`.
