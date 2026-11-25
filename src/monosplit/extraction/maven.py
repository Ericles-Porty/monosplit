"""Apache Maven for applications without a Maven wrapper (build = "maven").

Installs Maven 3.9.16, the version pinned by JPetStore's wrapper, from Maven Central into a
per-user folder next to the JDK, and checks the SHA-256 that the wrapper publishes for that
file. Set MONOSPLIT_MAVEN_HOME to use another installation.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .jdk import install_root as jdk_root

MAVEN_VERSION = "3.9.16"
MAVEN_URL = (
    "https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/"
    f"{MAVEN_VERSION}/apache-maven-{MAVEN_VERSION}-bin.zip"
)
MAVEN_SHA256 = "5af3b743dd8b876b5c45da33b676251e5f1687712644abb4ee519ca56e1d89ce"
ENV_OVERRIDE = "MONOSPLIT_MAVEN_HOME"


def install_root() -> Path:
    return jdk_root().parent / "maven"


def _launcher(home: Path) -> Path:
    return home / "bin" / ("mvn.cmd" if sys.platform == "win32" else "mvn")


def find_maven() -> Path | None:
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        home = Path(override)
        if not _launcher(home).exists():
            raise RuntimeError(f"{ENV_OVERRIDE}={override} has no {_launcher(home).name}")
        return home
    home = install_root() / f"apache-maven-{MAVEN_VERSION}"
    return home if _launcher(home).exists() else None


def install_maven() -> Path:
    existing = find_maven()
    if existing:
        return existing
    root = install_root()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as tmp:
        archive = Path(tmp) / "maven.zip"
        digest = hashlib.sha256()
        request = urllib.request.Request(MAVEN_URL, headers={"User-Agent": "monosplit-maven-installer"})
        with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as out:
            while chunk := response.read(1 << 20):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != MAVEN_SHA256:
            raise RuntimeError("Checksum mismatch for the Maven download")
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(Path(tmp) / "unpacked")
        source = Path(tmp) / "unpacked" / f"apache-maven-{MAVEN_VERSION}"
        target = root / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(source), str(target))
    home = find_maven()
    if home is None:
        raise RuntimeError("Maven installation failed")
    return home


def maven_command(home: Path) -> list[str]:
    launcher = _launcher(home)
    return ["cmd", "/c", str(launcher)] if sys.platform == "win32" else [str(launcher)]
