"""screenshot.py 자동 캡처 서비스 단위 테스트."""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
import pytest

from chugui.services.screenshot import capture_clean_screenshots
from chugui.ui.main_window import MainWindow

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_capture_clean_screenshots(qapp, tmp_path):
    window = MainWindow()
    window.show()

    captured = capture_clean_screenshots(window, tmp_path)
    assert len(captured) >= 1
    for f in captured:
        assert f.exists()
        assert f.stat().st_size > 0

    window.close()
