from __future__ import annotations

import math

from .llm import EmbeddingClient
from .models import Asset, DuplicateCluster


class DuplicateDetector:
    def __init__(self, embedder: EmbeddingClient, threshold: float = 0.82) -> None:
        self.embedder = embedder
        self.threshold = threshold

    def detect(self, assets: list[Asset]) -> list[DuplicateCluster]:
        if len(assets) < 2:
            return []
        vectors = self.embedder.embed([f"{a.name}\n{a.content[:4000]}" for a in assets])
        parent = list(range(len(assets)))
        sims: dict[tuple[int, int], float] = {}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for i in range(len(assets)):
            for j in range(i + 1, len(assets)):
                sim = cosine(vectors[i], vectors[j])
                sims[(i, j)] = sim
                if sim >= self.threshold:
                    union(i, j)
        groups: dict[int, list[int]] = {}
        for i in range(len(assets)):
            groups.setdefault(find(i), []).append(i)
        clusters: list[DuplicateCluster] = []
        for indexes in groups.values():
            if len(indexes) < 2:
                continue
            pair_sims = [sims[tuple(sorted((i, j)))] for idx, i in enumerate(indexes) for j in indexes[idx + 1 :]]
            clusters.append(DuplicateCluster([assets[i] for i in indexes], sum(pair_sims) / len(pair_sims)))
        return sorted(clusters, key=lambda c: c.average_similarity, reverse=True)


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)
