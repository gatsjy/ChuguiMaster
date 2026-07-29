"""식대 차감 정산.

구버전의 계산식은 이랬다::

    total_meal_fee = total_guests * adult_cost   # 하객 "명" 수 x 대인 단가

README 명세(``총 축의금 - 식대 x 발급된 식권 수``)와 전혀 다르다. 그 결과

* ``식권2`` 파싱 결과가 한 번도 쓰이지 않았고,
* 소인 단가 입력칸이 계산에 전혀 반영되지 않는 장식이었으며,
* 오지도 않은 불참 하객에게까지 식대가 차감됐다.

여기서는 명세대로 **발급된 식권 수 기준**으로 계산한다.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from chugui.models import Guest

DEFAULT_ADULT_MEAL = 42_000
DEFAULT_CHILD_MEAL = 25_000


@dataclass(frozen=True)
class Settlement:
    """정산 결과 스냅샷. 불변이라 UI 어디서든 안전하게 들고 다닐 수 있다."""

    total_amount: int = 0
    guest_count: int = 0
    head_count: int = 0
    attendee_count: int = 0
    absentee_count: int = 0
    adult_tickets: int = 0
    child_tickets: int = 0
    adult_unit_cost: int = DEFAULT_ADULT_MEAL
    child_unit_cost: int = DEFAULT_CHILD_MEAL
    meal_cost: int = 0
    net_amount: int = 0
    review_count: int = 0
    sent_count: int = 0
    cash_amount: int = 0
    transfer_amount: int = 0

    @property
    def average_amount(self) -> int:
        return self.total_amount // self.guest_count if self.guest_count else 0

    @property
    def sent_ratio(self) -> float:
        return self.sent_count / self.guest_count if self.guest_count else 0.0


def settle(
    guests: Sequence[Guest] | Iterable[Guest],
    adult_unit_cost: int = DEFAULT_ADULT_MEAL,
    child_unit_cost: int = DEFAULT_CHILD_MEAL,
) -> Settlement:
    """하객 목록으로부터 정산 결과를 계산한다.

    식대는 **발급된 식권 수**에만 부과된다. 불참 하객의 식권은 파서가
    0으로 두므로 자연스럽게 제외된다.
    """
    from chugui.models import Attendance, Payment  # 지역 import: 순환 참조 방지

    guest_list = list(guests)
    adult_unit_cost = max(0, int(adult_unit_cost))
    child_unit_cost = max(0, int(child_unit_cost))

    total_amount = sum(guest.amount for guest in guest_list)
    adult_tickets = sum(guest.adult_tickets for guest in guest_list)
    child_tickets = sum(guest.child_tickets for guest in guest_list)
    meal_cost = adult_tickets * adult_unit_cost + child_tickets * child_unit_cost

    attendee_count = sum(1 for guest in guest_list if guest.attendance is Attendance.PRESENT)

    return Settlement(
        total_amount=total_amount,
        guest_count=len(guest_list),
        head_count=sum(guest.head_count for guest in guest_list),
        attendee_count=attendee_count,
        absentee_count=len(guest_list) - attendee_count,
        adult_tickets=adult_tickets,
        child_tickets=child_tickets,
        adult_unit_cost=adult_unit_cost,
        child_unit_cost=child_unit_cost,
        meal_cost=meal_cost,
        net_amount=total_amount - meal_cost,
        review_count=sum(1 for guest in guest_list if guest.needs_review),
        sent_count=sum(1 for guest in guest_list if guest.sent_thanks),
        cash_amount=sum(g.amount for g in guest_list if g.payment is Payment.CASH),
        transfer_amount=sum(g.amount for g in guest_list if g.payment is Payment.TRANSFER),
    )
