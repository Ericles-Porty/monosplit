"""Locate or install the JDK used to build the applications and run javap.

The study pins one JDK: Eclipse Temurin, feature release 21. `install_jdk` downloads
the latest 21.x build from the Adoptium API into a per-user folder and checks its
SHA-256 checksum. It never changes JAVA_HOME or PATH: the commands of this package
receive the JDK through their own environment. Set MONOSPLIT_JAVA_HOME to use a JDK
installed elsewhere.

Default install folder:
    Windows: %LOCALAPPDATA%\\monosplit\\jdk
    macOS:   ~/Library/Application Support/monosplit/jdk
    Linux:   $XDG_DATA_HOME/monosplit/jdk (default ~/.local/share/monosplit/jdk)
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

JDK_FEATURE = 21
ENV_OVERRIDE = "MONOSPLIT_JAVA_HOME"
_ASSETS_URL = (
    "https://api.adoptium.net/v3/assets/latest/{feature}/hotspot"
    "?architecture={arch}&image_type=jdk&os={os}&vendor=eclipse"
)
_USER_AGENT = "monosplit-jdk-installer"


def install_root() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "monosplit" / "jdk"


def _exe(name: str) -> str:
    return name + (".exe" if sys.platform == "win32" else "")


def _home_of(folder: Path) -> Path:
    """macOS archives keep the JDK under Contents/Home."""
    mac_home = folder / "Contents" / "Home"
    return mac_home if mac_home.is_dir() else folder


def is_jdk(home: Path) -> bool:
    return (home / "bin" / _exe("javap")).is_file() and (home / "bin" / _exe("javac")).is_file()


def find_jdk() -> Path | None:
    """Return the JDK home to use, or None if no JDK is installed."""
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        home = Path(override)
        if not is_jdk(home):
            raise RuntimeError(f"{ENV_OVERRIDE}={override} is not a JDK: bin/javap or bin/javac is missing")
        return home
    root = install_root()
    if not root.is_dir():
        return None
    folders = [
        p for p in root.iterdir()
        if p.is_dir() and p.name.startswith(f"jdk-{JDK_FEATURE}") and is_jdk(_home_of(p))
    ]
    if not folders:
        return None
    # Newest build first: jdk-21.0.10+7 sorts after jdk-21.0.9+10.
    newest = max(folders, key=lambda p: [int(n) for n in re.findall(r"\d+", p.name)])
    return _home_of(newest)


def require_jdk() -> Path:
    home = find_jdk()
    if home is None:
        raise RuntimeError("No JDK found. Run `uv run monosplit jdk install` or set MONOSPLIT_JAVA_HOME.")
    return home


def java_env(home: Path) -> dict[str, str]:
    """Environment for subprocesses that need the pinned JDK."""
    env = dict(os.environ)
    env["JAVA_HOME"] = str(home)
    env["PATH"] = str(home / "bin") + os.pathsep + env.get("PATH", "")
    return env


def jdk_version(home: Path) -> str:
    """First line of `java -version`, e.g. 'openjdk version "21.0.9" 2025-10-21 LTS'."""
    result = subprocess.run(
        [str(home / "bin" / _exe("java")), "-version"], capture_output=True, text=True, check=True
    )
    lines = (result.stderr or result.stdout).strip().splitlines()
    return " | ".join(line.strip() for line in lines)


def _platform() -> tuple[str, str]:
    os_name = {"win32": "windows", "darwin": "mac"}.get(sys.platform, "linux")
    machine = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "aarch64", "aarch64": "aarch64"}.get(machine)
    if arch is None:
        raise RuntimeError(f"Unsupported architecture for the JDK download: {machine}")
    return os_name, arch


def _get(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return urllib.request.urlopen(request, timeout=120)


def install_jdk(feature: int = JDK_FEATURE, force: bool = False) -> Path:
    """Download and unpack the latest Temurin JDK of `feature`; return its home."""
    os_name, arch = _platform()
    with _get(_ASSETS_URL.format(feature=feature, arch=arch, os=os_name)) as response:
        assets = json.load(response)
    if not assets:
        raise RuntimeError(f"Adoptium API returned no JDK {feature} build for {os_name}/{arch}")
    asset = assets[0]
    package = asset["binary"]["package"]
    release = asset["release_name"]  # e.g. jdk-21.0.9+10

    root = install_root()
    target = root / release
    if is_jdk(_home_of(target)) and not force:
        return _home_of(target)

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as tmp:
        archive = Path(tmp) / package["name"]
        digest = hashlib.sha256()
        with _get(package["link"]) as response, archive.open("wb") as out:
            while chunk := response.read(1 << 20):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != package["checksum"]:
            raise RuntimeError(f"Checksum mismatch for {package['name']}")

        unpacked = Path(tmp) / "unpacked"
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(unpacked)
        else:
            with tarfile.open(archive) as tf:
                tf.extractall(unpacked, filter="data")
        tops = [p for p in unpacked.iterdir() if p.is_dir()]
        if len(tops) != 1:
            raise RuntimeError(f"Unexpected archive layout in {package['name']}")
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(tops[0]), str(target))

    home = _home_of(target)
    if not is_jdk(home):
        raise RuntimeError(f"Installed folder {target} does not look like a JDK")
    return home
