from __future__ import annotations

import math

from .llm import EmbeddingClient
from .models import PackageDuplicateCluster, SkillPackage


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class PackageDuplicateDetector:
    """Detects duplicate SkillPackages by comparing SKILL.md content only.

    Ignores references/templates/scripts/assets.
    """

    def __init__(self, embedder: EmbeddingClient, threshold: float = 0.82) -> None:
        self.embedder = embedder
        self.threshold = threshold

    def detect(self, packages: list[SkillPackage]) -> list[PackageDuplicateCluster]:
        """Detect duplicate packages among the given list."""
        if len(packages) < 2:
            return []

        # Embed only SKILL.md content for comparison
        texts = [f"{p.skill_md.name}\n{p.skill_md.content[:4000]}" for p in packages]
        vectors = self.embedder.embed(texts)
        parent = list(range(len(packages)))
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

        for i in range(len(packages)):
            for j in range(i + 1, len(packages)):
                sim = _cosine(vectors[i], vectors[j])
                key = (min(i, j), max(i, j))
                sims[key] = sim
                if sim >= self.threshold:
                    union(i, j)

        groups: dict[int, list[int]] = {}
        for i in range(len(packages)):
            groups.setdefault(find(i), []).append(i)

        clusters: list[PackageDuplicateCluster] = []
        for indexes in groups.values():
            if len(indexes) < 2:
                continue
            pair_sims: list[float] = []
            for idx_i, i in enumerate(indexes):
                for j in indexes[idx_i + 1:]:
                    key = (min(i, j), max(i, j))
                    pair_sims.append(sims.get(key, 0.0))
            avg_sim = sum(pair_sims) / len(pair_sims) if pair_sims else 0.0
            clusters.append(PackageDuplicateCluster(
                packages=[packages[i] for i in indexes],
                average_similarity=avg_sim,
            ))

        return sorted(clusters, key=lambda c: c.average_similarity, reverse=True)
