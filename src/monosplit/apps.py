"""Fetch and build the pinned applications (experimental objects).

The applications are documents of the `apps` collection in the main database (see
store.py), each pinned to one commit; the Configuration page edits them.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .extraction.jdk import java_env, require_jdk
from .extraction.maven import install_maven, maven_command
from .paths import WORK_DIR

# maven-wrapper: the project's mvnw; maven: Maven installed by monosplit; gradle-wrapper: the
# project's gradlew (Gradle 8.5 or later runs on JDK 21).
BUILD_TYPES = ("maven-wrapper", "maven", "gradle-wrapper")


@dataclass(frozen=True)
class App:
    id: str
    name: str
    repository: str
    commit: str
    tag: str | None
    build: str
    build_args: tuple[str, ...]
    source_roots: tuple[str, ...]
    class_dirs: tuple[str, ...]
    note: str = ""

    @property
    def checkout(self) -> Path:
        return WORK_DIR / "apps" / self.id

    @property
    def build_log(self) -> Path:
        return WORK_DIR / "apps" / f"{self.id}-build.log"


def app_from_doc(doc: dict) -> App:
    return App(
        id=doc["id"],
        name=doc["name"],
        repository=doc["repository"],
        commit=doc["commit"],
        tag=doc.get("tag"),
        build=doc["build"],
        build_args=tuple(doc.get("build_args") or []),
        source_roots=tuple(doc["source_roots"]),
        class_dirs=tuple(doc["class_dirs"]),
        note=doc.get("note") or "",
    )


def load_apps() -> dict[str, App]:
    from .store import open_store

    return {doc["id"]: app_from_doc(doc) for doc in open_store().config_docs("apps")}


def get_app(app_id: str) -> App:
    apps = load_apps()
    if app_id not in apps:
        raise SystemExit(f"Unknown application '{app_id}'. Known: {', '.join(sorted(apps))}")
    return apps[app_id]


def _git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def head_commit(folder: Path) -> str:
    return _git("rev-parse", "HEAD", cwd=folder)


def fetch(app: App) -> Path:
    """Clone the repository (once) and check out the pinned commit."""
    if not (app.checkout / ".git").is_dir():
        app.checkout.parent.mkdir(parents=True, exist_ok=True)
        _git("clone", "--quiet", app.repository, str(app.checkout))
    _git("checkout", "--quiet", "--detach", app.commit, cwd=app.checkout)
    head = head_commit(app.checkout)
    if head != app.commit:
        raise RuntimeError(f"{app.id}: HEAD is {head}, expected {app.commit}")
    return app.checkout


def verify_checkout(app: App) -> str:
    """Fail unless the checkout exists, is at the pinned commit and has no local changes."""
    if not (app.checkout / ".git").is_dir():
        raise RuntimeError(f"{app.id}: not fetched. Run `uv run monosplit app fetch {app.id}`.")
    head = head_commit(app.checkout)
    if head != app.commit:
        raise RuntimeError(f"{app.id}: HEAD is {head}, expected {app.commit}")
    if _git("status", "--porcelain", "--untracked-files=no", cwd=app.checkout):
        raise RuntimeError(f"{app.id}: tracked files were modified in {app.checkout}")
    return head


def _wrapper(app: App, windows: str, unix: str) -> list[str]:
    # Absolute path: cmd.exe skips the current folder when NoDefaultCurrentDirectoryInExePath is set.
    if sys.platform == "win32":
        return ["cmd", "/c", str(app.checkout / windows)]
    return ["sh", str(app.checkout / unix)]


def build_command(app: App) -> list[str]:
    """The command that compiles `app`, with its build arguments."""
    if app.build == "maven-wrapper":
        command = _wrapper(app, "mvnw.cmd", "mvnw")
    elif app.build == "gradle-wrapper":
        command = _wrapper(app, "gradlew.bat", "gradlew")
    elif app.build == "maven":
        command = maven_command(install_maven())
    else:
        raise ValueError(f"{app.id}: unsupported build '{app.build}'")
    return command + list(app.build_args)


def build_env(app: App, jdk: Path) -> dict[str, str]:
    """The pinned JDK; Gradle keeps its distribution and caches in work/gradle, not in the
    user's home folder."""
    env = java_env(jdk)
    if app.build == "gradle-wrapper":
        env["GRADLE_USER_HOME"] = str(WORK_DIR / "gradle")
    return env


def build(app: App) -> Path:
    """Compile the application with the pinned JDK; return the build log path."""
    verify_checkout(app)
    jdk = require_jdk()
    command = build_command(app)
    with app.build_log.open("w", encoding="utf-8", errors="replace") as log:
        result = subprocess.run(
            command, cwd=app.checkout, env=build_env(app, jdk), stdout=log, stderr=subprocess.STDOUT, text=True
        )
    if result.returncode != 0:
        raise RuntimeError(f"{app.id}: build failed (exit {result.returncode}); see {app.build_log}")
    missing = [d for d in app.class_dirs if not (app.checkout / d).is_dir()]
    if missing:
        raise RuntimeError(f"{app.id}: build produced no {', '.join(missing)}")
    # A formatter plugin that rewrites sources would shift the line numbers used to
    # check edges against the pinned code.
    changed = _git("status", "--porcelain", "--untracked-files=no", cwd=app.checkout)
    if changed:
        raise RuntimeError(f"{app.id}: the build modified tracked files:\n{changed}")
    return app.build_log
