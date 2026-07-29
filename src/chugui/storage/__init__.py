"""영속화 계층 - 경로 결정, 원자적 쓰기, 저장소."""

from chugui.storage.atomic import read_json, write_json_atomic
from chugui.storage.paths import (
    config_file,
    data_dir,
    log_file,
    migrate_legacy_files,
    session_file,
    templates_file,
)
from chugui.storage.repositories import ConfigRepository, SessionRepository, TemplateRepository

__all__ = [
    "ConfigRepository",
    "SessionRepository",
    "TemplateRepository",
    "config_file",
    "data_dir",
    "log_file",
    "migrate_legacy_files",
    "read_json",
    "session_file",
    "templates_file",
    "write_json_atomic",
]
