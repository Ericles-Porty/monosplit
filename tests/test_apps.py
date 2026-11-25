"""Build commands of the applications (nothing is cloned or compiled here)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import monosplit.apps as apps_module
from monosplit.apps import App, build_command, build_env


def app(build: str, args: tuple[str, ...] = ("compile",)) -> App:
    return App(id="shop", name="Shop", repository="https://example.org/shop.git", commit="a" * 40, tag=None,
               build=build, build_args=args, source_roots=("src",), class_dirs=("classes",))


@pytest.mark.parametrize("build, windows, unix", [("maven-wrapper", "mvnw.cmd", "mvnw"), ("gradle-wrapper", "gradlew.bat", "gradlew")])
def test_wrappers_run_from_the_checkout(build, windows, unix):
    command = build_command(app(build, ("--no-daemon", "classes")))
    script = windows if sys.platform == "win32" else unix
    assert command[-3] == str(app(build).checkout / script)
    assert command[-2:] == ["--no-daemon", "classes"]


def test_gradle_keeps_its_files_in_work(tmp_path, monkeypatch):
    monkeypatch.setattr(apps_module, "WORK_DIR", tmp_path)
    jdk = Path("jdk-21")
    assert build_env(app("gradle-wrapper"), jdk)["GRADLE_USER_HOME"] == str(tmp_path / "gradle")
    assert build_env(app("gradle-wrapper"), jdk)["JAVA_HOME"] == str(jdk)
    assert "GRADLE_USER_HOME" not in build_env(app("maven-wrapper"), jdk) or build_env(app("maven-wrapper"), jdk)[
        "GRADLE_USER_HOME"] != str(tmp_path / "gradle")


def test_unknown_build_is_refused():
    with pytest.raises(ValueError, match="unsupported build"):
        build_command(app("ant"))
