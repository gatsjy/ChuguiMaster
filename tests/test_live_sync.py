"""명단 입력창에서 Enter 를 칠 때마다 표를 갱신한다 — 표에서 한 일은 지키면서."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from chugui.models import Source
from chugui.parsing.text_parser import parse_text
from chugui.services.merge import sync_with_text
from chugui.ui.guest_model import Column


def names(guests):
    return [g.name for g in guests]


class TestSyncRules:
    def test_unchanged_lines_keep_their_row_and_edits(self):
        existing = parse_text("홍길동 10만원\n김철수 5만원")
        existing[0].sent_thanks = True
        existing[0].amount = 120_000  # 표에서 고친 값
        result = sync_with_text(existing, parse_text("홍길동 10만원\n김철수 5만원\n이영희 3만원"),
                                ["홍길동 10만원", "김철수 5만원"])
        assert names(result.guests) == ["홍길동", "김철수", "이영희"]
        assert result.guests[0] is existing[0]
        assert result.guests[0].sent_thanks and result.guests[0].amount == 120_000
        assert result.added == 1 and not result.removed

    def test_deleted_line_leaves_the_table(self):
        existing = parse_text("홍길동 10만원\n김철수 5만원")
        result = sync_with_text(existing, parse_text("홍길동 10만원"), ["홍길동 10만원", "김철수 5만원"])
        assert names(result.guests) == ["홍길동"]
        assert names(result.removed) == ["김철수"]

    def test_edited_line_is_reread(self):
        existing = parse_text("홍길동 10만원")
        result = sync_with_text(existing, parse_text("홍길동 20만원"), ["홍길동 10만원"])
        assert result.guests[0].amount == 200_000
        assert result.added == 1 and len(result.removed) == 1

    def test_rows_from_files_are_untouched(self):
        existing = parse_text("홍길동 10만원")
        bank = parse_text("정계좌 5만원")[0]
        bank.source = Source.BANK
        result = sync_with_text([*existing, bank], parse_text(""), ["홍길동 10만원"])
        assert names(result.guests) == ["정계좌"]

    def test_earlier_appended_batch_is_kept(self):
        """'기존 목록에 추가' 로 붙인 앞 묶음은 지금 입력창에 없어도 지우지 않는다."""
        existing = parse_text("홍길동 10만원\n김철수 5만원")  # 앞 묶음
        result = sync_with_text(existing, parse_text("이영희 3만원"), ["이영희 3만원"])
        assert names(result.guests) == ["홍길동", "김철수", "이영희"]
        assert not result.removed

    def test_duplicate_lines_are_matched_one_to_one(self):
        existing = parse_text("한주안 10만원\n한주안 10만원")
        result = sync_with_text(existing, parse_text("한주안 10만원"), ["한주안 10만원", "한주안 10만원"])
        assert len(result.guests) == 1 and len(result.removed) == 1

    def test_no_change_is_reported(self):
        existing = parse_text("홍길동 10만원")
        result = sync_with_text(existing, parse_text("홍길동 10만원\n"), ["홍길동 10만원"])
        assert not result.changed


# ------------------------------------------------------------------ 화면


@pytest.fixture
def window(qt_app, monkeypatch):
    from chugui.ui.main_window import MainWindow

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    win = MainWindow()
    win.show()
    # 기동 120ms 뒤의 세션 복구가 끝난 뒤부터 사람처럼 조작한다.
    QTest.qWait(200)
    yield win
    win.close()


def type_line(window, qt_app, text):
    """입력창 끝에 글을 치고 Enter."""
    window._input.setFocus()
    cursor = window._input.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    window._input.setTextCursor(cursor)
    window._input.insertPlainText(text)
    QTest.keyClick(window._input, Qt.Key.Key_Return)
    qt_app.processEvents()


class TestWindow:
    def test_each_enter_updates_the_table(self, window, qt_app):
        type_line(window, qt_app, "홍길동 10만원")
        assert names(window._model.guests) == ["홍길동"]
        type_line(window, qt_app, "김철수 5만원")
        assert names(window._model.guests) == ["홍길동", "김철수"]
        assert window._card_total.value_label.text() == "150,000원"

    def test_table_edits_survive_later_enters(self, window, qt_app):
        type_line(window, qt_app, "홍길동 10만원")
        model = window._model
        model.setData(model.index(0, Column.SENT), Qt.CheckState.Checked.value, Qt.ItemDataRole.CheckStateRole)
        type_line(window, qt_app, "김철수 5만원")
        assert model.guests[0].sent_thanks

    def test_ctrl_enter_still_does_a_full_parse(self, window, qt_app):
        window._input.setPlainText("홍길동 10만원")
        QTest.keyClick(window, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        qt_app.processEvents()
        assert names(window._model.guests) == ["홍길동"]

    def test_typing_without_enter_does_not_touch_the_table(self, window, qt_app):
        type_line(window, qt_app, "홍길동 10만원")
        window._input.insertPlainText("김철수 5만원")
        qt_app.processEvents()
        assert names(window._model.guests) == ["홍길동"]

    def test_bank_rows_survive_enter(self, window, qt_app, tmp_path):
        type_line(window, qt_app, "홍길동 10만원")
        bank = tmp_path / "입출금내역.csv"
        bank.write_text("보낸분,입금액\n정계좌,50000\n", encoding="utf-8-sig")
        window._load_file(str(bank))
        type_line(window, qt_app, "김철수 5만원")
        assert names(window._model.guests) == ["홍길동", "김철수", "정계좌"]

    def test_excel_reupload_unlinks_the_input(self, window, qt_app, tmp_path):
        """엑셀로 교체한 뒤 Enter 를 쳐도 입력창의 옛 줄이 중복으로 들어가지 않는다."""
        from chugui.services.exporter import export_to_excel
        from chugui.services.settlement import settle

        type_line(window, qt_app, "홍길동 10만원")
        path = tmp_path / "명단.xlsx"
        export_to_excel(path, window._model.guests, settle(window._model.guests))
        window._load_file(str(path))
        type_line(window, qt_app, "")
        assert names(window._model.guests) == ["홍길동"]
        assert "Ctrl+Enter" in window.statusBar().currentMessage()

    def test_scroll_position_is_kept(self, window, qt_app):
        window._input.setPlainText("\n".join(f"하객{i:02d}님 {i}만원" for i in range(1, 60)))
        window._handle_parse()
        qt_app.processEvents()
        bar = window._table.verticalScrollBar()
        bar.setValue(bar.maximum())
        type_line(window, qt_app, "마지막 1만원")
        assert bar.value() > 0
