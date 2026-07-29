"""식권 표기 파싱 회귀 테스트.

실제 명단 225건을 검증하다 겪은 사고를 고정한다.
하객 성명에 `대인` 이 들어 있었고, 그 두 글자가 식권 표기로 오인되어

* 금액 50,000원이 0원으로 사라지고
* 대인 식권이 1장에서 50장으로 부풀고
* 순 정산금이 2,745,000원 틀어졌다.

아래 이름·소속은 모두 가명이다. 실제 데이터는 테스트에도 두지 않는다.
"""

from __future__ import annotations

import pytest

from chugui.models import WARN_NO_AMOUNT
from chugui.parsing.amount import extract_amount, strip_non_amount_numbers
from chugui.parsing.text_parser import parse_line, parse_text
from chugui.parsing.tickets import adult_tickets, child_tickets, strip_ticket_tokens
from chugui.services.settlement import settle


class TestNamesContainingTicketWords:
    """이름 속 '대인' / '소인' / '성인' 을 식권 수로 읽으면 안 된다."""

    @pytest.mark.parametrize(
        ("line", "amount", "adult"),
        [
            ("홍대인\t50,000\tOO기업 충청사업소", 50_000, 1),
            ("홍대인 50,000 OO기업", 50_000, 1),
            ("홍대인 10만원 회사", 100_000, 1),
            ("홍소인 100,000 교회", 100_000, 1),
            ("홍성인 200,000 친척", 200_000, 1),
            ("홍식대 50,000 지인", 50_000, 1),
            ("홍아이 100,000 대학동기", 100_000, 1),
        ],
    )
    def test_amount_and_tickets_survive(self, line, amount, adult):
        guest = parse_line(line)
        assert guest.amount == amount
        assert guest.adult_tickets == adult
        assert guest.child_tickets == 0
        assert WARN_NO_AMOUNT not in guest.warnings

    def test_ticket_words_in_name_are_not_ticket_counts(self):
        assert adult_tickets("홍대인\t50,000\tOO기업") is None
        assert adult_tickets("홍대인 10만원") is None
        assert child_tickets("홍소인 100,000") is None

    def test_stripper_leaves_the_amount_alone(self):
        assert "50,000" in strip_non_amount_numbers("홍대인\t50,000\tOO기업")
        assert extract_amount("홍대인\t50,000\tOO기업")[0] == 50_000


class TestRealTicketNotationStillWorks:
    """경계 조건을 넣었어도 문서화된 표기는 그대로 동작해야 한다."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("최동료 10만 식권2", 2),
            ("최동료 10만 식권 2", 2),
            ("최동료 10만 식권:2", 2),
            ("최동료 10만 대인2", 2),
            ("최동료 10만 성인 3", 3),
            ("최동료 10만 식권 2장", 2),
            ("최동료 10만원식권2", 2),  # 붙여쓰기 - 단위 뒤 경계는 허용한다
            ("최동료 10만 식권12", 12),
        ],
    )
    def test_adult_notation(self, text, expected):
        assert adult_tickets(text) == expected
        assert parse_line(text).adult_tickets == expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("정삼촌 30만 소인1", 1),
            ("정삼촌 30만 소인 2", 2),
            ("정삼촌 30만 어린이1", 1),
            ("정삼촌 30만 아동 2", 2),
        ],
    )
    def test_child_notation(self, text, expected):
        assert child_tickets(text) == expected

    def test_both_together(self):
        guest = parse_line("김선배 500,000 회사 선배 식권2 소인1")
        assert (guest.amount, guest.adult_tickets, guest.child_tickets) == (500_000, 2, 1)

    def test_amount_is_not_eaten_by_ticket_strip(self):
        assert extract_amount("최동료 10만 식권2 소인1")[0] == 100_000

    def test_strip_removes_ticket_tokens(self):
        assert "식권" not in strip_ticket_tokens("최동료 10만 식권2")
        assert "소인" not in strip_ticket_tokens("최동료 10만 소인1")


class TestTabSeparatedList:
    """엑셀·한글에서 복사한 탭 구분 명단(가명)."""

    RAW = (
        "홍대인\t50,000\tOO기업 충청사업소\n"
        "홍길동\t200,000\t큰집\n"
        "김가족,김친지\t300,000\t이모\n"
        "박지성\t100,000\t천안\n"
        "이영희\t50,000\t온양5동\n"
        "최동욱\t100,000\t세교4리\n"
        "강수진\t1,000,000\t서울이모\n"
        "임재현\t2,000,000\t친척\n"
        "조은지\t70,000\tOO교회 사랑부\n"
    )

    def test_every_amount_is_exact(self):
        amounts = [g.amount for g in parse_text(self.RAW)]
        assert amounts == [
            50_000, 200_000, 300_000, 100_000, 50_000, 100_000, 1_000_000, 2_000_000, 70_000
        ]

    def test_total_matches_hand_sum(self):
        assert sum(g.amount for g in parse_text(self.RAW)) == 3_870_000

    def test_place_names_are_not_read_as_units(self):
        """'천안'의 '천', '온양5동'의 5, '세교4리'의 4가 금액에 섞이면 안 된다."""
        by_name = {g.name: g for g in parse_text(self.RAW)}
        assert by_name["박지성"].amount == 100_000
        assert by_name["이영희"].amount == 50_000
        assert by_name["최동욱"].amount == 100_000

    def test_ticket_count_equals_head_count(self):
        for guest in parse_text(self.RAW):
            assert guest.adult_tickets == guest.head_count

    def test_settlement_is_exact(self):
        guests = parse_text(self.RAW)
        result = settle(guests, 55_000, 30_000)
        assert result.total_amount == 3_870_000
        assert result.adult_tickets == 10          # 부부 1건 포함
        assert result.meal_cost == 10 * 55_000
        assert result.net_amount == 3_870_000 - 550_000


class TestGroupDonor:
    """단체 명의는 '하객83' 이 아니라 그 이름을 쓴다."""

    def test_group_name_is_used(self):
        guest = parse_line("사랑교회청년부\t50,000\t사랑교회청년부", 83)
        assert guest.name == "사랑교회청년부"
        assert guest.amount == 50_000

    def test_group_name_is_still_flagged(self):
        """사람 이름인지 확신할 수 없으므로 확인 대상으로 남긴다."""
        assert parse_line("사랑교회청년부\t50,000\t사랑교회청년부", 83).needs_review is True

    def test_plain_org_line_keeps_amount(self):
        guest = parse_line("청년회 100,000", 5)
        assert (guest.name, guest.amount) == ("청년회", 100_000)
