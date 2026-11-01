"""사람들이 실제로 적는 방식. 전부 예전에는 조용히 틀리거나 읽지 못하던 줄이다."""

from __future__ import annotations

import pytest

from chugui.parsing.amount import extract_amount, hangul_amount
from chugui.parsing.excel_parser import parse_rows
from chugui.parsing.text_parser import parse_line
from chugui.services.exporter import export_to_excel
from chugui.services.settlement import settle


class TestStrayNumbers:
    """'10만 아기1' 의 1 이 금액에 붙어 100,001원이 됐다."""

    @pytest.mark.parametrize(
        ("line", "amount"),
        [
            ("홍길동 10만 아기1", 100_000),
            ("홍길동 10만원 답례품 2", 100_000),
            ("홍길동 10만 테이블3", 100_000),
            ("홍길동 10만 5000원", 105_000),  # 진짜 합산은 유지
            ("홍길동 10만 500원", 100_500),
            ("홍길동 10만 5천", 105_000),
        ],
    )
    def test_amount(self, line, amount):
        assert parse_line(line).amount == amount

    def test_balance_is_not_the_gift(self):
        """입금 알림을 붙여넣으면 잔액이 더 커서 금액으로 뽑혔다."""
        guest = parse_line("홍길동 100,000원 입금 잔액 2,500,000원")
        assert guest.amount == 100_000
        assert not guest.warnings

    def test_sentence_ending(self):
        assert parse_line("홍길동 10만원입니다").amount == 100_000
        assert parse_line("홍길동 10만원이요").amount == 100_000


class TestHangulAmounts:
    @pytest.mark.parametrize(
        ("text", "amount"),
        [
            ("오만원", 50_000),
            ("십만원", 100_000),
            ("십오만원", 150_000),
            ("삼십만원", 300_000),
            ("이백만원", 2_000_000),
            ("만원", 10_000),
            ("오천원", 5_000),
            ("일억원", 100_000_000),
            ("이십만 원", 200_000),
        ],
    )
    def test_value(self, text, amount):
        assert extract_amount(text)[0] == amount

    @pytest.mark.parametrize("text", ["이천", "오만", "오삼만원", "이원", "백원", "일이삼"])
    def test_not_money(self, text):
        assert hangul_amount(text) == 0

    def test_digits_win_over_words(self):
        assert extract_amount("오만원 100,000")[0] == 100_000

    def test_written_amount_is_not_the_name(self):
        guest = parse_line("오만원 홍길동")
        assert guest.name == "홍길동"
        assert guest.amount == 50_000

    def test_city_stays_a_word(self):
        """'이천' 은 지명이다. '원' 이 없으면 금액으로 읽지 않는다."""
        guest = parse_line("홍길동 5만원 이천")
        assert guest.amount == 50_000
        assert not guest.warnings


class TestGluedName:
    def test_name_without_space(self):
        guest = parse_line("홍길동10만원")
        assert (guest.name, guest.amount) == ("홍길동", 100_000)
        assert not guest.warnings

    def test_place_with_digit_is_left_alone(self):
        assert parse_line("홍길동 5만원 새내4리").name == "홍길동"
        assert parse_line("새내4리 홍길동 5만원").name == "홍길동"


class TestStatedHeadcount:
    """인원을 적었는데 이름이 하나라는 이유로 식권 1장으로 쳐서 식대가 덜 잡혔다."""

    @pytest.mark.parametrize(
        ("line", "tickets"),
        [
            ("김철수 부부 20만원", 2),
            ("김철수 내외 20만원", 2),
            ("홍길동 10만원 3명", 3),
            ("홍길동 10만원 2인", 2),
            ("홍길동 외 2명 10만원", 3),
            ("김철수,이영희 외 1명 30만", 3),
            ("김철수,이영희 20만", 2),  # 이름 두 개는 그대로
            ("홍길동 10만원", 1),
        ],
    )
    def test_adult_tickets(self, line, tickets):
        assert parse_line(line).adult_tickets == tickets

    def test_explicit_tickets_win(self):
        assert parse_line("홍길동 10만원 3명 식권2").adult_tickets == 2

    def test_child_count_is_not_headcount(self):
        guest = parse_line("홍길동 10만원 소인 2명")
        assert (guest.adult_tickets, guest.child_tickets) == (1, 2)

    def test_absent_guest_gets_no_tickets(self):
        assert parse_line("김철수 부부 20만원 불참").adult_tickets == 0

    @pytest.mark.parametrize("word", ["아기", "애기", "아이", "유아"])
    def test_child_words(self, word):
        assert parse_line(f"홍길동 10만 {word}1").child_tickets == 1


class TestSpreadsheetEdges:
    def test_file_without_header_keeps_first_guest(self):
        """제목 줄이 없으면 첫 하객이 제목이 되어 사라지고 나머지는 금액을 못 읽었다."""
        guests = parse_rows([["홍길동", "100000", "이모"], ["김철수", "50000", "회사"]])
        assert [(g.name, g.amount) for g in guests] == [("홍길동", 100_000), ("김철수", 50_000)]

    def test_ticket_cell_with_decimal(self):
        """숫자만 이어붙여 '2.0' 이 20장(= 식대 84만원)이 됐다."""
        guests = parse_rows([["성명", "금액", "식권"], ["홍길동", "100000", "2.0"]])
        assert guests[0].adult_tickets == 2

    def test_ticket_cell_with_unit(self):
        guests = parse_rows([["성명", "금액", "식권"], ["홍길동", "100000", "3장"]])
        assert guests[0].adult_tickets == 3


def test_exported_text_is_never_a_formula(tmp_path):
    """보낸 사람 칸은 누구나 적을 수 있다. 내보낸 파일을 열 때 수식이 실행되면 안 된다."""
    from openpyxl import load_workbook

    guests = [parse_line("홍길동 5만원")]
    guests[0].name = '=HYPERLINK("http://example.com","클릭")'
    guests[0].note = "=1+1"
    path = tmp_path / "x.xlsx"
    export_to_excel(path, guests, settle(guests))
    row = load_workbook(path)["축의금 명단"][2]
    assert all(cell.data_type != "f" for cell in row)
    assert row[1].value == guests[0].name
