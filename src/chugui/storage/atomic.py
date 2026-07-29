"""원자적 JSON 저장.

구버전은 대상 파일을 직접 열어 덮어썼다::

    with open(AUTOSAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ...)

쓰는 도중 프로그램이 죽으면 세션 파일이 반쪽짜리로 남는다.
"갑자기 꺼져도 100% 복구"라는 기능의 존재 이유가 바로 그 순간 무너진다.

여기서는 같은 디렉터리에 임시 파일로 먼저 쓰고 ``os.replace`` 로 교체한다.
동일 볼륨에서 ``os.replace`` 는 원자적이므로 중간 상태가 관측되지 않는다.
직전 정상본은 ``.bak`` 으로 보존해 두고, 본 파일이 깨졌을 때 자동 복구한다.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def write_json_atomic(path: str | Path, data: Any, *, keep_backup: bool = True) -> bool:
    """JSON을 원자적으로 저장한다. 성공하면 ``True``."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2)
    except (OSError, TypeError, ValueError) as exc:
        logger.error("저장할 데이터를 직렬화하지 못했습니다 (%s): %s", target, exc)
        return False

    handle = None
    temp_path: Path | None = None
    try:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
        )
        temp_path = Path(temp_name)
        handle = os.fdopen(descriptor, "w", encoding="utf-8")
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        handle = None

        if keep_backup and target.exists():
            backup = target.with_suffix(target.suffix + ".bak")
            try:
                os.replace(target, backup)
            except OSError as exc:  # 백업 실패가 본 저장을 막아서는 안 된다
                logger.debug("백업 생성 실패 (%s): %s", backup, exc)

        os.replace(temp_path, target)
        temp_path = None
        return True
    except OSError as exc:
        logger.error("파일 저장 실패 (%s): %s", target, exc)
        return False
    finally:
        if handle is not None:
            with contextlib.suppress(OSError):
                handle.close()
        if temp_path is not None and temp_path.exists():
            with contextlib.suppress(OSError):
                temp_path.unlink()


def read_json(path: str | Path, default: Any = None) -> Any:
    """JSON을 읽는다. 본 파일이 깨졌으면 ``.bak`` 으로 자동 복구한다."""
    target = Path(path)
    for candidate in (target, target.with_suffix(target.suffix + ".bak")):
        if not candidate.is_file():
            continue
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if candidate != target:
                logger.warning("%s 가 손상되어 백업본에서 복구했습니다.", target.name)
            return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("JSON을 읽지 못했습니다 (%s): %s", candidate, exc)
            continue
    return default
