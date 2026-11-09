"""Bounded dependency-aware retrieval for repository interviews."""
import re


def _references(chunks, limit=3):
    names = []
    for chunk in chunks[:8]:
        content = chunk.get("content", "")
        found = re.findall(
            r"\b(?:self\.)?settings\.([A-Za-z_]\w*)\b",
            content,
        )
        found += re.findall(
            r"(?m)^\s*from\s+[\w.]+\s+import\s+([A-Za-z_]\w*)",
            content,
        )
        for name in found:
            if name not in names:
                names.append(name)
            if len(names) >= limit:
                return names
    return names


def _definition(content, name):
    n = re.escape(name)
    return bool(re.search(
        rf"(?m)^\s*(?:(?:async\s+)?def|class)\s+{n}\b"
        rf"|^\s*{n}\s*(?::[^=\n]+)?=\s*[^=]",
        content,
    ))


def expand_dependencies(repository_id, hits, search, *, max_queries=3):
    if not hits:
        return hits

    commit = hits[0]["commit_sha"]
    names = _references(hits, max_queries)
    definitions = []

    for name in names:
        # Promote matching definitions already found by hybrid search.
        matches = [
            h for h in hits
            if h["commit_sha"] == commit
            and _definition(h.get("content", ""), name)
        ]

        # Search again only if the definition was not among initial hits.
        if not matches:
            matches = [
                h for h in search(repository_id, name, 20)["chunks"]
                if h["commit_sha"] == commit
                and _definition(h.get("content", ""), name)
            ]

        if matches:
            definitions.append(matches[0])

    # Two implementation chunks, required definitions, remaining evidence.
    ordered = definitions + hits
    result, seen = [], set()

    for hit in ordered:
        if hit["commit_sha"] != commit or hit["chunk_id"] in seen:
            continue
        seen.add(hit["chunk_id"])
        result.append(dict(
            hit, ranking_score=float(1000 - len(result))
        ))
        if len(result) == 20:
            break

    return result
