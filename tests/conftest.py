"""테스트 공통 설정."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """모든 테스트가 자기만의 데이터 디렉터리를 쓰도록 격리한다.

    구버전은 설정/세션 경로가 CWD 고정이라 테스트가 실제 사용자 파일을 덮어썼다.
    """
    monkeypatch.setenv("CHUGUI_DATA_DIR", str(tmp_path / "data"))
    yield tmp_path


@pytest.fixture
def qt_app():
    """GUI 테스트용 QApplication (오프스크린)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
