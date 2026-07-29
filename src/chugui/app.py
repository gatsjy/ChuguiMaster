"""애플리케이션 부트스트랩."""

from __future__ import annotations

import logging
import sys

from chugui import __app_name__, __version__
from chugui.logging_setup import install_excepthook, setup_logging
from chugui.storage.paths import data_dir, migrate_legacy_files

logger = logging.getLogger(__name__)


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
