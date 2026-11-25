"""Folders of the experiment package, relative to the `experimento/` root."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = ROOT / "work"
WEB_DIR = ROOT / "web"
WEB_DIST = WEB_DIR / "dist"


def resolve(path: str | Path) -> Path:
    """Return `path` unchanged if absolute, otherwise relative to the package root."""
    path = Path(path)
    return path if path.is_absolute() else ROOT / path
