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


def test_context_menus_are_styled():
    """Windows 기본 메뉴는 흰 바탕이라 밝은 글자가 안 보였다(표 우클릭이 빈 상자로 보임)."""
    sheet = build_stylesheet(PALETTE)
    assert "QMenu {" in sheet
    assert f"background-color: {PALETTE.surface}" in sheet.split("QMenu {", 1)[1].split("}", 1)[0]
    assert "QMenu::item:selected" in sheet
