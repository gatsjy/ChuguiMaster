"""사용자 데이터 경로 결정.

구버전은 ``CONFIG_FILE = "config_settings.json"`` 처럼 **상대 경로**를 썼다.
``--onefile --windowed`` 로 만든 exe는 실행 위치가 매번 달라서 설정과 세션이
여기저기 흩어졌고, ``Program Files`` 에 두면 쓰기 자체가 실패했다.
그런데 저장 함수가 ``except Exception: pass`` 라 사용자는 영문도 몰랐다.

여기서는 OS 표준 사용자 데이터 디렉터리를 쓴다. Qt에 의존하지 않으므로
테스트에서 ``CHUGUI_DATA_DIR`` 환경 변수만 바꾸면 완전히 격리된다.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

APP_DIR_NAME = "ChuguiMaster"
ENV_OVERRIDE = "CHUGUI_DATA_DIR"

CONFIG_FILENAME = "config.json"
SESSION_FILENAME = "session.json"
TEMPLATES_FILENAME = "templates.json"
LOG_FILENAME = "chugui.log"

# v1이 실행 디렉터리에 남긴 파일들 -> 새 파일명 매핑
_LEGACY_FILES: dict[str, str] = {
    "config_settings.json": CONFIG_FILENAME,
    "autosave_session.json": SESSION_FILENAME,
    "template_settings.json": TEMPLATES_FILENAME,
}


def _platform_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_DIR_NAME
        return Path.home() / "AppData" / "Local" / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_DIR_NAME


def data_dir() -> Path:
    """사용자 데이터 디렉터리. 없으면 만든다."""
    override = os.environ.get(ENV_OVERRIDE)
    directory = Path(override).expanduser() if override else _platform_data_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - 권한 문제 등
        logger.error("데이터 디렉터리를 만들 수 없습니다 (%s): %s", directory, exc)
    return directory


def config_file() -> Path:
    return data_dir() / CONFIG_FILENAME


def session_file() -> Path:
    return data_dir() / SESSION_FILENAME


def templates_file() -> Path:
    return data_dir() / TEMPLATES_FILENAME


def log_file() -> Path:
    log_dir = data_dir() / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:  # pragma: no cover
        return data_dir() / LOG_FILENAME
    return log_dir / LOG_FILENAME


def migrate_legacy_files(source_dir: Path | None = None) -> list[str]:
    """v1이 실행 디렉터리에 남긴 설정/세션을 새 위치로 한 번만 옮긴다.

    기존 사용자가 업그레이드해도 작업 내용을 잃지 않게 하기 위한 장치다.
    이미 새 파일이 있으면 건드리지 않는다.
    """
    origin = source_dir or Path.cwd()
    target = data_dir()
    moved: list[str] = []

    for legacy_name, new_name in _LEGACY_FILES.items():
        legacy_path = origin / legacy_name
        new_path = target / new_name
        if not legacy_path.is_file() or new_path.exists():
            continue
        try:
            shutil.copy2(legacy_path, new_path)
            moved.append(legacy_name)
            logger.info("구버전 파일 이전: %s -> %s", legacy_path, new_path)
        except OSError as exc:
            logger.warning("구버전 파일 이전 실패 (%s): %s", legacy_path, exc)

    return moved
