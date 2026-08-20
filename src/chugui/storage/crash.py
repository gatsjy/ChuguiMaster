"""비정상 종료 감지.

앱은 자기가 지난번에 어떻게 끝났는지 모른다. 정상 종료와 강제 종료를 구분하지
못하면 "지난번에 갑자기 꺼졌습니다. 작업은 복구했습니다" 같은 안내를 할 수 없다.
사용자는 자기 작업이 살아 있는지 모른 채 불안해한다.

방법은 단순하다. 기동할 때 표식 파일을 만들고 정상 종료할 때 지운다.
다음 기동에 파일이 남아 있으면 지난번이 비정상 종료였다는 뜻이다.

주의: 이 표식만으로 '지금 다른 인스턴스가 실행 중'인지는 알 수 없다.
여기서 하려는 일은 잠금이 아니라 사후 감지이므로 그 구분은 필요 없다.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chugui.storage.atomic import read_json, write_json_atomic
from chugui.storage.paths import data_dir

logger = logging.getLogger(__name__)

SENTINEL_FILENAME = "running.lock"


@dataclass(frozen=True)
class CrashReport:
    """지난 실행이 어떻게 끝났는지."""

    crashed: bool
    last_started_at: datetime | None = None

    @property
    def message(self) -> str:
        if not self.crashed:
            return ""
        if self.last_started_at is None:
            return "지난번에 프로그램이 정상적으로 종료되지 않았습니다."
        return (
            f"지난번({self.last_started_at:%m월 %d일 %H:%M} 시작)에 "
            "프로그램이 정상적으로 종료되지 않았습니다."
        )


class CrashSentinel:
    """실행 중 표식 파일."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or (data_dir() / SENTINEL_FILENAME)

    def arm(self) -> CrashReport:
        """표식을 세우고, 지난 실행의 결말을 돌려준다.

        기동 시 **한 번만** 부른다.
        """
        report = self._inspect()
        write_json_atomic(
            self.path,
            {"pid": os.getpid(), "started_at": datetime.now().isoformat(timespec="seconds")},
            keep_backup=False,
        )
        if report.crashed:
            logger.warning("지난 실행이 비정상 종료되었습니다.")
        return report

    def disarm(self) -> None:
        """정상 종료 시 표식을 지운다."""
        for candidate in (self.path, self.path.with_suffix(self.path.suffix + ".bak")):
            try:
                candidate.unlink(missing_ok=True)
            except OSError as exc:  # pragma: no cover
                logger.warning("표식 파일 삭제 실패 (%s): %s", candidate, exc)

    def _inspect(self) -> CrashReport:
        if not self.path.is_file():
            return CrashReport(crashed=False)

        data = read_json(self.path, default=None)
        started_at: datetime | None = None
        if isinstance(data, dict):
            raw = data.get("started_at")
            if isinstance(raw, str):
                try:
                    started_at = datetime.fromisoformat(raw)
                except ValueError:
                    started_at = None
        return CrashReport(crashed=True, last_started_at=started_at)
