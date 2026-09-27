"""v2.1.1 파서 정확도 회귀 테스트.

전부 경고 없이 **조용히** 틀리던 사례다. 조용한 오답은 사용자가 찾을 방법이 없다.
"""

from __future__ import annotations

import pytest

from chugui.models import Payment, Relation
from chugui.parsing.amount import extract_amount
from chugui.parsing.excel_parser import parse_rows
from chugui.parsing.text_parser import parse_line


class TestDecimalAmounts:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1.5만원", 15_000),  # 예전: '1' 과 '5만' 으로 쪼개져 50,000
            ("0.5만", 5_000),
            ("2.5십만", 250_000),
            ("1.2억", 120_000_000),
            ("100.000원", 100_000),  # 점을 천 단위 구분자로 쓴 표기
            ("1.000.000", 1_000_000),
        ],
    )
    def test_decimal_and_dot_thousands(self, text, expected):
        assert extract_amount(text)[0] == expected

    def test_date_with_dots_is_still_ignored(self):
        assert extract_amount("홍길동 5만원 (2025.10.03)")[0] == 50_000


class TestNames:
    @pytest.mark.parametrize(
        ("line", "names"),
        [
            ("김철수 , 이영희 20만", ["김철수", "이영희"]),
            ("김철수, 이영희 20만", ["김철수", "이영희"]),
            ("홍길동, 5만원", ["홍길동"]),
            ("홍길동님 10만원", ["홍길동"]),
            ("홍길동씨 5만", ["홍길동"]),
            ("[홍길동] 5만원", ["홍길동"]),
            ("홍길동:50000", ["홍길동"]),
            ("홍길동-50000", ["홍길동"]),
            ("친구 김민지 5만", ["김민지"]),
            ("이모 박순자 10만", ["박순자"]),
            ("신부측 김민지 5만", ["김민지"]),
        ],
    )
    def test_extracted_names(self, line, names):
        guest = parse_line(line)
        assert guest.names == names
        assert not guest.warnings

    def test_couple_gets_two_tickets(self):
        assert parse_line("김철수 , 이영희 20만").adult_tickets == 2

    def test_message_does_not_double_honorific(self):
        assert parse_line("홍길동님 10만원").name == "홍길동"


class TestRelations:
    def test_bride_side_is_not_clergy(self):
        assert parse_line("김민지\t50000\t신부측 대학동기").relation is Relation.SCHOOL
        assert parse_line("홍길동(신부측) 5만").relation is Relation.OTHER

    def test_priest_still_recognized(self):
        assert parse_line("홍길동 10만 신부님").relation is Relation.FAITH

    def test_keyword_inside_real_name_is_ignored(self):
        assert parse_line("이사랑 5만원").relation is Relation.OTHER

    @pytest.mark.parametrize(
        ("line", "relation"),
        [("김부장 10만", Relation.WORK), ("박이모 10만", Relation.FAMILY), ("최동료 10만", Relation.WORK)],
    )
    def test_surname_plus_title_keeps_relation(self, line, relation):
        assert parse_line(line).relation is relation

    def test_spreadsheet_ignores_keyword_inside_name(self):
        guests = parse_rows([["성명", "금액"], ["이사랑", "50000"]])
        assert guests[0].relation is Relation.OTHER


def test_pay_apps_are_transfers():
    assert parse_line("홍길동 5만원 카카오페이").payment is Payment.TRANSFER
    assert Payment.coerce("네이버페이") is Payment.TRANSFER
