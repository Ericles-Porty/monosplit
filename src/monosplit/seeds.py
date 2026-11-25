"""Seeds derived from the experiment's master seed.

Each random step gets its own seed, computed from the master seed and the step's
identity (application, variant, run). The derived seed is written next to the result,
so any single partition can be regenerated without rerunning the others.
"""

from __future__ import annotations

import hashlib


def derive_seed(master: int, *parts: object) -> int:
    text = "/".join(str(p) for p in (master, *parts))
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big") >> 1
