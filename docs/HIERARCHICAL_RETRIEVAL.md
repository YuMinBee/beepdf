# Multi-level Summary Retrieval

CourseBee v2 uses a multi-level summary retrieval idea adapted to course materials. Instead of building a clustered embedding tree, the current implementation builds a course-structure-aware summary index from the natural hierarchy of learning materials.

```text
Chunk summaries
-> Lecture summaries
-> Course Pack summary
```

## Why

Chunk-level retrieval works well for local detail questions, but global overview questions often need a higher abstraction level.

```text
BPE와 OOV는 어떤 관계야?          -> chunk or graph retrieval
11주차 전체 흐름 설명해줘          -> multi-level summary retrieval
1차시부터 3차시까지 어떻게 이어져? -> lecture summary + supporting chunks
```

## Artifact

Course Pack ingestion writes:

```text
outputs/course_packs/{pack_id}/hierarchical_summary_index.json
```

The index contains:

```json
{
  "root_id": "course_pack_summary",
  "nodes": [
    {"type": "course_pack_summary", "children": ["lecture:11-1"]},
    {"type": "lecture_summary", "children": ["chunk_summary:..."]},
    {"type": "chunk_summary", "sources": [{"page": 3, "chunk_id": "p3_c1"}]}
  ]
}
```

## Retrieval Response

```json
{
  "mode": "hierarchical",
  "retrieval_mode": "hierarchical_summary",
  "abstraction_level": "course_pack",
  "selected_summary_nodes": [
    {"type": "course_pack_summary"},
    {"type": "lecture_summary"}
  ],
  "supporting_chunks": [
    {"filename": "자연어처리_11주차_1차시.pptx", "page": 3, "chunk_id": "p3_c1"}
  ]
}
```

## Scope

This is not a clustered embedding-tree implementation. It does not perform embedding clustering or recursive LLM summarization over clusters. The current version is a deterministic Course Pack hierarchy that separates global overview retrieval from local detail retrieval. It is inspired by hierarchical summarization ideas, but intentionally scoped to the current Course Pack structure.
