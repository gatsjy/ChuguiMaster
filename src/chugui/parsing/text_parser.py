"""자유 텍스트(카톡/메모장) → Guest 변환."""

from __future__ import annotations

import re

from chugui.models import (
    WARN_AMBIGUOUS_AMOUNT,
    WARN_NO_AMOUNT,
    WARN_NO_NAME,
    Attendance,
    Guest,
    Payment,
    Source,
    renumber,
)
from chugui.parsing.amount import extract_amount
from chugui.parsing.names import extract_names, format_display_name
from chugui.parsing.relations import guess_relation
from chugui.parsing.tickets import adult_tickets as parse_adult_tickets
from chugui.parsing.tickets import child_tickets as parse_child_tickets

_ABSENT_RE = re.compile(r"불참|미참|못\s*오|못\s*와|못\s*참|결석")
_PRESENT_RE = re.compile(r"참석|참여|오심|왔음|방문")
_TRANSFER_RE = re.compile(r"계좌|이체|송금|토스|카카오\s*뱅크|카뱅|입금")
_COMMENT_RE = re.compile(r"^\s*(#|//|-{3,}|={3,})")


def _resolve_attendance(line: str) -> Attendance:
    """참석 여부 판정.

    '송금'은 보통 불참을 뜻하지만 '참석 후 계좌송금'도 존재한다.
    명시적 참석 표현이 있으면 그쪽을 신뢰한다.
    """
    if _ABSENT_RE.search(line):
        return Attendance.ABSENT
    if _PRESENT_RE.search(line):
        return Attendance.PRESENT
    if "송금" in line:
        return Attendance.ABSENT
    return Attendance.PRESENT


def parse_line(line: str, line_number: int = 1) -> Guest | None:
    """한 줄을 :class:`Guest` 로 변환한다. 빈 줄/주석은 ``None``."""
    text = str(line or "").strip()
    if not text or _COMMENT_RE.match(text):
        return None

    names, aliases, name_found = extract_names(text, fallback=f"하객{line_number}")
    amount, candidates = extract_amount(text)
    attendance = _resolve_attendance(text)

    stated_adult = parse_adult_tickets(text)
    stated_child = parse_child_tickets(text)

    if attendance is Attendance.ABSENT:
        # 오지 않은 하객에게 식대를 물리지 않는다. 구버전의 정산 오차 원인.
        adult_tickets = stated_adult or 0
        child_tickets = stated_child or 0
    else:
        # 식권 수를 안 적었으면 사람 수만큼 발급된 것으로 본다(부부 = 2장).
        adult_tickets = stated_adult if stated_adult is not None else max(1, len(names))
        child_tickets = stated_child or 0

    guest = Guest(
        name=format_display_name(names) or f"하객{line_number}",
        names=names,
        aliases=aliases,
        amount=amount,
        relation=guess_relation(text),
        attendance=attendance,
        payment=Payment.TRANSFER if _TRANSFER_RE.search(text) else Payment.CASH,
        adult_tickets=adult_tickets,
        child_tickets=child_tickets,
        raw=text,
        source=Source.TEXT,
        guest_id=line_number,
    )

    if not name_found:
        guest.add_warning(WARN_NO_NAME)
    if amount <= 0:
        guest.add_warning(WARN_NO_AMOUNT)
    elif len({c for c in candidates}) > 1:
        guest.add_warning(WARN_AMBIGUOUS_AMOUNT)
    return guest


def parse_text(raw_text: str) -> list[Guest]:
    """여러 줄 텍스트를 파싱한다. 순번은 유효한 행 기준으로 다시 매긴다."""
    guests: list[Guest] = []
    for index, line in enumerate(str(raw_text or "").splitlines(), start=1):
        guest = parse_line(line, index)
        if guest is not None:
            guests.append(guest)
    return renumber(guests)
