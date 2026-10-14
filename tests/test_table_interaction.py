"""표 조작이 의도하지 않은 값 변경을 일으키지 않는다. 버튼처럼 보이는 것만 버튼처럼 동작한다."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from chugui.parsing.text_parser import parse_text
from chugui.ui.guest_model import TOOLTIPS, Column


@pytest.fixture
def window(qt_app):
    from chugui.ui.main_window import MainWindow

    win = MainWindow()
    win.resize(1360, 880)
    win.show()
    QTest.qWait(200)
    win._model.set_guests(parse_text("한주안 10만원\n이영희 3만원"))
    qt_app.processEvents()
    yield win
    win.close()


def cell_rect(window, row, column):
    return window._table.visualRect(window._proxy.index(row, int(column)))


class TestTicketStepper:
    def test_clicking_the_number_only_selects_the_row(self, window, qt_app):
        """줄을 고르려고 숫자를 눌렀더니 식권(= 식대)이 바뀌던 문제."""
        rect = cell_rect(window, 0, Column.ADULT_TICKETS)
        for point in (QPoint(rect.left() + 8, rect.top() + 4), QPoint(rect.left() + 8, rect.bottom() - 4)):
            QTest.mouseClick(window._table.viewport(), Qt.MouseButton.LeftButton, pos=point)
            QTest.qWait(600)  # 더블클릭으로 묶이지 않게
        assert window._model.guests[0].adult_tickets == 1
        assert window._undo_stack.count() == 0
        assert window._table.selectionModel().isRowSelected(0)

    def test_down_at_zero_leaves_no_undo_entry(self, window, qt_app):
        delegate = window._table.itemDelegateForColumn(int(Column.CHILD_TICKETS))
        _up, down = delegate._button_rects(cell_rect(window, 0, Column.CHILD_TICKETS))
        QTest.mouseClick(window._table.viewport(), Qt.MouseButton.LeftButton, pos=down.center())
        assert window._model.guests[0].child_tickets == 0
        assert window._undo_stack.count() == 0

    def test_fast_taps_count_each_tap_once(self, window, qt_app):
        delegate = window._table.itemDelegateForColumn(int(Column.ADULT_TICKETS))
        up, _down = delegate._button_rects(cell_rect(window, 0, Column.ADULT_TICKETS))
        for _ in range(3):
            QTest.mouseClick(window._table.viewport(), Qt.MouseButton.LeftButton, pos=up.center())
        assert window._model.guests[0].adult_tickets == 4

    def test_tooltips_do_not_promise_wheel(self):
        for column in (Column.ADULT_TICKETS, Column.CHILD_TICKETS):
            assert "휠" not in TOOLTIPS[column]


class TestCopyBadge:
    def _label_color(self, window, row):
        """복사 칸 버튼 가운데의 배경색."""
        rect = cell_rect(window, row, Column.COPY)
        image = window._table.viewport().grab().toImage()
        return image.pixelColor(rect.left() + 12, rect.center().y())

    def test_copy_marks_only_the_copied_guest(self, window, qt_app):
        before = self._label_color(window, 0)
        window._on_copy_clicked(window._proxy.index(0, int(Column.COPY)))
        qt_app.processEvents()
        assert self._label_color(window, 0) != before, "복사한 줄의 버튼이 '복사완료' 로 바뀌어야 한다"
        assert self._label_color(window, 1) == before, "복사하지 않은 줄은 그대로여야 한다"
        assert not window._model.guests[0].sent_thanks, "복사는 발송이 아니다"

    def test_sent_flag_alone_does_not_claim_copied(self, window, qt_app):
        before = self._label_color(window, 0)
        window._model.mark_sent(0, True)
        qt_app.processEvents()
        assert self._label_color(window, 0) == before


def test_selected_row_is_one_colour(window, qt_app):
    """선택 줄은 일반 칸과 직접 그리는 칸(관계 · 참석 · 식권 · 발송)이 같은 색이다.

    예전에는 두 곳이 같은 색 값을 따로 들고 있어(테마 · 델리게이트) 한쪽만 바꾸면 줄무늬가 졌다.
    이제 델리게이트는 표의 선택색을 그대로 쓴다.
    """
    window._table.selectRow(0)
    qt_app.processEvents()
    image = window._table.viewport().grab().toImage()
    y = cell_rect(window, 0, Column.NAME).top() + 3  # 배지 · 글자를 피한 칸 위쪽 가장자리
    colours = {
        column.name: image.pixelColor(cell_rect(window, 0, column).left() + 3, y).name()
        for column in (Column.NAME, Column.RELATION, Column.ATTENDANCE, Column.ADULT_TICKETS, Column.SENT)
    }
    assert len(set(colours.values())) == 1, colours
