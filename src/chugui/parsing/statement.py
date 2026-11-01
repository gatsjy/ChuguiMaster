"""은행 거래내역 읽기.

명단 엑셀과 거래내역은 같은 표처럼 보여도 뜻이 다르다. 일반 파서로 읽으면 이렇게 틀린다.

    거래금액 -500,000 (예식장 잔금)   → 축의금 +500,000 으로 합산, 경고 없음
    적요=타행이체, 기재내용=홍길동    → 이름이 '타행이체'
    거래유형=출금                     → 0원짜리 하객으로 등록
    파일 이름에 '내역' 이 없으면      → 계좌이체가 현금으로 집계

그래서 **열 구성으로** 거래내역을 알아보고(파일 이름은 믿지 않는다) 따로 읽는다.

* 돈이 나간 줄은 하객이 아니다. 건너뛰고 몇 건 건너뛰었는지 알린다.
* 돈이 들어온 줄은 **절대 버리지 않는다.** 보낸 사람을 모르면 '이름 미상' + 확인 필요로 남긴다.
* 계좌로 보낸 사람은 `불참(송금)` · 식권 0장으로 시작한다. 메모에 '참석' 이 있으면 참석으로 본다.
  와서 이체한 사람은 표에서 참석으로 바꾸면 식권이 살아난다.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from chugui.models import WARN_NO_NAME, Attendance, Guest, Payment, Source, renumber
from chugui.parsing.amount import parse_amount
from chugui.parsing.names import extract_names, format_display_name, strip_person_names
from chugui.parsing.relations import guess_relation

_MAX_HEADER_SCAN = 20

#: 있으면 거래내역이다. 사람이 만든 명단에는 잘 없는 열들.
_SIGNATURE = ("잔액", "잔고", "출금", "찾으신", "거래일", "거래일시", "보낸분", "보내는분", "입금자")
_IN_KEYS = ("입금액", "입금금액", "맡기신", "받은금액", "입금")
_OUT_KEYS = ("출금", "찾으신", "지급", "인출")
_SIGNED_KEYS = ("거래금액", "거래액", "금액")
_BALANCE_KEYS = ("잔액", "잔고")
_TYPE_KEYS = ("구분", "유형", "입출금")
#: 앞에 있을수록 보낸 사람일 가능성이 높다. '적요' 는 은행마다 뜻이 달라 맨 뒤에 둔다.
_SENDER_KEYS = (
    "보낸분", "보내는분", "입금자", "의뢰인", "거래자", "성명", "이름", "받는분",
    "기재내용", "내용", "통장표시", "표시내용", "적요",
)
_MEMO_KEYS = ("메모", "비고")
_TOTAL_MARKERS = ("합계", "총계", "소계", "TOTAL", "Total")

_OUT_WORD_RE = re.compile(r"출금|지급|인출|결제|찾으신")
_IN_WORD_RE = re.compile(r"입금|맡기신")
_ATTENDED_RE = re.compile(r"참석|왔음|오심|방문")
#: 사람 이름처럼 생겼지만 은행이 적는 거래 종류.
_BANK_WORDS = frozenset(
    {
        "타행이체", "타행", "당행", "전자금융", "인터넷", "모바일", "스마트폰", "폰뱅킹", "펌뱅킹",
        "체크카드", "신용카드", "오픈뱅킹", "자동이체", "대체", "현금", "이자", "결산이자", "예금이자",
        "수수료", "일반입금", "일반출금", "계좌이체", "이체", "입금", "출금", "무통장", "창구",
    }
)
#: 앞에 붙은 음수 표시: -500,000 · −500,000 · (500,000) · △500,000
_NEGATIVE_RE = re.compile(r"^\s*(?:[-−–△▲]|\()\s*[\d₩]")


def _squash(header: object) -> str:
    return re.sub(r"\s+", "", str(header or ""))


def _column(headers: Sequence[str], keys: Sequence[str], exclude: Sequence[str] = ()) -> int | None:
    """keys 중 앞선 키를 가진 열. exclude 가 든 열은 건너뛴다."""
    for key in keys:
        for index, header in enumerate(headers):
            if key in header and not any(word in header for word in exclude):
                return index
    return None


def _columns(headers: Sequence[str], keys: Sequence[str]) -> list[int]:
    return [i for i, header in enumerate(headers) if any(key in header for key in keys)]


def find_statement_header(rows: Sequence[Sequence[object]]) -> int | None:
    """거래내역의 헤더 행 번호. 거래내역이 아니면 ``None``.

    거래내역 표지(잔액 · 출금 · 거래일 · 보낸분 …)와 금액 열이 **함께** 있어야 한다.
    """
    for index, row in enumerate(rows[:_MAX_HEADER_SCAN]):
        headers = [_squash(cell) for cell in row]
        if sum(1 for header in headers if header) < 2:
            continue
        has_signature = any(key in header for header in headers for key in _SIGNATURE)
        has_money = (
            _column(headers, _IN_KEYS, exclude=_OUT_KEYS) is not None
            or _column(headers, _SIGNED_KEYS, exclude=_BALANCE_KEYS + _OUT_KEYS) is not None
        )
        if has_signature and has_money:
            return index
    return None


@dataclass
class StatementResult:
    guests: list[Guest] = field(default_factory=list)
    #: 돈이 나간 줄이라 건너뛴 건수. 사용자에게 알린다.
    skipped_outflows: int = 0


def _text(row: Sequence[object], index: int | None) -> str:
    if index is None or index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()


def _is_person(value: str) -> bool:
    """거래 종류가 아니라 사람(또는 단체) 이름으로 보이는가."""
    cleaned = _squash(value)
    if not cleaned or cleaned in _BANK_WORDS:
        return False
    return extract_names(value)[2]


def _pick_sender_column(
    headers: Sequence[str], body: Sequence[Sequence[object]], reserved: set[int]
) -> int | None:
    """보낸 사람 열. 이름처럼 보이는 값이 가장 많은 열을 고르고, 같으면 키 순서를 따른다.

    은행마다 열 이름의 뜻이 다르다. 같은 '적요' 가 어디서는 '타행이체' 이고 어디서는 보낸 사람이다.
    그래서 열 이름만 믿지 않고 실제 값을 본다.
    """
    best: int | None = None
    best_count = 0
    for key in _SENDER_KEYS:
        for index, header in enumerate(headers):
            if key not in header or index in reserved:
                continue
            count = sum(1 for row in body if _is_person(_text(row, index)))
            if count > best_count:
                best, best_count = index, count
    if best is not None:
        return best
    return next(
        (
            index
            for key in _SENDER_KEYS
            for index, header in enumerate(headers)
            if key in header and index not in reserved
        ),
        None,
    )


def parse_statement_rows(rows: Sequence[Sequence[object]]) -> StatementResult | None:
    """거래내역이면 입금 줄을 하객으로 바꾼다. 거래내역이 아니면 ``None``."""
    header_index = find_statement_header(rows)
    if header_index is None:
        return None

    headers = [_squash(cell) for cell in rows[header_index]]
    body = [row for row in rows[header_index + 1 :] if any(str(cell or "").strip() for cell in row)]

    in_col = _column(headers, _IN_KEYS, exclude=_OUT_KEYS + _TYPE_KEYS)
    out_col = _column(headers, _OUT_KEYS, exclude=_IN_KEYS + _TYPE_KEYS)
    signed_col = _column(headers, _SIGNED_KEYS, exclude=_BALANCE_KEYS + _OUT_KEYS + _IN_KEYS)
    type_cols = _columns(headers, _TYPE_KEYS)
    money_cols = {i for i in (in_col, out_col, signed_col) if i is not None}
    balance_cols = set(_columns(headers, _BALANCE_KEYS))
    memo_col = _column(headers, _MEMO_KEYS)
    reserved = money_cols | balance_cols | set(type_cols)
    if memo_col is not None:
        reserved.add(memo_col)
    sender_col = _pick_sender_column(headers, body, reserved)

    result = StatementResult()
    for row in body:
        cells = [str(cell).strip() for cell in row if cell is not None]
        if any(marker in cell for cell in cells[:3] for marker in _TOTAL_MARKERS):
            continue

        kinds = " ".join(_text(row, i) for i in type_cols)
        money = _text(row, in_col if in_col is not None else signed_col)
        amount = parse_amount(money)
        went_out = (
            bool(_OUT_WORD_RE.search(kinds) and not _IN_WORD_RE.search(kinds))
            or bool(_NEGATIVE_RE.match(money))
            or (in_col is not None and amount <= 0 and parse_amount(_text(row, out_col)) > 0)
        )
        if went_out:
            result.skipped_outflows += 1
            continue
        if amount <= 0:
            continue  # 금액이 없는 줄(소계 · 안내문)은 거래가 아니다.

        result.guests.append(_guest_from(row, sender_col, memo_col, amount))

    renumber(result.guests)
    return result


def _guest_from(row: Sequence[object], sender_col: int | None, memo_col: int | None, amount: int) -> Guest:
    raw_name = _text(row, sender_col)
    memo = _text(row, memo_col)
    person = _is_person(raw_name)
    names = extract_names(raw_name)[0] if person else ([raw_name] if raw_name else [])

    attended = bool(_ATTENDED_RE.search(memo))
    guest = Guest(
        name=format_display_name(names) or "이름 미상",
        names=names,
        amount=amount,
        relation=guess_relation(memo, strip_person_names(raw_name, names)),
        attendance=Attendance.PRESENT if attended else Attendance.ABSENT,
        payment=Payment.TRANSFER,
        adult_tickets=max(1, len(names)) if attended else 0,
        note=memo,
        raw=" ".join(part for part in (raw_name, str(amount), memo) if part),
        source=Source.BANK,
    )
    if not person:
        guest.add_warning(WARN_NO_NAME)
    return guest
