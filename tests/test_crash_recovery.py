"""비정상 종료 감지 · 시점 복구 테스트."""

from __future__ import annotations

import json

import pytest

from chugui.parsing.text_parser import parse_text
from chugui.storage.crash import CrashSentinel


class TestCrashSentinel:
    def test_first_run_is_not_a_crash(self, tmp_path):
        sentinel = CrashSentinel(tmp_path / "running.lock")
        assert sentinel.arm().crashed is False

    def test_clean_exit_leaves_no_trace(self, tmp_path):
        sentinel = CrashSentinel(tmp_path / "running.lock")
        sentinel.arm()
        sentinel.disarm()
        assert CrashSentinel(tmp_path / "running.lock").arm().crashed is False

    def test_missing_disarm_is_reported_as_crash(self, tmp_path):
        """종료 처리를 못 하고 죽으면 표식이 남는다."""
        path = tmp_path / "running.lock"
        CrashSentinel(path).arm()          # 1회차: 강제 종료 시뮬레이션
        report = CrashSentinel(path).arm()  # 2회차
        assert report.crashed is True
        assert "정상적으로 종료되지" in report.message

    def test_report_includes_start_time(self, tmp_path):
        path = tmp_path / "running.lock"
        CrashSentinel(path).arm()
        report = CrashSentinel(path).arm()
        assert report.last_started_at is not None
        assert "시작" in report.message

    def test_corrupted_sentinel_still_detects_crash(self, tmp_path):
        path = tmp_path / "running.lock"
        path.write_text("{깨진", encoding="utf-8")
        report = CrashSentinel(path).arm()
        assert report.crashed is True
        assert report.last_started_at is None

    def test_clean_report_has_empty_message(self, tmp_path):
        assert CrashSentinel(tmp_path / "running.lock").arm().message == ""

    def test_disarm_is_idempotent(self, tmp_path):
        sentinel = CrashSentinel(tmp_path / "running.lock")
        sentinel.arm()
        sentinel.disarm()
        sentinel.disarm()  # 두 번 불러도 예외 없음

    def test_sentinel_records_pid(self, tmp_path):
        import os

        path = tmp_path / "running.lock"
        CrashSentinel(path).arm()
        assert json.loads(path.read_text(encoding="utf-8"))["pid"] == os.getpid()


class TestRestoreThroughWindow:
    @pytest.fixture
    def window(self, qt_app, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        from chugui.ui.main_window import MainWindow

        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        win = MainWindow()
        win.show()
        win._model.set_guests(parse_text("홍길동 10만원 친척\n김철수 5만원 친구"))
        yield win
        win.close()

    def test_restore_dialog_lists_snapshots(self, window, qt_app):
        from chugui.ui.dialogs import SnapshotRestoreDialog

        window._handle_clear()
        qt_app.processEvents()

        dialog = SnapshotRestoreDialog(window._snapshots.list_snapshots(), window)
        assert dialog._list.count() >= 1

    def test_empty_snapshot_list_disables_ok(self, qt_app):
        from PySide6.QtWidgets import QDialogButtonBox

        from chugui.ui.dialogs import SnapshotRestoreDialog

        dialog = SnapshotRestoreDialog([], None)
        box = dialog.findChild(QDialogButtonBox)
        assert box.button(QDialogButtonBox.StandardButton.Ok).isEnabled() is False

    def test_restore_payload_brings_guests_back(self, window, qt_app):
        payload = window._current_payload()
        window._handle_clear()
        qt_app.processEvents()
        assert window._model.guests == []

        window._restore_payload(payload)
        qt_app.processEvents()
        assert len(window._model.guests) == 2

    def test_snapshot_survives_session_clear(self, window, qt_app):
        """세션 파일을 지워도 스냅샷은 남아야 복구가 가능하다."""
        window._handle_clear()
        qt_app.processEvents()
        assert window._session_repo.load().guests == []
        assert window._snapshots.list_snapshots()

    def test_restore_button_exists(self, window):
        assert window._btn_restore.accessibleName() == "이전 시점 복구"
