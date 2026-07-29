"""Qt widget.grab() 기반 가상 데이터 UI 스크린샷 자동 캡처 서비스 모듈."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest

if TYPE_CHECKING:
    from chugui.ui.main_window import MainWindow

ANONYMOUS_SAMPLE_DATA = """홍길동\t200,000\t친척
김철수\t100,000\t친구
이영희\t300,000\t직장
박민수\t150,000\t교회
최동욱\t500,000\t친척"""


def capture_clean_screenshots(window: MainWindow, save_dir: Path | str) -> list[Path]:
    """실제 사용자 개인정보 노출 없이 가상 샘플 데이터로 UI 스크린샷을 자동 캡처하여 저장한다."""
    from chugui.parsing.text_parser import parse_text

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    # 1. 기존 명단 백업
    original_guests = list(window._model.guests)

    try:
        # 2. 익명 가상 데이터 주입
        sample_guests = parse_text(ANONYMOUS_SAMPLE_DATA)
        window._model.set_guests(sample_guests)
        window._on_guests_changed()
        QTest.qWait(300)

        captured_files: list[Path] = []

        # 3. 메인 대시보드 캡처
        dashboard_pixmap = window.grab()
        dash_file = save_path / "anonymous_dashboard.png"
        dashboard_pixmap.save(str(dash_file))
        captured_files.append(dash_file)

        # 4. 하객 테이블 캡처
        if hasattr(window, "_table"):
            table_pixmap = window._table.grab()
            table_file = save_path / "anonymous_table.png"
            table_pixmap.save(str(table_file))
            captured_files.append(table_file)

        return captured_files

    finally:
        # 5. 기존 사용자 데이터 100% 안전하게 원복
        window._model.set_guests(original_guests)
        window._on_guests_changed()
