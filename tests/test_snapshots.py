"""스냅샷 · 되돌리기 테스트.

자동 저장은 **크래시**를 막지만 **사람의 실수**는 막지 못한다.
`전체 비우기` 를 잘못 누르면 자동 저장은 그 결과를 성실히 저장할 뿐이다.
이 테스트는 되돌릴 지점이 실제로 남는지 검증한다.
"""

from __future__ import annotations

import pytest

from chugui.models import Guest
from chugui.storage.repositories import SessionState
from chugui.storage.snapshots import SnapshotStore


def payload(count: int, amount: int = 100_000) -> dict:
    guests = [Guest(name=f"하객{n}", names=[f"하객{n}"], amount=amount) for n in range(count)]
    return SessionState(guests=guests, raw_text="원문").to_dict()


class TestCapture:
    def test_capture_creates_file(self, tmp_path):
        store = SnapshotStore(tmp_path)
        assert store.capture(payload(3), "전체 비우기 전") is not None
        assert len(list(tmp_path.glob("*.json"))) == 1

    def test_empty_state_is_not_captured(self, tmp_path):
        """되돌릴 것이 없으면 시점을 남기지 않는다."""
        store = SnapshotStore(tmp_path)
        assert store.capture(payload(0), "자동") is None
        assert list(tmp_path.glob("*.json")) == []

    def test_same_second_captures_do_not_overwrite(self, tmp_path):
        store = SnapshotStore(tmp_path)
        first = store.capture(payload(1), "테스트")
        second = store.capture(payload(2), "테스트")
        assert first != second
        assert len(list(tmp_path.glob("*.json"))) == 2

    def test_reason_with_spaces_is_safe_for_filename(self, tmp_path):
        store = SnapshotStore(tmp_path)
        path = store.capture(payload(1), "파일 병합 전 / 위험")
        assert path is not None and path.exists()


class TestRingBuffer:
    def test_old_snapshots_are_pruned(self, tmp_path):
        store = SnapshotStore(tmp_path, limit=3)
        for index in range(6):
            store.capture(payload(index + 1), f"회차{index}")
        assert len(list(tmp_path.glob("*.json"))) == 3

    def test_newest_survive_pruning(self, tmp_path):
        store = SnapshotStore(tmp_path, limit=2)
        for index in range(5):
            store.capture(payload(index + 1), f"회차{index}")
        counts = {info.guest_count for info in store.list_snapshots()}
        assert counts == {4, 5}


class TestListing:
    def test_newest_first(self, tmp_path):
        store = SnapshotStore(tmp_path, limit=10)
        for index in range(3):
            store.capture(payload(index + 1), f"회차{index}")
        infos = store.list_snapshots()
        assert [info.guest_count for info in infos] == [3, 2, 1]

    def test_info_carries_reason_and_totals(self, tmp_path):
        store = SnapshotStore(tmp_path)
        store.capture(payload(2, amount=250_000), "전체 비우기 전")
        info = store.list_snapshots()[0]
        assert info.reason == "전체 비우기 전"
        assert info.guest_count == 2
        assert info.total_amount == 500_000
        assert "2건" in info.detail

    def test_corrupted_snapshot_is_skipped(self, tmp_path):
        store = SnapshotStore(tmp_path)
        store.capture(payload(1), "정상")
        (tmp_path / "20990101-000000-깨짐.json").write_text("{깨진", encoding="utf-8")
        assert len(store.list_snapshots()) == 1

    def test_empty_directory(self, tmp_path):
        assert SnapshotStore(tmp_path).list_snapshots() == []


class TestRoundTrip:
    def test_load_restores_guests(self, tmp_path):
        store = SnapshotStore(tmp_path)
        path = store.capture(payload(4), "테스트")
        restored = SessionState.from_dict(store.load(path))
        assert len(restored.guests) == 4
        assert restored.raw_text == "원문"

    def test_load_missing_returns_none(self, tmp_path):
        assert SnapshotStore(tmp_path).load(tmp_path / "없음.json") is None


class TestUndoInWindow:
    """창 수준 되돌리기. 파괴 연산 후 원래 목록이 살아 돌아와야 한다."""

    @pytest.fixture
    def window(self, qt_app):
        from chugui.parsing.text_parser import parse_text
        from chugui.ui.main_window import MainWindow

        win = MainWindow()
        win.show()
        win._model.set_guests(parse_text("홍길동 10만원 친척\n김철수 5만원 친구"))
        yield win
        win.close()

    def test_clear_can_be_undone(self, window, qt_app, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        window._handle_clear()
        qt_app.processEvents()
        assert window._model.guests == []

        window._undo_last()
        qt_app.processEvents()
        assert len(window._model.guests) == 2
        assert window._model.guests[0].name == "홍길동"

    def test_clear_leaves_a_snapshot(self, window, qt_app, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        window._handle_clear()
        qt_app.processEvents()
        infos = window._snapshots.list_snapshots()
        assert infos and infos[0].guest_count == 2

    def test_parse_overwrite_can_be_undone(self, window, qt_app, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        window._input.setPlainText("이영희 30만원 직장")
        window._handle_parse()
        qt_app.processEvents()
        assert len(window._model.guests) == 1

        window._undo_last()
        qt_app.processEvents()
        assert len(window._model.guests) == 2

    def test_undo_restores_input_text_too(self, window, qt_app, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        window._input.setPlainText("원래 입력")
        window._handle_clear()
        qt_app.processEvents()
        window._undo_last()
        qt_app.processEvents()
        assert window._input.toPlainText() == "원래 입력"

    def test_undo_is_single_shot(self, window, qt_app, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        window._handle_clear()
        window._undo_last()
        qt_app.processEvents()
        before = len(window._model.guests)
        window._undo_last()  # 두 번째 호출은 아무 일도 하지 않는다
        qt_app.processEvents()
        assert len(window._model.guests) == before

    def test_undo_toast_shows_action_button(self, window, qt_app, monkeypatch):
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
        )
        window._handle_clear()
        qt_app.processEvents()
        assert window._toast._action.isVisible()
        assert window._toast._action.text() == "되돌리기"
