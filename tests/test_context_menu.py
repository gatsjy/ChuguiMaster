"""우클릭 메뉴와 선택 동작. 사람이 메뉴를 고르는 방식(강조 → Enter)으로 검증한다."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from chugui.parsing.text_parser import parse_text
from chugui.ui.guest_model import Column

LINES = "홍길동 10만원 친척\n김철수 5만원 회사\n이영희 3만원 교회 불참\n박민수 7만원 대학동기\n최하객 2만원"
ABSENT = 2  # 이영희


@pytest.fixture
def window(qt_app):
    from chugui.ui.main_window import MainWindow

    win = MainWindow()
    win.resize(1360, 880)
    win.show()
    QTest.qWait(200)
    win._model.set_guests(parse_text(LINES))
    qt_app.processEvents()
    yield win
    win.close()


def select_rows(window, rows):
    table = window._table
    table.clearSelection()
    model = table.selectionModel()
    for row in rows:
        model.select(window._proxy.index(row, 0), model.SelectionFlag.Select | model.SelectionFlag.Rows)


def open_menu(window, row, choose=None, path=()):
    """줄을 우클릭해 메뉴를 열고 choose 를 고른다. 메뉴 항목 목록을 돌려준다."""
    seen: dict = {}

    def handle():
        menu = QApplication.activePopupWidget()
        if menu is None:
            return
        seen["items"] = [action.text() for action in menu.actions() if action.text()]
        seen["enabled"] = {action.text(): action.isEnabled() for action in menu.actions() if action.text()}
        if choose is None:
            menu.close()
            return
        target = menu
        for step in path:
            action = next(a for a in target.actions() if a.text() == step)
            target.setActiveAction(action)
            QTest.keyClick(target, Qt.Key.Key_Right)
            QTest.qWait(100)
            target = action.menu()
        action = next(a for a in target.actions() if a.text() == choose)
        target.setActiveAction(action)
        QTest.keyClick(target, Qt.Key.Key_Return)

    QTimer.singleShot(150, handle)
    position = window._table.visualRect(window._proxy.index(row, int(Column.NAME))).center()
    window._show_table_menu(position)
    return seen


class TestSelection:
    def test_right_click_outside_selection_selects_that_row(self, window):
        select_rows(window, [0])
        open_menu(window, 3)
        assert window._selected_source_rows() == [3]

    def test_right_click_inside_selection_keeps_it(self, window):
        select_rows(window, [0, 1, 3])
        seen = open_menu(window, 1)
        assert window._selected_source_rows() == [0, 1, 3]
        assert "3줄 삭제" in seen["items"]
        assert seen["enabled"]["인사말 복사"] is False

    def test_delete_keeps_a_row_selected_for_the_next_delete(self, window):
        """Delete 로 지운 뒤 그 자리 줄이 선택되어 연달아 지울 수 있다."""
        table = window._table
        table.setFocus()
        table.selectRow(1)
        QTest.keyClick(table, Qt.Key.Key_Delete)
        QTest.keyClick(table, Qt.Key.Key_Delete)
        assert [g.name for g in window._model.guests] == ["홍길동", "박민수", "최하객"]

    def test_deleting_the_last_row_selects_the_new_last(self, window):
        window._delete_rows([4])
        assert window._selected_source_rows() == [3]

    @pytest.mark.parametrize(
        "column", [Column.SENT, Column.COPY, Column.ADULT_TICKETS, Column.RELATION, Column.ATTENDANCE]
    )
    def test_right_button_never_edits(self, window, column):
        before = [(g.sent_thanks, g.adult_tickets, g.relation, g.attendance) for g in window._model.guests]
        QTimer.singleShot(100, lambda: QApplication.activePopupWidget() and QApplication.activePopupWidget().close())
        point = window._table.visualRect(window._proxy.index(0, int(column))).center()
        QTest.mouseClick(window._table.viewport(), Qt.MouseButton.RightButton, pos=point)
        QTest.qWait(200)
        after = [(g.sent_thanks, g.adult_tickets, g.relation, g.attendance) for g in window._model.guests]
        assert before == after
        assert window._table.state() != window._table.State.EditingState


class TestTicketQuickSet:
    def test_absent_guests_get_no_tickets(self, window):
        """불참 줄이 섞인 채 '대인 2장' 을 고르면 불참 하객에게도 2장(= 식대)이 들어갔다."""
        select_rows(window, [1, ABSENT, 3])
        open_menu(window, 1, choose="대인 2장", path=("식권 빠른 설정",))
        guests = window._model.guests
        assert guests[ABSENT].adult_tickets == 0
        assert (guests[1].adult_tickets, guests[3].adult_tickets) == (2, 2)
        assert "불참 1건 제외" in window._toast._label.text()

    def test_one_undo_restores_the_whole_change(self, window):
        select_rows(window, [0, 1, 3])
        open_menu(window, 0, choose="대인 2장 + 소인 1장", path=("식권 빠른 설정",))
        QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        assert [(g.adult_tickets, g.child_tickets) for g in window._model.guests] == [
            (1, 0), (1, 0), (0, 0), (1, 0), (1, 0),
        ]

    def test_no_change_leaves_no_undo_entry(self, window):
        select_rows(window, [0])
        open_menu(window, 0, choose="대인 1장", path=("식권 빠른 설정",))
        assert window._undo_stack.count() == 0


class TestMenuActions:
    def test_copy_from_menu(self, window):
        select_rows(window, [3])
        open_menu(window, 3, choose="인사말 복사")
        assert QApplication.clipboard().text().startswith("박민수")

    def test_delete_under_filter_removes_the_visible_row(self, window):
        window._search.setText("이영희")
        open_menu(window, 0, choose="줄 삭제")
        window._search.clear()
        assert "이영희" not in [g.name for g in window._model.guests]
        assert len(window._model.guests) == 4

    def test_delete_under_sort_removes_the_visible_row(self, window):
        window._table.sortByColumn(int(Column.AMOUNT), Qt.SortOrder.DescendingOrder)
        open_menu(window, 0, choose="줄 삭제")  # 금액이 가장 큰 홍길동
        assert "홍길동" not in [g.name for g in window._model.guests]
