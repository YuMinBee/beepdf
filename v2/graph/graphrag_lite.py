from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from v2.schemas import RelationTriple


class LiteRelationGraph:
    def __init__(self) -> None:
        self._edges: dict[str, list[RelationTriple]] = defaultdict(list)

    def add_triples(self, triples: Iterable[RelationTriple]) -> None:
        for triple in triples:
            self._edges[triple.subject.lower()].append(triple)
            self._edges[triple.object.lower()].append(triple)

    def neighbors_for_text(self, text: str, limit: int = 6) -> list[RelationTriple]:
        lowered = text.lower()
        matches: list[RelationTriple] = []
        seen: set[tuple[str, str, str]] = set()
        for entity, triples in self._edges.items():
            if entity not in lowered:
                continue
            for triple in triples:
                key = (triple.subject, triple.predicate, triple.object)
                if key in seen:
                    continue
                matches.append(triple)
                seen.add(key)
                if len(matches) >= limit:
                    return matches
        return matches

    def to_dict(self) -> dict[str, list[list[str]]]:
        return {entity: [triple.as_list() for triple in triples] for entity, triples in self._edges.items()}


def build_relation_graph(triples: list[RelationTriple]) -> LiteRelationGraph:
    graph = LiteRelationGraph()
    graph.add_triples(triples)
    return graph
