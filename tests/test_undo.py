"""셀 편집 되돌리기 테스트.

표에서 금액을 잘못 고치면 되돌릴 방법이 없었다. 자동 저장은 잘못 고친 값을
성실히 저장할 뿐이고, 스냅샷은 파괴 연산 단위라 셀 하나까지 되짚지 못한다.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QUndoStack

from chugui.models import Attendance, Relation
from chugui.parsing.text_parser import parse_text
from chugui.services.messages import MessageService
from chugui.ui.guest_model import Column, GuestTableModel


@pytest.fixture
def model(qt_app):
    table_model = GuestTableModel(MessageService())
    stack = QUndoStack()
    table_model.set_undo_stack(stack)
    table_model.set_guests(parse_text("홍길동 10만원 친척\n김철수 5만원 대학동기"))
    return table_model


def stack_of(model: GuestTableModel) -> QUndoStack:
    return model._undo_stack


class TestAmountUndo:
    def test_undo_restores_previous_amount(self, model):
        model.setData(model.index(0, Column.AMOUNT), "999,999")
        assert model.guests[0].amount == 999_999
        stack_of(model).undo()
        assert model.guests[0].amount == 100_000

    def test_redo_reapplies(self, model):
        model.setData(model.index(0, Column.AMOUNT), "250,000")
        stack_of(model).undo()
        stack_of(model).redo()
        assert model.guests[0].amount == 250_000

    def test_multiple_edits_undo_in_reverse_order(self, model):
        model.setData(model.index(0, Column.AMOUNT), "200,000")
        model.setData(model.index(0, Column.AMOUNT), "300,000")
        stack = stack_of(model)
        stack.undo()
        assert model.guests[0].amount == 200_000
        stack.undo()
        assert model.guests[0].amount == 100_000


class TestOtherColumns:
    def test_name_undo(self, model):
        model.setData(model.index(0, Column.NAME), "홍길순")
        stack_of(model).undo()
        assert model.guests[0].name == "홍길동"

    def test_relation_undo(self, model):
        model.setData(model.index(0, Column.RELATION), Relation.WORK.value)
        assert model.guests[0].relation is Relation.WORK
        stack_of(model).undo()
        assert model.guests[0].relation is Relation.FAMILY

    def test_attendance_undo_restores_tickets(self, model):
        """불참으로 바꾸면 식권이 0이 된다. 되돌리면 식권도 함께 돌아와야 한다."""
        before = model.guests[0].adult_tickets
        model.setData(model.index(0, Column.ATTENDANCE), Attendance.ABSENT.value)
        assert model.guests[0].adult_tickets == 0
        stack_of(model).undo()
        assert model.guests[0].attendance is Attendance.PRESENT
        assert model.guests[0].adult_tickets == before

    def test_ticket_undo(self, model):
        model.setData(model.index(0, Column.ADULT_TICKETS), 7)
        stack_of(model).undo()
        assert model.guests[0].adult_tickets == 1

    def test_sent_checkbox_undo(self, model):
        index = model.index(0, Column.SENT)
        model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        assert model.guests[0].sent_thanks is True
        stack_of(model).undo()
        assert model.guests[0].sent_thanks is False


class TestStackHygiene:
    def test_rejected_edit_does_not_grow_stack(self, model):
        """빈 이름처럼 거부되는 편집은 이력에 쌓이지 않는다."""
        assert model.setData(model.index(0, Column.NAME), "   ") is False
        assert stack_of(model).count() == 0

    def test_no_op_check_does_not_grow_stack(self, model):
        index = model.index(0, Column.SENT)
        model.setData(index, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        assert stack_of(model).count() == 0

    def test_reloading_list_clears_history(self, model):
        """목록이 바뀌면 이전 행 번호가 무의미해진다. 이력을 남기면 엉뚱한 행을 고친다."""
        model.setData(model.index(0, Column.AMOUNT), "200,000")
        assert stack_of(model).count() == 1
        model.set_guests(parse_text("이영희 30만원 직장"))
        assert stack_of(model).count() == 0

    def test_works_without_stack(self, qt_app):
        """되돌리기 스택 없이도 편집은 그대로 동작해야 한다."""
        plain = GuestTableModel(MessageService())
        plain.set_guests(parse_text("홍길동 10만원 친척"))
        assert plain.setData(plain.index(0, Column.AMOUNT), "500,000") is True
        assert plain.guests[0].amount == 500_000


class TestWindowIntegration:
    @pytest.fixture
    def window(self, qt_app):
        from chugui.ui.main_window import MainWindow

        win = MainWindow()
        win.show()
        win._model.set_guests(parse_text("홍길동 10만원 친척"))
        yield win
        win.close()

    def test_undo_redo_shortcuts_registered(self, window):
        shortcuts = {
            action.shortcut().toString(QKeySequence.SequenceFormat.PortableText)
            for action in window.actions()
        }
        assert "Ctrl+Z" in shortcuts
        assert "Ctrl+Y" in shortcuts or "Ctrl+Shift+Z" in shortcuts

    def test_append_shortcut_registered(self, window):
        shortcuts = {
            action.shortcut().toString(QKeySequence.SequenceFormat.PortableText)
            for action in window.actions()
        }
        assert "Ctrl+Shift+Return" in shortcuts

    def test_edit_then_undo_through_window_stack(self, window, qt_app):
        window._model.setData(window._model.index(0, Column.AMOUNT), "777,000")
        qt_app.processEvents()
        assert window._model.guests[0].amount == 777_000
        window._undo_stack.undo()
        qt_app.processEvents()
        assert window._model.guests[0].amount == 100_000

    def test_undo_updates_totals(self, window, qt_app):
        window._model.setData(window._model.index(0, Column.AMOUNT), "900,000")
        qt_app.processEvents()
        assert window._current_settlement().total_amount == 900_000
        window._undo_stack.undo()
        qt_app.processEvents()
        assert window._current_settlement().total_amount == 100_000
