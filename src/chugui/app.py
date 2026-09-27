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


def _install_korean_qt_texts(app) -> None:
    """Qt 기본 문구(Yes/No, Cancel 등)를 한국어로 바꾼다.

    확인 창의 버튼이 'Yes / No' 로 떠서, 전체 비우기 같은 중요한 질문에
    영어 버튼을 눌러야 했다.
    """
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    translator = QTranslator(app)
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(QLocale(QLocale.Language.Korean), "qtbase", "_", folder):
        app.installTranslator(translator)
    else:
        logger.warning("Qt 한국어 번역을 찾지 못했습니다: %s", folder)


def acquire_single_instance():
    """두 번째 실행을 막는 잠금. 이미 실행 중이면 ``None``.

    창이 둘이면 둘 다 같은 세션 파일에 자동 저장해 한쪽 작업이 조용히 사라지고,
    두 번째 창은 첫 번째 창의 실행 표식을 보고 '비정상 종료' 라고 잘못 알린다.
    QLockFile 은 잠금을 쥔 프로세스가 죽으면 그 잠금을 낡은 것으로 보고 넘겨준다.
    그래서 강제 종료 뒤에는 정상적으로 다시 켜진다.

    반환된 객체를 프로세스가 끝날 때까지 들고 있어야 잠금이 유지된다.
    """
    from PySide6.QtCore import QLockFile

    lock = QLockFile(str(data_dir() / "instance.lock"))
    lock.setStaleLockTime(0)  # 시간이 아니라 PID 생존 여부로만 낡음을 판단한다
    return lock if lock.tryLock(200) else None


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
    _install_korean_qt_texts(app)

    def _report(kind: str, message: str) -> None:
        QMessageBox.critical(
            None,
            "오류가 발생했습니다",
            f"{kind}: {message}\n\n작업 내용은 자동 저장되어 있습니다.\n"
            f"자세한 내용은 로그를 확인해 주세요:\n{data_dir() / 'logs'}",
        )

    install_excepthook(_report)

    instance_lock = acquire_single_instance()
    if instance_lock is None:
        QMessageBox.information(
            None,
            "이미 실행 중입니다",
            "ChuguiMaster가 이미 열려 있습니다. 작업 표시줄에서 기존 창을 사용해 주세요.\n\n"
            "창을 두 개 띄우면 서로의 자동 저장을 덮어써 작업이 사라질 수 있습니다.",
        )
        return 0

    window = MainWindow()
    window.show_initial()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
