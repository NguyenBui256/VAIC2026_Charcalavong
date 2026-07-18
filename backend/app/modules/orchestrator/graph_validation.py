"""Pure graph validation + topology helpers for the DAG workflow model (3A).

No DB / ORM here -- these operate on plain `node_key` strings and
`(from_key, to_key)` edge tuples so 3D authoring, seed scripts, and the 3B
engine all reuse them. `assert_valid_graph` is the single gate every
graph-definition write must pass.
"""

from __future__ import annotations

from collections import deque

__all__ = [
    "GraphValidationError",
    "assert_valid_graph",
    "root_keys",
    "parents_by_key",
    "topological_order",
]


class GraphValidationError(ValueError):
    """Raised when a node/edge set is not a valid DAG."""


def assert_valid_graph(node_keys: list[str], edges: list[tuple[str, str]]) -> None:
    """Raise `GraphValidationError` on a malformed graph.

    Rejects: duplicate node keys, edges referencing an unknown key, a
    self-loop, a duplicate edge, or any cycle (the edge set must be a DAG).
    """
    seen: set[str] = set()
    for key in node_keys:
        if key in seen:
            raise GraphValidationError(f"duplicate node_key: {key!r}")
        seen.add(key)

    edge_seen: set[tuple[str, str]] = set()
    for src, dst in edges:
        if src not in seen:
            raise GraphValidationError(f"edge references unknown from-node: {src!r}")
        if dst not in seen:
            raise GraphValidationError(f"edge references unknown to-node: {dst!r}")
        if src == dst:
            raise GraphValidationError(f"self-loop on node: {src!r}")
        if (src, dst) in edge_seen:
            raise GraphValidationError(f"duplicate edge: {src!r} -> {dst!r}")
        edge_seen.add((src, dst))

    # Kahn's algorithm: if the topological pass cannot consume every node,
    # a cycle exists.
    indegree = {k: 0 for k in node_keys}
    adjacency: dict[str, list[str]] = {k: [] for k in node_keys}
    for src, dst in edges:
        indegree[dst] += 1
        adjacency[src].append(dst)
    queue = deque(k for k in node_keys if indegree[k] == 0)
    consumed = 0
    while queue:
        node = queue.popleft()
        consumed += 1
        for child in adjacency[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if consumed != len(node_keys):
        raise GraphValidationError("graph contains a cycle")


def parents_by_key(
    node_keys: list[str], edges: list[tuple[str, str]]
) -> dict[str, list[str]]:
    """Map each node key to its parent keys (order = edge declaration order)."""
    parents: dict[str, list[str]] = {k: [] for k in node_keys}
    for src, dst in edges:
        if dst in parents:
            parents[dst].append(src)
    return parents


def root_keys(node_keys: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Node keys with no incoming edge -- they receive the run input directly."""
    has_parent = {dst for _, dst in edges}
    return [k for k in node_keys if k not in has_parent]


def topological_order(
    node_keys: list[str], edges: list[tuple[str, str]]
) -> list[str]:
    """Return node keys in a valid execution order. Assumes a valid DAG
    (call `assert_valid_graph` first)."""
    indegree = {k: 0 for k in node_keys}
    adjacency: dict[str, list[str]] = {k: [] for k in node_keys}
    for src, dst in edges:
        indegree[dst] += 1
        adjacency[src].append(dst)
    queue = deque(k for k in node_keys if indegree[k] == 0)
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for child in adjacency[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return order
