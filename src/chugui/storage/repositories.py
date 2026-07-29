"""설정 / 세션 / 템플릿 저장소.

모든 로딩 경로는 **관용적**이다. 파일이 없거나, 깨졌거나, 키가 빠졌거나,
구버전 스키마여도 예외를 던지지 않고 유효한 기본값을 돌려준다.
구버전은 부분 레코드 하나(``{"id":1,"name":"테스트"}``)가 세션 파일에 들어 있으면
기동 직후 ``KeyError: 'relation'`` 으로 죽었다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chugui.models import SCHEMA_VERSION, Guest
from chugui.services.messages import Templates, default_templates, normalize_templates
from chugui.services.settlement import DEFAULT_ADULT_MEAL, DEFAULT_CHILD_MEAL
from chugui.storage.atomic import read_json, write_json_atomic
from chugui.storage.paths import config_file, session_file, templates_file

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """앱 전역 설정."""

    adult_meal: int = DEFAULT_ADULT_MEAL
    child_meal: int = DEFAULT_CHILD_MEAL
    dark_mode: bool = True
    window_width: int = 1360
    window_height: int = 880

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "adult_meal": self.adult_meal,
            "child_meal": self.child_meal,
            "dark_mode": self.dark_mode,
            "window_width": self.window_width,
            "window_height": self.window_height,
        }

    @classmethod
    def from_dict(cls, data: Any) -> AppConfig:
        config = cls()
        if not isinstance(data, dict):
            return config

        def _int(key: str, current: int, minimum: int, maximum: int) -> int:
            try:
                return max(minimum, min(maximum, int(data.get(key, current))))
            except (TypeError, ValueError):
                return current

        config.adult_meal = _int("adult_meal", config.adult_meal, 0, 1_000_000)
        config.child_meal = _int("child_meal", config.child_meal, 0, 1_000_000)
        config.window_width = _int("window_width", config.window_width, 900, 6000)
        config.window_height = _int("window_height", config.window_height, 600, 4000)
        config.dark_mode = bool(data.get("dark_mode", config.dark_mode))
        return config


@dataclass
class SessionState:
    """자동 저장되는 작업 세션."""

    guests: list[Guest]
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "raw_text": self.raw_text,
            "guests": [guest.to_dict() for guest in self.guests],
        }

    @classmethod
    def from_dict(cls, data: Any) -> SessionState:
        if not isinstance(data, dict):
            return cls(guests=[], raw_text="")
        # v1은 키 이름이 guest_data 였다.
        raw_guests = data.get("guests")
        if raw_guests is None:
            raw_guests = data.get("guest_data", [])
        guests = [Guest.from_dict(item) for item in raw_guests] if isinstance(raw_guests, list) else []
        return cls(guests=guests, raw_text=str(data.get("raw_text") or ""))


class ConfigRepository:
    """설정 파일 읽기/쓰기."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or config_file()

    def load(self) -> AppConfig:
        return AppConfig.from_dict(read_json(self.path, default={}))

    def save(self, config: AppConfig) -> bool:
        return write_json_atomic(self.path, config.to_dict())


class SessionRepository:
    """작업 세션 자동 저장/복구."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or session_file()

    def load(self) -> SessionState:
        state = SessionState.from_dict(read_json(self.path, default={}))
        if state.guests:
            logger.info("이전 세션 복구: %d건", len(state.guests))
        return state

    def save(self, state: SessionState) -> bool:
        return write_json_atomic(self.path, state.to_dict())

    def clear(self) -> None:
        for candidate in (self.path, self.path.with_suffix(self.path.suffix + ".bak")):
            try:
                candidate.unlink(missing_ok=True)
            except OSError as exc:  # pragma: no cover
                logger.warning("세션 파일 삭제 실패 (%s): %s", candidate, exc)


class TemplateRepository:
    """감사 인사말 템플릿 저장소."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or templates_file()

    def load(self) -> Templates:
        data = read_json(self.path, default=None)
        return default_templates() if data is None else normalize_templates(data)

    def save(self, templates: Templates) -> bool:
        return write_json_atomic(self.path, normalize_templates(templates))

    def reset(self) -> Templates:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover
            logger.warning("템플릿 파일 삭제 실패: %s", exc)
        return default_templates()
