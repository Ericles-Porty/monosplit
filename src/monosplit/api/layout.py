"""Seeded force-directed layout of the class graph.

The web interface draws every decomposition of an application on the same node
positions, so the positions are computed once here, with a fixed seed, and shipped with
the graph. Fruchterman-Reingold on the classes that have edges, with edge weights
log(1 + calls in both directions) and a weak pull toward the centre. Classes without
edges go in a row below the drawing, so they do not stretch it.

Coordinates are in screen pixels at zoom 1: the drawing spans about 90 * sqrt(n) pixels,
which keeps the node density, and the labels, readable for small and large graphs.
"""

from __future__ import annotations

import math

import numpy as np

from ..graph import CallGraph

ISOLATED_GAP = 70.0
ISOLATED_SPACING = 80.0


def _fruchterman_reingold(weights: np.ndarray, seed: int, iterations: int) -> np.ndarray:
    n = weights.shape[0]
    rng = np.random.default_rng(seed)
    pos = rng.uniform(-1.0, 1.0, size=(n, 2))
    if n == 1:
        return np.zeros((1, 2))
    k = 1.0 / math.sqrt(n)  # ideal distance for unit area
    temperature = 0.2
    cooling = temperature / iterations
    gravity = 0.08
    for _ in range(iterations):
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.linalg.norm(delta, axis=-1)
        np.fill_diagonal(dist, 1.0)
        dist = np.maximum(dist, 1e-3)
        repulsion = (k * k / dist**2)[:, :, None] * delta
        attraction = (weights * dist / k)[:, :, None] * delta
        displacement = repulsion.sum(axis=1) - attraction.sum(axis=1) - gravity * pos
        length = np.maximum(np.linalg.norm(displacement, axis=1), 1e-9)
        pos += displacement / length[:, None] * np.minimum(length, temperature)[:, None]
        temperature = max(temperature - cooling, 0.002)
    return pos


def force_layout(
    graph: CallGraph, seed: int = 0, iterations: int = 700, size: float | None = None
) -> dict[str, tuple[float, float]]:
    n = graph.n_classes
    if n == 0:
        return {}
    size = size if size is not None else 90.0 * math.sqrt(n)
    neighbours = graph.undirected_neighbors()
    connected = [c for c in graph.classes if neighbours[c]]
    isolated = [c for c in graph.classes if not neighbours[c]]

    positions: dict[str, tuple[float, float]] = {}
    bottom = 0.0
    if connected:
        index = {c: i for i, c in enumerate(connected)}
        weights = np.zeros((len(connected), len(connected)))
        for (a, b), calls in graph.calls.items():
            weights[index[a], index[b]] += calls
            weights[index[b], index[a]] += calls
        pos = _fruchterman_reingold(np.log1p(weights), seed, iterations)
        pos -= pos.min(axis=0)
        span = float(pos.max())
        if span > 0:
            pos *= size / span
        for c, i in index.items():
            positions[c] = (round(float(pos[i, 0]), 1), round(float(pos[i, 1]), 1))
        bottom = float(pos[:, 1].max())

    per_row = max(1, int(size // ISOLATED_SPACING) + 1)
    for i, c in enumerate(isolated):
        row, column = divmod(i, per_row)
        y = (bottom + ISOLATED_GAP if connected else 0.0) + row * ISOLATED_SPACING
        positions[c] = (round(column * ISOLATED_SPACING, 1), round(y, 1))
    return positions
