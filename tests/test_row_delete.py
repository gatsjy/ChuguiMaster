"""표에서 줄 삭제(우클릭 · Delete)와 되돌리기."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack
from PySide6.QtTest import QTest

from chugui.parsing.text_parser import parse_text
from chugui.services.messages import MessageService
from chugui.ui.guest_model import Column, GuestTableModel

LINES = "홍길동 10만원\n김철수 5만원\n이영희 3만원\n박민수 7만원"


@pytest.fixture
def model(qt_app):
    m = GuestTableModel(MessageService())
    m.set_undo_stack(QUndoStack())
    m.set_guests(parse_text(LINES))
    return m


def names(model):
    return [g.name for g in model.guests]


class TestModel:
    def test_remove_renumbers(self, model):
        model.remove_rows([1])
        assert names(model) == ["홍길동", "이영희", "박민수"]
        assert [g.guest_id for g in model.guests] == [1, 2, 3]

    def test_undo_restores_original_positions(self, model):
        model.remove_rows([0, 2])
        assert names(model) == ["김철수", "박민수"]
        model._undo_stack.undo()
        assert names(model) == ["홍길동", "김철수", "이영희", "박민수"]
        model._undo_stack.redo()
        assert names(model) == ["김철수", "박민수"]

    def test_cell_edit_before_delete_still_undoes_correctly(self, model):
        """삭제 전에 한 셀 편집을 되돌려도 엉뚱한 줄을 고치지 않는다."""
        model.setData(model.index(3, Column.AMOUNT), "90000", Qt.ItemDataRole.EditRole)
        model.remove_rows([0])
        stack = model._undo_stack
        stack.undo()  # 삭제 취소
        stack.undo()  # 금액 편집 취소
        assert model.guests[3].name == "박민수"
        assert model.guests[3].amount == 70_000

    def test_invalid_rows_are_ignored(self, model):
        model.remove_rows([-1, 99])
        assert len(model.guests) == 4
        assert model._undo_stack.count() == 0

    def test_summary_follows(self, model):
        seen = []
        model.guestsChanged.connect(lambda: seen.append(sum(g.amount for g in model.guests)))
        model.remove_rows([0])
        assert seen[-1] == 150_000


@pytest.fixture
def window(qt_app):
    from chugui.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    win._model.set_guests(parse_text(LINES))
    qt_app.processEvents()
    yield win
    win.close()


class TestWindow:
    def test_delete_key_on_table(self, window, qt_app):
        window._table.setFocus()
        window._table.selectRow(1)
        QTest.keyClick(window._table, Qt.Key.Key_Delete)
        assert names(window._model) == ["홍길동", "이영희", "박민수"]

    def test_delete_key_in_input_does_not_delete_rows(self, window, qt_app):
        window._table.selectRow(1)
        window._input.setPlainText("abc")
        window._input.setFocus()
        QTest.keyClick(window._input, Qt.Key.Key_Delete)
        assert len(window._model.guests) == 4

    def test_multi_select_delete(self, window, qt_app):
        selection = window._table.selectionModel()
        for row in (0, 3):
            selection.select(
                window._proxy.index(row, 0),
                selection.SelectionFlag.Select | selection.SelectionFlag.Rows,
            )
        window._delete_selected_rows()
        assert names(window._model) == ["김철수", "이영희"]

    def test_toast_undo_restores(self, window, qt_app):
        window._delete_rows([0])
        window._undo_last()
        assert names(window._model)[0] == "홍길동"

    def test_delete_is_autosaved(self, window, qt_app):
        window._autosave_timer.stop()
        window._delete_rows([0])
        assert window._autosave_timer.isActive()

    def test_filtered_view_deletes_the_right_guest(self, window, qt_app):
        """검색으로 걸러진 상태에서도 보이는 줄이 지워져야 한다(프록시 → 원본 변환)."""
        window._search.setText("이영희")
        window._table.selectRow(0)
        window._delete_selected_rows()
        window._search.clear()
        assert "이영희" not in names(window._model)
        assert len(window._model.guests) == 3

    def test_context_menu_is_enabled(self, window):
        # 메뉴 자체는 exec() 로 모달이라 여기서는 정책만 확인한다.
        assert window._table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
