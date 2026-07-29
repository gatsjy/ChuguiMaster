"""자유 텍스트 파서 통합 테스트."""

from __future__ import annotations

import pytest

from chugui.models import WARN_NO_AMOUNT, WARN_NO_NAME, Attendance, Payment, Relation
from chugui.parsing.text_parser import parse_line, parse_text
from chugui.samples import SAMPLE_TEXT


class TestReadmeDocumentedFormats:
    """README가 안내하는 양식은 전부 정확히 동작해야 한다."""

    @pytest.mark.parametrize(
        ("line", "name", "amount", "relation"),
        [
            ("홍길동 10만원 친척", "홍길동", 100_000, Relation.FAMILY),
            ("김철수 50,000 대학동기", "김철수", 50_000, Relation.SCHOOL),
            ("최동료 10만 식권2", "최동료", 100_000, Relation.WORK),  # '동료' → 직장
            ("박지성 5만원 불참", "박지성", 50_000, Relation.OTHER),
        ],
    )
    def test_basic_forms(self, line, name, amount, relation):
        guest = parse_line(line)
        assert guest is not None
        assert guest.name == name
        assert guest.amount == amount
        assert guest.relation is relation


class TestTickets:
    def test_explicit_tickets(self):
        guest = parse_line("정삼촌 300000 삼촌 식권2 소인1")
        assert (guest.adult_tickets, guest.child_tickets) == (2, 1)

    def test_default_one_ticket_for_attendee(self):
        guest = parse_line("홍길동 100000 친척")
        assert guest.adult_tickets == 1

    def test_couple_defaults_to_two_tickets(self):
        guest = parse_line("김가족,김친지 300000 이모")
        assert guest.adult_tickets == 2
        assert guest.head_count == 2

    def test_absentee_gets_no_ticket(self):
        """v1은 불참 하객에게도 식대를 차감했다."""
        guest = parse_line("박지성 100000 불참 송금")
        assert guest.attendance is Attendance.ABSENT
        assert (guest.adult_tickets, guest.child_tickets) == (0, 0)


class TestAttendanceAndPayment:
    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("홍길동 10만 친척", Attendance.PRESENT),
            ("홍길동 10만 불참", Attendance.ABSENT),
            ("홍길동 10만 송금", Attendance.ABSENT),
            ("홍길동 10만 참석 후 계좌송금", Attendance.PRESENT),
            ("홍길동 10만 못 와서 미안", Attendance.ABSENT),
        ],
    )
    def test_attendance(self, line, expected):
        assert parse_line(line).attendance is expected

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("홍길동 10만 친척", Payment.CASH),
            ("홍길동 10만 계좌이체", Payment.TRANSFER),
            ("홍길동 10만 토스 송금", Payment.TRANSFER),
        ],
    )
    def test_payment(self, line, expected):
        assert parse_line(line).payment is expected


class TestWarnings:
    """확신하지 못하면 조용히 추측하지 않고 표시한다."""

    def test_missing_amount_is_flagged(self):
        guest = parse_line("홍길동 친척")
        assert guest.amount == 0
        assert WARN_NO_AMOUNT in guest.warnings
        assert guest.needs_review is True

    def test_missing_name_is_flagged(self):
        guest = parse_line("OO교회 100000", 7)
        assert guest.name == "하객7"
        assert WARN_NO_NAME in guest.warnings

    def test_clean_line_has_no_warning(self):
        assert parse_line("홍길동 100,000 친척").needs_review is False


class TestBlankAndComments:
    @pytest.mark.parametrize("line", ["", "   ", "\t", "# 메모", "// 주석", "-----"])
    def test_ignored_lines(self, line):
        assert parse_line(line) is None


class TestParseText:
    def test_ids_are_sequential_without_gaps(self):
        guests = parse_text("홍길동 10만\n\n\n김철수 5만\n\n이영희 30만")
        assert [g.guest_id for g in guests] == [1, 2, 3]

    def test_sample_data_parses_exactly(self):
        """앱에 내장된 샘플이 첫 화면에서 틀린 숫자를 보여주면 안 된다."""
        guests = parse_text(SAMPLE_TEXT)
        assert len(guests) == 10

        by_name = {guest.name: guest for guest in guests}
        assert by_name["홍길동"].amount == 200_000
        assert by_name["김철수"].amount == 100_000
        assert by_name["이영희"].amount == 300_000
        assert by_name["최동욱"].amount == 500_000

        assert sum(guest.amount for guest in guests) == 2_000_000

    def test_sample_data_has_no_warnings(self):
        guests = parse_text(SAMPLE_TEXT)
        problems = {g.name: g.warnings for g in guests if g.needs_review}
        assert problems == {}
