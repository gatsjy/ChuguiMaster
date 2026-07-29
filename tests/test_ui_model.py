"""표 모델 / 프록시 테스트 (오프스크린 Qt)."""

from __future__ import annotations

import pytest

from chugui.models import WARN_NO_AMOUNT, Attendance, Guest, Relation

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from chugui.services.messages import MessageService
from chugui.ui.guest_model import GUEST_ROLE, Column, GuestFilterProxy, GuestTableModel


@pytest.fixture
def model(qt_app):
    table_model = GuestTableModel(MessageService())
    table_model.set_guests(
        [
            Guest(name="홍길동", names=["홍길동"], amount=200_000, relation=Relation.FAMILY, adult_tickets=1),
            Guest(name="김철수", names=["김철수"], amount=50_000, relation=Relation.SCHOOL, adult_tickets=1),
            Guest(name="박지성", names=["박지성"], amount=0, relation=Relation.OTHER,
                  attendance=Attendance.ABSENT, warnings=[WARN_NO_AMOUNT]),
        ]
    )
    return table_model


class TestModelBasics:
    def test_dimensions(self, model):
        assert model.rowCount() == 3
        assert model.columnCount() == len(Column)

    def test_ids_are_renumbered(self, model):
        assert [g.guest_id for g in model.guests] == [1, 2, 3]

    def test_amount_display_is_formatted(self, model):
        index = model.index(0, Column.AMOUNT)
        assert model.data(index, Qt.ItemDataRole.DisplayRole) == "200,000"
        assert model.data(index, Qt.ItemDataRole.EditRole) == 200_000  # 숫자 정렬용

    def test_guest_role_exposes_object(self, model):
        assert model.data(model.index(0, Column.RELATION), GUEST_ROLE) is model.guests[0]

    def test_invalid_index_is_safe(self, model):
        from PySide6.QtCore import QModelIndex

        assert model.data(QModelIndex()) is None
        assert model.guest_at(99) is None


class TestEditingPersists:
    """v1은 표에서 셀을 고쳐도 모델에 반영되지 않아 다음 렌더링 때 조용히 원복됐다."""

    def test_name_edit_is_written_back(self, model):
        assert model.setData(model.index(0, Column.NAME), "홍길순") is True
        assert model.guests[0].name == "홍길순"

    def test_amount_edit_accepts_korean_units(self, model):
        model.setData(model.index(1, Column.AMOUNT), "10만원")
        assert model.guests[1].amount == 100_000

    def test_amount_edit_clears_warning(self, model):
        model.setData(model.index(2, Column.AMOUNT), "50,000")
        assert model.guests[2].amount == 50_000
        assert model.guests[2].needs_review is False

    def test_relation_edit_changes_message(self, model):
        before = model.message_for(0)
        model.setData(model.index(0, Column.RELATION), Relation.SCHOOL.value)
        assert model.guests[0].relation is Relation.SCHOOL
        assert model.message_for(0) != before

    def test_attendance_to_absent_zeroes_tickets(self, model):
        model.setData(model.index(0, Column.ATTENDANCE), Attendance.ABSENT.value)
        assert model.guests[0].adult_tickets == 0

    def test_attendance_back_to_present_restores_ticket(self, model):
        model.setData(model.index(2, Column.ATTENDANCE), Attendance.PRESENT.value)
        assert model.guests[2].adult_tickets == 1

    def test_ticket_edit_is_clamped(self, model):
        model.setData(model.index(0, Column.ADULT_TICKETS), 500)
        assert model.guests[0].adult_tickets == 99

    def test_empty_name_is_rejected(self, model):
        assert model.setData(model.index(0, Column.NAME), "   ") is False
        assert model.guests[0].name == "홍길동"

    def test_readonly_columns_reject_edits(self, model):
        assert model.setData(model.index(0, Column.RAW), "변조") is False


class TestCheckState:
    def test_toggle_sent(self, model):
        index = model.index(0, Column.SENT)
        assert model.data(index, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked
        model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        assert model.guests[0].sent_thanks is True

    def test_mark_sent_helper(self, model):
        model.mark_sent(1, True)
        assert model.guests[1].sent_thanks is True


class TestSignals:
    def test_guests_changed_fires_on_edit(self, model):
        received = []
        model.guestsChanged.connect(lambda: received.append(1))
        model.setData(model.index(0, Column.NAME), "새이름")
        assert received


class TestFilterProxy:
    @pytest.fixture
    def proxy(self, model):
        filter_proxy = GuestFilterProxy()
        filter_proxy.setSourceModel(model)
        return filter_proxy

    def test_no_filter_shows_all(self, proxy):
        assert proxy.rowCount() == 3

    def test_search_by_name(self, proxy):
        proxy.set_query("홍길")
        assert proxy.rowCount() == 1

    def test_search_is_case_insensitive_and_trimmed(self, proxy):
        proxy.set_query("  김철수 ")
        assert proxy.rowCount() == 1

    def test_relation_filter(self, proxy):
        proxy.set_relation(Relation.FAMILY)
        assert proxy.rowCount() == 1

    def test_review_only(self, proxy):
        proxy.set_review_only(True)
        assert proxy.rowCount() == 1

    def test_unsent_only(self, proxy, model):
        model.mark_sent(0, True)
        proxy.set_unsent_only(True)
        assert proxy.rowCount() == 2

    def test_filters_combine(self, proxy):
        proxy.set_relation(Relation.FAMILY)
        proxy.set_query("김철수")
        assert proxy.rowCount() == 0

    def test_clearing_query_restores_rows(self, proxy):
        proxy.set_query("홍길")
        proxy.set_query("")
        assert proxy.rowCount() == 3


class TestSorting:
    def test_amount_sorts_numerically(self, model, qt_app):
        proxy = GuestFilterProxy()
        proxy.setSourceModel(model)
        proxy.sort(int(Column.AMOUNT), Qt.SortOrder.DescendingOrder)
        first = proxy.data(proxy.index(0, Column.NAME), Qt.ItemDataRole.DisplayRole)
        assert first == "홍길동"  # 문자열 정렬이면 "50,000"이 앞에 온다

    def test_default_view_order_is_input_order(self, qt_app):
        """Qt의 setSortingEnabled(True)는 0번 열 내림차순이 기본이라
        그대로 두면 명단이 역순으로 보인다."""
        from chugui.parsing.text_parser import parse_text
        from chugui.ui.main_window import MainWindow

        window = MainWindow()
        try:
            window._model.set_guests(parse_text("홍길동 10만\n김철수 5만\n이영희 30만"))
            proxy = window._proxy
            shown = [
                proxy.data(proxy.index(row, Column.NO), Qt.ItemDataRole.DisplayRole)
                for row in range(proxy.rowCount())
            ]
            assert shown == [1, 2, 3]
        finally:
            window.close()
