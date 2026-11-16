"""Which cell belongs to which part, and which parts hold which.

Shared by the layout solver, the checks and the renderer so they all agree on what
"connected" means: part B is held by part A when B's underside sits directly on at least
one of A's studs. Parts side by side in the same layer do not hold each other.
"""

from __future__ import annotations

import networkx as nx
import numpy as np

from bricksnap.catalog import Catalog
from bricksnap.types import Build


def occupancy(
    build: Build, catalog: Catalog
) -> tuple[np.ndarray, list[tuple[int, int]], list[int], list[int]]:
    """Map every cell to the part that covers it.

    Returns ``(occ, collisions, out_of_bounds, unknown)``:

    - ``occ``: int32 array of ``build.shape``, the index into ``build.parts`` of the part
      covering each cell, or -1 where the cell is empty.
    - ``collisions``: pairs ``(i, j)`` with ``i < j`` of parts that share at least one cell.
      Where two parts collide, ``occ`` keeps the lower index.
    - ``out_of_bounds``: indices of parts that stick out of the grid (they are not written
      into ``occ``).
    - ``unknown``: indices of parts whose part id or colour is not in the catalogue, or whose
      colour does not exist for that part (parts with an unknown id are not written into
      ``occ``; a known part in a wrong colour still is).
    """
    nx_, ny_, nz_ = build.shape
    occ = np.full(build.shape, -1, dtype=np.int32)
    collisions: set[tuple[int, int]] = set()
    out_of_bounds: list[int] = []
    unknown: list[int] = []
    for i, p in enumerate(build.parts):
        if p.part not in catalog.parts:
            unknown.append(i)
            continue
        if not catalog.exists(p.part, p.color):
            unknown.append(i)
        w, d, h = catalog.footprint(p)
        if p.x < 0 or p.y < 0 or p.z < 0 or p.x + w > nx_ or p.y + d > ny_ or p.z + h > nz_:
            out_of_bounds.append(i)
            continue
        region = occ[catalog.cells(p)]
        taken = region[region >= 0]
        for j in np.unique(taken):
            collisions.add((int(j), i))
        region[region < 0] = i
    return occ, sorted(collisions), out_of_bounds, unknown


def connection_graph(build: Build, catalog: Catalog, occ: np.ndarray | None = None) -> nx.Graph:
    """Graph of which parts hold which.

    Nodes are indices into ``build.parts`` (every part is a node, even if nothing touches it).
    An edge ``(a, b)`` means one sits directly on the other's studs; its ``studs`` attribute
    is how many studs are engaged. Pass ``occ`` from :func:`occupancy` to avoid recomputing it.
    """
    if occ is None:
        occ = occupancy(build, catalog)[0]
    nz_ = build.shape[2]
    g = nx.Graph()
    g.add_nodes_from(range(len(build.parts)))
    for i, p in enumerate(build.parts):
        part = catalog.parts.get(p.part)
        if part is None:
            continue
        top = p.z + part.h
        if top >= nz_:
            continue
        counts: dict[int, int] = {}
        for x, y in catalog.stud_cells(p):
            if not (0 <= x < occ.shape[0] and 0 <= y < occ.shape[1]):
                continue
            j = int(occ[x, y, top])
            if j < 0 or j == i:
                continue
            above = build.parts[j]
            above_part = catalog.parts.get(above.part)
            # the part above must start exactly on this layer and accept studs underneath
            if above_part is None or above.z != top or not above_part.antistuds_bottom:
                continue
            counts[j] = counts.get(j, 0) + 1
        for j, n in counts.items():
            g.add_edge(i, j, studs=n)
    return g
