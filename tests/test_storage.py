"""저장소 · 원자적 쓰기 · 스키마 관용성 테스트."""

from __future__ import annotations

import json

import pytest

from chugui.models import Attendance, Guest, Payment, Relation
from chugui.storage.atomic import read_json, write_json_atomic
from chugui.storage.paths import config_file, data_dir, migrate_legacy_files, session_file
from chugui.storage.repositories import (
    AppConfig,
    ConfigRepository,
    SessionRepository,
    SessionState,
    TemplateRepository,
)


class TestAtomicWrite:
    def test_round_trip(self, tmp_path):
        target = tmp_path / "a.json"
        assert write_json_atomic(target, {"값": 1}) is True
        assert read_json(target) == {"값": 1}

    def test_no_temp_files_left_behind(self, tmp_path):
        target = tmp_path / "a.json"
        write_json_atomic(target, {"a": 1})
        write_json_atomic(target, {"a": 2})
        leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"]
        assert leftovers == []

    def test_previous_version_is_kept_as_backup(self, tmp_path):
        target = tmp_path / "a.json"
        write_json_atomic(target, {"세대": 1})
        write_json_atomic(target, {"세대": 2})
        assert read_json(target) == {"세대": 2}
        assert read_json(target.with_suffix(".json.bak")) == {"세대": 1}

    def test_corrupted_file_recovers_from_backup(self, tmp_path):
        """v1은 대상 파일에 직접 덮어써서, 저장 중 종료되면 세션이 통째로 날아갔다."""
        target = tmp_path / "a.json"
        write_json_atomic(target, {"정상": True})
        write_json_atomic(target, {"정상": "두번째"})
        target.write_text('{"깨진', encoding="utf-8")  # 반쪽짜리 파일 시뮬레이션
        assert read_json(target) == {"정상": True}

    def test_missing_file_returns_default(self, tmp_path):
        assert read_json(tmp_path / "없음.json", default={"기본": 1}) == {"기본": 1}

    def test_unserializable_payload_fails_gracefully(self, tmp_path):
        assert write_json_atomic(tmp_path / "a.json", {"f": object()}) is False


class TestDataDirIsolation:
    def test_env_override_is_respected(self, tmp_path, monkeypatch):
        target = tmp_path / "커스텀"
        monkeypatch.setenv("CHUGUI_DATA_DIR", str(target))
        assert data_dir() == target
        assert target.is_dir()

    def test_paths_are_absolute(self):
        """v1은 상대 경로라 exe 실행 위치에 따라 설정이 흩어졌다."""
        assert config_file().is_absolute()
        assert session_file().is_absolute()


class TestConfigRepository:
    def test_defaults_when_missing(self):
        config = ConfigRepository().load()
        assert config.adult_meal > 0
        assert config.dark_mode is True

    def test_round_trip(self):
        repo = ConfigRepository()
        repo.save(AppConfig(adult_meal=55_000, child_meal=30_000, dark_mode=False))
        loaded = repo.load()
        assert (loaded.adult_meal, loaded.child_meal, loaded.dark_mode) == (55_000, 30_000, False)

    @pytest.mark.parametrize(
        "payload",
        [{"adult_meal": "이상한값"}, {"adult_meal": -100}, {"adult_meal": 99_999_999}, "문자열", None],
    )
    def test_garbage_never_raises(self, payload):
        repo = ConfigRepository()
        repo.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        config = repo.load()
        assert 0 <= config.adult_meal <= 1_000_000


class TestSessionRepository:
    def test_round_trip_preserves_everything(self):
        repo = SessionRepository()
        original = Guest(
            name="김가족 & 김친지",
            names=["김가족", "김친지"],
            aliases=["조성도"],
            amount=300_000,
            relation=Relation.FAMILY,
            attendance=Attendance.ABSENT,
            payment=Payment.TRANSFER,
            adult_tickets=0,
            child_tickets=0,
            note="비고",
            sent_thanks=True,
            warnings=["확인"],
        )
        repo.save(SessionState(guests=[original], raw_text="원문"))

        restored = repo.load()
        assert restored.raw_text == "원문"
        assert restored.guests[0].to_dict() == original.to_dict()

    def test_partial_record_does_not_crash(self):
        """v1은 이 레코드가 세션 파일에 있으면 기동 직후 KeyError로 죽었다.

        게다가 그 파일이 저장소에 커밋되어 있어서, clone한 모든 사용자가
        첫 실행에서 에러 팝업을 봤다.
        """
        repo = SessionRepository()
        repo.path.write_text(
            json.dumps({"guest_data": [{"id": 1, "name": "테스트"}], "raw_text": "홍길동 10만"}),
            encoding="utf-8",
        )
        state = repo.load()
        guest = state.guests[0]
        assert guest.name == "테스트"
        assert guest.relation is Relation.OTHER
        assert guest.attendance is Attendance.PRESENT

    def test_v1_schema_is_readable(self):
        repo = SessionRepository()
        repo.path.write_text(
            json.dumps(
                {
                    "guest_data": [
                        {"id": 1, "name": "홍길동", "amount": 100000,
                         "relation": "친척/가족", "attended": "불참(송금)", "sent_thanks": True}
                    ],
                    "raw_text": "",
                }
            ),
            encoding="utf-8",
        )
        guest = repo.load().guests[0]
        assert guest.attendance is Attendance.ABSENT
        assert guest.sent_thanks is True

    @pytest.mark.parametrize("payload", ["[]", "null", "{}", "깨진 json", '{"guests": "문자열"}'])
    def test_garbage_yields_empty_session(self, payload):
        repo = SessionRepository()
        repo.path.write_text(payload, encoding="utf-8")
        assert repo.load().guests == []

    def test_clear_removes_backup_too(self):
        repo = SessionRepository()
        repo.save(SessionState(guests=[Guest(name="A")], raw_text=""))
        repo.save(SessionState(guests=[Guest(name="B")], raw_text=""))
        repo.clear()
        assert repo.load().guests == []


class TestTemplateRepository:
    def test_round_trip(self):
        repo = TemplateRepository()
        templates = repo.load()
        templates[Relation.WORK.value][Attendance.PRESENT.value] = "수정된 문구"
        repo.save(templates)
        assert repo.load()[Relation.WORK.value][Attendance.PRESENT.value] == "수정된 문구"

    def test_reset(self):
        repo = TemplateRepository()
        templates = repo.load()
        templates[Relation.WORK.value][Attendance.PRESENT.value] = "임시"
        repo.save(templates)
        repo.reset()
        assert repo.load()[Relation.WORK.value][Attendance.PRESENT.value] != "임시"


class TestLegacyMigration:
    def test_v1_files_are_migrated_once(self, tmp_path):
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / "config_settings.json").write_text(
            json.dumps({"adult_meal": 55000, "child_meal": 30000}), encoding="utf-8"
        )
        moved = migrate_legacy_files(legacy)
        assert "config_settings.json" in moved
        assert ConfigRepository().load().adult_meal == 55000

        # 이미 새 파일이 있으면 다시 덮어쓰지 않는다.
        assert migrate_legacy_files(legacy) == []

    def test_missing_legacy_dir_is_safe(self, tmp_path):
        assert migrate_legacy_files(tmp_path / "없음") == []
