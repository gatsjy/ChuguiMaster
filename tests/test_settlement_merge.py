"""정산 · 병합 테스트."""

from __future__ import annotations

from chugui.models import Attendance, Guest, Payment
from chugui.parsing.text_parser import parse_text
from chugui.services.merge import merge_guests, normalize_name
from chugui.services.settlement import settle


def guest(name: str, amount: int, adult: int = 1, child: int = 0, **kwargs) -> Guest:
    return Guest(name=name, names=[name], amount=amount, adult_tickets=adult, child_tickets=child, **kwargs)


class TestSettlementFormula:
    """v1: ``total_guests * adult_cost`` — 식권 수도, 소인 단가도 쓰지 않았다."""

    def test_uses_ticket_count_not_guest_count(self):
        guests = [guest("홍길동", 300_000, adult=2), guest("김철수", 100_000, adult=1)]
        result = settle(guests, adult_unit_cost=50_000, child_unit_cost=30_000)
        assert result.adult_tickets == 3
        assert result.meal_cost == 150_000       # v1이라면 2명 x 50,000 = 100,000
        assert result.net_amount == 250_000

    def test_child_unit_cost_is_actually_used(self):
        """v1에서 소인 단가 입력칸은 계산에 전혀 반영되지 않는 장식이었다."""
        guests = [guest("홍길동", 300_000, adult=2, child=1)]
        result = settle(guests, adult_unit_cost=50_000, child_unit_cost=30_000)
        assert result.meal_cost == 2 * 50_000 + 1 * 30_000
        assert result.net_amount == 300_000 - 130_000

    def test_absentee_is_not_charged(self):
        guests = [
            guest("홍길동", 100_000, adult=1),
            guest("박지성", 100_000, adult=0, attendance=Attendance.ABSENT),
        ]
        result = settle(guests, adult_unit_cost=50_000)
        assert result.meal_cost == 50_000
        assert result.attendee_count == 1
        assert result.absentee_count == 1

    def test_matches_readme_formula_on_sample(self):
        guests = parse_text("홍길동 300000 친척 식권2 소인1\n김철수 100000 친구 불참")
        result = settle(guests, 55_000, 30_000)
        expected_meal = sum(g.adult_tickets * 55_000 + g.child_tickets * 30_000 for g in guests)
        assert result.meal_cost == expected_meal
        assert result.net_amount == result.total_amount - expected_meal


class TestSettlementAggregates:
    def test_empty(self):
        result = settle([])
        assert (result.total_amount, result.guest_count, result.net_amount) == (0, 0, 0)
        assert result.average_amount == 0

    def test_payment_split(self):
        guests = [
            guest("홍길동", 100_000, payment=Payment.CASH),
            guest("김철수", 200_000, payment=Payment.TRANSFER),
        ]
        result = settle(guests, 0, 0)
        assert (result.cash_amount, result.transfer_amount) == (100_000, 200_000)

    def test_review_and_sent_counts(self):
        a = guest("홍길동", 0)
        a.add_warning("금액을 찾지 못했습니다")
        b = guest("김철수", 100_000, sent_thanks=True)
        result = settle([a, b])
        assert (result.review_count, result.sent_count) == (1, 1)

    def test_negative_net_is_reported_as_is(self):
        result = settle([guest("홍길동", 30_000, adult=1)], adult_unit_cost=55_000)
        assert result.net_amount == -25_000


class TestMerge:
    """v1에는 병합 기능이 아예 없었다 - 새 데이터가 기존 목록을 덮어썼다."""

    def test_appends_instead_of_replacing(self):
        cash = parse_text("홍길동 100000 친척\n김철수 50000 친구")
        bank = [guest("이영희", 300_000)]
        result = merge_guests(cash, bank)
        assert len(result.guests) == 3
        assert result.added == 1
        assert [g.guest_id for g in result.guests] == [1, 2, 3]

    def test_duplicate_is_flagged_not_dropped(self):
        existing = [guest("홍길동", 100_000)]
        incoming = [guest("홍길동", 200_000)]
        result = merge_guests(existing, incoming)
        assert len(result.guests) == 2          # 돈이 걸린 문제라 삼키지 않는다
        assert result.duplicate_count == 1
        assert all(g.needs_review for g in result.guests)

    def test_exact_duplicate_can_be_skipped(self):
        existing = [guest("홍길동", 100_000)]
        incoming = [guest("홍길동", 100_000)]
        result = merge_guests(existing, incoming, skip_exact_duplicates=True)
        assert len(result.guests) == 1
        assert result.added == 0

    def test_name_normalization(self):
        assert normalize_name("김가족 & 김친지") == "김가족김친지"
        assert normalize_name(" 홍 길 동 ") == "홍길동"

    def test_matches_on_member_name(self):
        existing = [Guest(name="김가족 & 김친지", names=["김가족", "김친지"], amount=300_000)]
        result = merge_guests(existing, [guest("김친지", 100_000)])
        assert result.duplicate_count == 1

    def test_empty_merge_is_noop(self):
        existing = [guest("홍길동", 100_000)]
        result = merge_guests(existing, [])
        assert len(result.guests) == 1
        assert result.added == 0
