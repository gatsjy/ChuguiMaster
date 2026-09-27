"""텍스트로 내보내기.

카톡으로 가족에게 보내거나 메모장에 보관할 수 있는 글 형태로 명단과 정산을 뽑는다.

설계 원칙 하나: **뽑은 글을 입력창에 그대로 붙여넣으면 다시 같은 명단이 된다.**

* 정산 요약 줄은 ``#`` 으로 시작한다. 텍스트 파서가 주석으로 보고 건너뛴다.
* 명단 줄은 열을 두 칸 이상 띄어 쓴다. 파서가 표 형식으로 읽어 이름 · 금액을
  정확한 열에서 고른다.
* 관계 · 불참 · 계좌 · 식권은 파서가 알아듣는 낱말로 적는다.

발송 여부처럼 파서가 되읽을 수 없는 값은 적지 않는다(적어도 소속 칸으로 들어가 섞인다).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from chugui.models import Attendance, Guest, Payment
from chugui.services.settlement import Settlement

_SEP = "  "  # 파서가 열 구분으로 보는 최소 간격


def _default_adult_tickets(guest: Guest) -> int:
    """파서가 식권 표기가 없을 때 채우는 값. 이와 같으면 굳이 적지 않는다."""
    return guest.head_count if guest.is_present else 0


def format_guest_line(guest: Guest) -> str:
    """하객 한 명을 파서가 되읽을 수 있는 한 줄로."""
    names = ",".join(guest.names) if guest.names else guest.name
    parts = [f"{guest.guest_id}. {names}", f"{guest.amount:,}원", guest.relation.value]
    if guest.attendance is Attendance.ABSENT:
        parts.append("불참")
    if guest.payment is Payment.TRANSFER:
        parts.append("계좌")
    if guest.adult_tickets != _default_adult_tickets(guest) or guest.child_tickets:
        tickets = f"식권{guest.adult_tickets}"
        if guest.child_tickets:
            tickets += f" 소인{guest.child_tickets}"
        parts.append(tickets)
    for extra in (guest.belong, guest.note):
        if extra.strip():
            parts.append(extra.strip())
    return _SEP.join(parts)


def export_text(
    guests: Sequence[Guest],
    settlement: Settlement,
    today: date | None = None,
) -> str:
    """명단 + 정산 요약 글."""
    s = settlement
    day = (today or date.today()).isoformat()
    lines = [
        f"# 축의금 정산 ({day})",
        f"# 총 축의금 {s.total_amount:,}원 · {s.guest_count}건 {s.head_count}명"
        f" (현금 {s.cash_amount:,} · 계좌 {s.transfer_amount:,})",
        f"# 총 식대 {s.meal_cost:,}원 = 대인 {s.adult_tickets}장 × {s.adult_unit_cost:,}"
        f" + 소인 {s.child_tickets}장 × {s.child_unit_cost:,}",
        f"# 최종 순 정산금 {s.net_amount:,}원",
    ]
    if s.review_count:
        lines.append(f"# 확인 필요 {s.review_count}건")
    lines.append("#")
    lines.extend(format_guest_line(guest) for guest in guests)
    return "\n".join(lines) + "\n"
