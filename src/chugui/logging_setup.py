"""로깅 설정.

구버전은 ``print()`` 와 ``except Exception: pass`` 뿐이었다.
``--windowed`` 로 빌드한 exe에는 콘솔이 없어서 ``print``는 그대로 허공으로 사라진다.
사용자 PC에서 무슨 일이 있었는지 알 방법이 없었다.

여기서는 회전 파일 핸들러로 사용자 데이터 디렉터리에 로그를 남긴다.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from collections.abc import Callable
from types import TracebackType

from chugui.storage.paths import log_file

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 3


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """루트 로거를 구성한다. 중복 호출해도 핸들러가 늘어나지 않는다."""
    root = logging.getLogger()
    root.setLevel(level)

    if any(getattr(handler, "_chugui", False) for handler in root.handlers):
        return root

    formatter = logging.Formatter(_LOG_FORMAT)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file(), maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler._chugui = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)
    except OSError as exc:  # pragma: no cover - 권한 문제
        print(f"[ChuguiMaster] 로그 파일을 열 수 없습니다: {exc}", file=sys.stderr)

    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        stream_handler._chugui = True  # type: ignore[attr-defined]
        root.addHandler(stream_handler)

    return root


def install_excepthook(on_error: Callable[[str, str], None] | None = None) -> None:
    """처리되지 않은 예외를 로그에 남기고 선택적으로 UI에 알린다."""
    logger = logging.getLogger("chugui.excepthook")
    previous = sys.excepthook

    def _hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc_value, exc_tb)
            return
        logger.critical("처리되지 않은 예외", exc_info=(exc_type, exc_value, exc_tb))
        if on_error is not None:
            try:
                on_error(exc_type.__name__, str(exc_value))
            except Exception:  # pragma: no cover - 알림 실패는 무시
                logger.exception("오류 알림 표시에 실패했습니다.")

    sys.excepthook = _hook
