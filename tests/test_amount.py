"""금액 파서 회귀 테스트.

v1의 6배 오류(``"1 홍길동 200000 친척모임"`` → 1,200,000원)는
이 파일의 첫 번째 테스트 하나만 있었어도 첫날 잡혔을 버그다.
"""

from __future__ import annotations

import pytest

from chugui.parsing.amount import extract_amount, parse_amount


class TestLeadingRowNumber:
    """v1 최악의 버그: 줄번호가 금액에 이어붙었다."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("1 홍길동 200000 친척모임", 200_000),
            ("5 최동료 100000 A보건지소", 100_000),
            ("10 박대현 1000000 고모", 1_000_000),
            ("26 진부부,신부부 100000", 100_000),
            ("3. 이영희 300,000 이모", 300_000),
            ("27) 권집사 100000 OO교회", 100_000),
        ],
    )
    def test_row_number_is_not_part_of_amount(self, line, expected):
        assert extract_amount(line)[0] == expected


class TestKoreanUnits:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("10만원", 100_000),
            ("10만", 100_000),
            ("100,000", 100_000),
            ("100000", 100_000),
            ("5만원", 50_000),
            ("10만 5천원", 105_000),
            ("10만5천", 105_000),
            ("10만 5000원", 105_000),
            ("3억 2천만원", 320_000_000),
            ("1백만원", 1_000_000),
            ("2천만", 20_000_000),
        ],
    )
    def test_unit_expressions(self, text, expected):
        assert extract_amount(text)[0] == expected


class TestTicketsAreNotAmounts:
    """식권/소인 숫자가 금액에 흡수되면 안 된다."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("최동료 10만 식권2", 100_000),
            ("정삼촌 300000 삼촌 식권2 소인1", 300_000),
            ("김선배 500,000 회사 선배 식권2 소인1", 500_000),
            ("이웃 50000 대인1", 50_000),
        ],
    )
    def test_ticket_counts_excluded(self, line, expected):
        assert extract_amount(line)[0] == expected


class TestNoisyNumbers:
    """은행 내역에 섞여 오는 날짜/전화/계좌번호."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("2025-03-14 홍길동 100,000", 100_000),
            ("2025.03.14 14:30 김철수 50,000", 50_000),
            ("홍길동 010-1234-5678 100000", 100_000),
            ("110-123-456789 이영희 300000", 300_000),
        ],
    )
    def test_dates_phones_accounts_excluded(self, line, expected):
        assert extract_amount(line)[0] == expected


class TestNoSilentGuessing:
    """v1은 1,000 미만 숫자를 만원 단위로 승격시켰다(500 → 500만원)."""

    @pytest.mark.parametrize("text", ["500", "홍길동 5 친척", "박지성 12"])
    def test_bare_small_numbers_are_not_amounts(self, text):
        amount, candidates = extract_amount(text)
        assert amount == 0
        assert candidates == []

    def test_empty_and_garbage(self):
        assert extract_amount("")[0] == 0
        assert extract_amount("이백만원")[0] == 0  # 한글 수사는 지원하지 않음(경고 대상)
        assert extract_amount("홍길동 친척")[0] == 0


class TestCandidates:
    def test_multiple_candidates_are_reported(self):
        amount, candidates = extract_amount("홍길동 100,000 그리고 50,000")
        assert amount == 100_000
        assert sorted(candidates) == [50_000, 100_000]

    def test_single_candidate(self):
        amount, candidates = extract_amount("홍길동 10만원 친척")
        assert (amount, candidates) == (100_000, [100_000])


class TestParseAmountCell:
    """스프레드시트 셀 파싱."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (100000, 100_000),
            (100000.0, 100_000),
            ("100,000", 100_000),
            ("100000원", 100_000),
            ("10만원", 100_000),
            (None, 0),
            ("", 0),
            ("-", 0),
            (True, 0),
        ],
    )
    def test_cell_values(self, value, expected):
        assert parse_amount(value) == expected
