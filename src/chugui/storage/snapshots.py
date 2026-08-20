"""작업 스냅샷 보관소.

자동 저장(``session.json``)은 **크래시**를 막아 준다. 하지만 **사람의 실수**는
막아 주지 못한다. `전체 비우기` 를 잘못 누르거나 파싱으로 기존 목록을 덮어쓰면
자동 저장은 그 결과를 성실하게 저장할 뿐이다. ``.bak`` 도 직전 저장본이라
디바운스 600ms 기준으로 사실상 같은 내용이다.

그래서 되돌릴 지점을 따로 남긴다.

* **파괴 연산 직전** — 비우기 / 덮어쓰기 / 병합 전에 자동 기록
* **주기적** — 일정 간격마다 자동 기록
* 링 버퍼로 최대 :data:`MAX_SNAPSHOTS` 개 유지, 오래된 것부터 삭제

파일 하나가 곧 한 시점이므로 복원은 그냥 그 파일을 읽으면 된다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chugui.storage.atomic import read_json, write_json_atomic
from chugui.storage.paths import data_dir

logger = logging.getLogger(__name__)

#: 보관할 최대 스냅샷 수. 넘으면 오래된 것부터 지운다.
MAX_SNAPSHOTS = 20

_STAMP_FORMAT = "%Y%m%d-%H%M%S"
_FILENAME_RE = re.compile(r"^(?P<stamp>\d{8}-\d{6})-(?P<reason>.+)\.json$")
_UNSAFE_CHARS_RE = re.compile(r"[^0-9A-Za-z가-힣_-]+")


def snapshots_dir() -> Path:
    directory = data_dir() / "snapshots"
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - 권한 문제
        logger.error("스냅샷 디렉터리를 만들 수 없습니다 (%s): %s", directory, exc)
    return directory


@dataclass(frozen=True)
class SnapshotInfo:
    """복원 목록에 보여 줄 한 줄."""

    path: Path
    taken_at: datetime
    reason: str
    guest_count: int
    total_amount: int

    @property
    def label(self) -> str:
        return f"{self.taken_at:%m/%d %H:%M:%S}  ·  {self.reason}"

    @property
    def detail(self) -> str:
        return f"{self.guest_count}건 · {self.total_amount:,}원"


def _slugify(reason: str) -> str:
    slug = _UNSAFE_CHARS_RE.sub("_", str(reason or "자동")).strip("_")
    return slug[:40] or "자동"


class SnapshotStore:
    """스냅샷 링 버퍼."""

    def __init__(self, directory: Path | None = None, limit: int = MAX_SNAPSHOTS) -> None:
        self._directory = directory
        self._limit = max(1, limit)

    @property
    def directory(self) -> Path:
        return self._directory or snapshots_dir()

    # ------------------------------------------------------------- 기록

    def capture(self, payload: dict, reason: str) -> Path | None:
        """현재 상태를 한 시점으로 남긴다.

        하객이 하나도 없으면 되돌릴 가치가 없으므로 건너뛴다.
        """
        guests = payload.get("guests") if isinstance(payload, dict) else None
        if not guests:
            return None

        stamp = datetime.now().strftime(_STAMP_FORMAT)
        path = self.directory / f"{stamp}-{_slugify(reason)}.json"

        # 같은 초에 두 번 찍히면 뒤엣것이 앞엣것을 덮지 않도록 이름을 비운다.
        counter = 1
        while path.exists():
            path = self.directory / f"{stamp}-{_slugify(reason)}_{counter}.json"
            counter += 1

        record = dict(payload)
        record["snapshot_reason"] = reason
        record["snapshot_taken_at"] = datetime.now().isoformat(timespec="seconds")

        # 스냅샷은 세대마다 파일이 따로 있으므로 .bak 을 또 만들 필요가 없다.
        if not write_json_atomic(path, record, keep_backup=False):
            return None

        logger.info("스냅샷 기록: %s (%d건)", path.name, len(guests))
        self.prune()
        return path

    def prune(self) -> int:
        """개수 제한을 넘은 오래된 스냅샷을 지운다. 지운 개수를 돌려준다."""
        files = sorted(self.directory.glob("*.json"))
        excess = len(files) - self._limit
        removed = 0
        for path in files[:max(0, excess)]:
            try:
                path.unlink()
                removed += 1
            except OSError as exc:  # pragma: no cover
                logger.warning("오래된 스냅샷 삭제 실패 (%s): %s", path, exc)
        return removed

    # ------------------------------------------------------------- 조회

    def list_snapshots(self) -> list[SnapshotInfo]:
        """최근 것이 앞에 오도록 정렬된 스냅샷 목록."""
        infos: list[SnapshotInfo] = []
        for path in sorted(self.directory.glob("*.json"), reverse=True):
            info = self._describe(path)
            if info is not None:
                infos.append(info)
        return infos

    def _describe(self, path: Path) -> SnapshotInfo | None:
        data = read_json(path, default=None)
        if not isinstance(data, dict):
            return None
        guests = data.get("guests")
        if not isinstance(guests, list):
            return None

        match = _FILENAME_RE.match(path.name)
        try:
            taken_at = (
                datetime.strptime(match.group("stamp"), _STAMP_FORMAT)
                if match
                else datetime.fromtimestamp(path.stat().st_mtime)
            )
        except (ValueError, OSError):  # pragma: no cover
            taken_at = datetime.fromtimestamp(0)

        reason = str(data.get("snapshot_reason") or "")
        if not reason and match:
            reason = match.group("reason").replace("_", " ")

        total = 0
        for guest in guests:
            if isinstance(guest, dict):
                try:
                    total += int(guest.get("amount") or 0)
                except (TypeError, ValueError):
                    continue

        return SnapshotInfo(
            path=path,
            taken_at=taken_at,
            reason=reason or "자동",
            guest_count=len(guests),
            total_amount=total,
        )

    def load(self, path: Path) -> dict | None:
        data = read_json(path, default=None)
        return data if isinstance(data, dict) else None

    def clear(self) -> None:
        for path in self.directory.glob("*.json"):
            try:
                path.unlink()
            except OSError as exc:  # pragma: no cover
                logger.warning("스냅샷 삭제 실패 (%s): %s", path, exc)
