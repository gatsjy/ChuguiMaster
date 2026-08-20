"""사용자에게 보이는 버전과 패키지 메타데이터의 일치 검증."""

from __future__ import annotations

import re
from pathlib import Path

from chugui import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_package_metadata_matches_runtime_version():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert match is not None
    assert match.group(1) == __version__


def test_readme_and_changelog_show_runtime_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"v{__version__}" in readme.splitlines()[0]
    assert f"[{__version__}]" in changelog
