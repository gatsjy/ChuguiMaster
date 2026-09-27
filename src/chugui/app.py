"""애플리케이션 부트스트랩."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from chugui import __app_name__, __version__
from chugui.logging_setup import install_excepthook, setup_logging
from chugui.storage.paths import data_dir, migrate_legacy_files

logger = logging.getLogger(__name__)


def _register_bundled_fonts() -> None:
    """``assets/fonts`` 의 폰트(레트로 테마 픽셀 폰트)를 등록한다. 없으면 조용히 넘어간다."""
    from PySide6.QtGui import QFontDatabase

    # PyInstaller 산출물은 _MEIPASS 아래에, 소스 실행은 src/ 아래에 같은 구조로 있다.
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    for font in sorted((base / "chugui" / "assets" / "fonts").glob("*.[ot]tf")):
        if QFontDatabase.addApplicationFont(str(font)) < 0:
            logger.warning("폰트 등록 실패: %s", font.name)


def run() -> int:
    """ChuguiMaster를 실행한다."""
    setup_logging()
    logger.info("%s %s 시작", __app_name__, __version__)
    logger.info("데이터 디렉터리: %s", data_dir())

    moved = migrate_legacy_files()
    if moved:
        logger.info("구버전 파일을 이전했습니다: %s", ", ".join(moved))

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from chugui.ui.main_window import MainWindow

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(__app_name__)
    _register_bundled_fonts()

    def _report(kind: str, message: str) -> None:
        QMessageBox.critical(
            None,
            "오류가 발생했습니다",
            f"{kind}: {message}\n\n작업 내용은 자동 저장되어 있습니다.\n"
            f"자세한 내용은 로그를 확인해 주세요:\n{data_dir() / 'logs'}",
        )

    install_excepthook(_report)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
