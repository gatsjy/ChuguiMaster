"""관계 · 참석 칸: 한 번 클릭하면 목록이 열리고, 고르면 바로 반영된다. 우클릭 메뉴는 읽힌다."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox

from chugui.models import Attendance, Relation
from chugui.parsing.text_parser import parse_text
from chugui.ui.guest_model import TOOLTIPS, Column
from chugui.ui.theme import PALETTE, build_stylesheet


@pytest.fixture
def window(qt_app):
    from chugui.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    QTest.qWait(200)
    win._model.set_guests(parse_text("한주안 10만원\n이영희 3만원"))
    qt_app.processEvents()
    yield win
    win.close()


def open_editor(window, column):
    table = window._table
    rect = table.visualRect(window._proxy.index(0, column))
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    QTest.qWait(50)
    return next((c for c in table.findChildren(QComboBox) if c.isVisible()), None)


def pick(editor, text):
    editor.setCurrentText(text)
    editor.activated.emit(editor.currentIndex())


@pytest.mark.parametrize(
    ("column", "choice", "check"),
    [
        (Column.RELATION, Relation.WORK.value, lambda g: g.relation is Relation.WORK),
        (Column.ATTENDANCE, Attendance.ABSENT.value, lambda g: g.attendance is Attendance.ABSENT),
    ],
)
def test_single_click_opens_and_pick_applies(window, qt_app, column, choice, check):
    editor = open_editor(window, column)
    assert editor is not None, "한 번 클릭으로 목록 편집기가 열려야 한다"
    pick(editor, choice)
    qt_app.processEvents()
    assert check(window._model.guests[0])
    assert not any(c.isVisible() for c in window._table.findChildren(QComboBox)), "고르면 닫혀야 한다"


def test_pick_is_undoable(window, qt_app):
    pick(open_editor(window, Column.RELATION), Relation.FAITH.value)
    qt_app.processEvents()
    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window._model.guests[0].relation is Relation.OTHER


def test_ticket_stepper_buttons(window, qt_app):
    """대인/소인 위아래(▲/▼) 버튼 클릭으로 숫자가 증감한다."""
    table = window._table
    # 0번 하객: 한주안 10만원 (초기 대인 1장, 소인 0장)
    assert window._model.guests[0].adult_tickets == 1
    assert window._model.guests[0].child_tickets == 0

    # 대인 ▲ 버튼 클릭 (오른쪽 상단)
    idx_adult = window._proxy.index(0, int(Column.ADULT_TICKETS))
    rect_adult = table.visualRect(idx_adult)
    delegate = table.itemDelegateForColumn(int(Column.ADULT_TICKETS))
    up_rect, down_rect = delegate._button_rects(rect_adult)

    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=up_rect.center())
    qt_app.processEvents()
    assert window._model.guests[0].adult_tickets == 2, "▲ 버튼을 누르면 대인 식권이 1 늘어야 한다"

    # 대인 ▼ 버튼 클릭
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=down_rect.center())
    qt_app.processEvents()
    assert window._model.guests[0].adult_tickets == 1, "▼ 버튼을 누르면 대인 식권이 1 줄어야 한다"

    # Ctrl+Z 로 되돌리기
    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    qt_app.processEvents()
    assert window._model.guests[0].adult_tickets == 2, "Ctrl+Z 로 되돌릴 수 있어야 한다"

    # 소인 ▲ 버튼 클릭
    idx_child = window._proxy.index(0, int(Column.CHILD_TICKETS))
    rect_child = table.visualRect(idx_child)
    up_child, _down_child = delegate._button_rects(rect_child)

    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=up_child.center())
    qt_app.processEvents()
    assert window._model.guests[0].child_tickets == 1, "▲ 버튼을 누르면 소인 식권이 1 늘어야 한다"


def test_sent_badge_toggle(window, qt_app):
    """발송 칸 클릭 시 발송/미발송 상태가 즉시 토글된다."""
    table = window._table
    assert window._model.guests[0].sent_thanks is False

    idx_sent = window._proxy.index(0, int(Column.SENT))
    rect_sent = table.visualRect(idx_sent)
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect_sent.center())
    qt_app.processEvents()
    assert window._model.guests[0].sent_thanks is True, "클릭 시 발송완료로 바뀌어야 한다"

    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect_sent.center())
    qt_app.processEvents()
    assert window._model.guests[0].sent_thanks is False, "다시 클릭 시 미발송으로 바뀌어야 한다"


def test_other_columns_still_need_double_click(window, qt_app):
    """금액 · 이름은 한 번 클릭으로 편집되지 않는다(줄 선택과 겹치지 않게)."""
    table = window._table
    rect = table.visualRect(window._proxy.index(0, Column.AMOUNT))
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    QTest.qWait(50)
    assert table.state() != table.State.EditingState


def test_tooltips_say_click():
    assert "클릭" in TOOLTIPS[Column.RELATION]
    assert "클릭" in TOOLTIPS[Column.ATTENDANCE]
    assert "버튼" in TOOLTIPS[Column.ADULT_TICKETS]
    assert "버튼" in TOOLTIPS[Column.CHILD_TICKETS]


def test_ticket_bulk_actions(window, qt_app):
    window._set_tickets_bulk([0, 1], adult=2, child=1)
    qt_app.processEvents()
    assert window._model.guests[0].adult_tickets == 2
    assert window._model.guests[0].child_tickets == 1
    assert window._model.guests[1].adult_tickets == 2
    assert window._model.guests[1].child_tickets == 1

    window._add_child_ticket_bulk([0])
    qt_app.processEvents()
    assert window._model.guests[0].child_tickets == 2

    # Ctrl+Z 로 되돌리기
    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    qt_app.processEvents()
    assert window._model.guests[0].child_tickets == 1


def test_context_menus_are_styled():
    """Windows 기본 메뉴는 흰 바탕이라 밝은 글자가 안 보였다(표 우클릭이 빈 상자로 보임)."""
    sheet = build_stylesheet(PALETTE)
    assert "QMenu {" in sheet
    assert f"background-color: {PALETTE.surface}" in sheet.split("QMenu {", 1)[1].split("}", 1)[0]
    assert "QMenu::item:selected" in sheet


def test_ticket_stepper_mouse_hover(window, qt_app):
    """표에서 마우스 이동/호버 시 TicketStepperDelegate가 정상 동작하고 예외가 발생하지 않는다."""
    table = window._table
    idx = window._proxy.index(0, int(Column.ADULT_TICKETS))
    rect = table.visualRect(idx)
    QTest.mouseMove(table.viewport(), rect.center())
    qt_app.processEvents()
    delegate = table.itemDelegateForColumn(int(Column.ADULT_TICKETS))
    assert hasattr(delegate, "set_hover_row")
    delegate.set_hover_row(0)
    assert delegate._hover_row == 0
    delegate.set_hover_row(-1)
    assert delegate._hover_row == -1

