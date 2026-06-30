# Concept Graph-assisted Retrieval

CourseBee v2 uses Concept Graph-assisted Retrieval as a lightweight retrieval layer over a Course Pack. It is not a full graph indexing system. The graph is built from course structure nodes and evidence-backed concept relations that can be used during retrieval.

## Graph Shape

```text
Document Node
-> Lecture Node
-> Page Node
-> Chunk Node
-> Concept Node
```

Representative relation types:

```text
document -> contains -> lecture
lecture -> contains -> page
page -> contains -> chunk
chunk -> mentions -> concept
lecture -> introduces -> concept
concept -> prerequisite_of -> concept
concept -> explains -> concept
concept -> contrasts -> concept
concept -> used_in -> concept
concept -> evidence_in -> chunk
```

## Retrieval Modes

`local_graph` starts by matching entities in the question, then chooses a lightweight traversal strategy.

| Question shape | Strategy | Example |
| --- | --- | --- |
| Direct relation | `edge` | `BPE와 OOV는 어떤 관계야?` |
| Prior knowledge | `prerequisite` | `BPE를 이해하려면 먼저 뭘 알아야 해?` |
| Concept connection | `path` | `RNN, LSTM, CNN은 NLP pipeline에서 어떻게 연결돼?` |
| Comparison | `contrast` | `RNN과 CNN은 뭐가 달라?` |

## Query Output

```json
{
  "mode": "local_graph",
  "retrieval_mode": "course_graph_path",
  "matched_entities": ["BPE"],
  "traversal_strategy": "prerequisite",
  "graph_paths": [
    {
      "nodes": ["subword tokenization", "BPE"],
      "edges": [{"relation": "prerequisite_of"}]
    }
  ],
  "evidence_chunks": [
    {
      "filename": "자연어처리_11주차_1차시.pptx",
      "page": 3,
      "chunk_id": "p3_c1"
    }
  ]
}
```

## Scope

The implementation intentionally avoids claiming a full graph indexing stack. It does not perform global community detection, graph summarization, or large-scale entity resolution. Instead, it provides a practical Course Pack retrieval layer where structure and concept paths help select evidence chunks before answer generation.

## Evaluation

See [Concept Graph Retrieval Evaluation](GRAPH_RAG_EVALUATION.md) for case-based comparisons of vector retrieval, graph retrieval, prerequisite traversal, pipeline paths, and no-context fallback behavior.
