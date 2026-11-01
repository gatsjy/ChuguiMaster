"""금액 파서.

이 모듈은 프로그램 전체에서 가장 중요하다. 여기가 틀리면 나머지가 전부 무의미하다.

구버전은 줄 전체에서 ``re.findall(r'\\d+')`` 로 숫자를 긁어 **이어붙였다**.
그래서 ``"1 홍길동 200000 친척모임"`` 이 1,200,000원으로 계산됐다(6배).
여기서는 정반대로 접근한다.

1. 금액이 아닌 것이 확실한 토큰을 **먼저 제거한다** (줄번호/식권/날짜/전화/계좌번호).
2. 남은 문자열에서 ``숫자 + 단위`` 후보를 구조적으로 추출한다.
3. 단위가 없는 1,000 미만의 맨숫자는 **금액으로 인정하지 않는다**.
   구버전은 ``500`` 을 500만원으로 승격시켰다. 조용한 추측은 하지 않는다.
4. 후보가 여러 개면 가장 큰 값을 채택하되, 호출자가 모호성을 알 수 있게 후보를 노출한다.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Any

from chugui.parsing.tickets import strip_ticket_tokens

# 선언 순서 = 크기 내림차순. 아래 _UNIT_RANK가 이 순서에 의존한다.
_UNITS: dict[str, int] = {
    "억": 100_000_000,
    "천만": 10_000_000,
    "백만": 1_000_000,
    "십만": 100_000,
    "만": 10_000,
    "천": 1_000,
}
_UNIT_RANK: dict[str, int] = {unit: rank for rank, unit in enumerate(_UNITS)}

# 단위 대체 표기는 정규식 교대에서 반드시 긴 것부터 와야 한다("천만"이 "천"보다 앞).
# 단위 뒤에 일반 한글 단어가 이어지면(예: "천안") 단위가 아닌 단어의 일부로 판단한다.
# 소수점도 숫자의 일부로 읽는다. 예전에는 '1.5만' 이 '1' 과 '5만' 으로 쪼개져 50,000원이 됐다.
# '10만원입니다' 처럼 '원' 뒤에 말이 이어져도 금액이다.
_NUM_UNIT_RE = re.compile(
    r"(\d[\d,]*(?:\.\d+)*)\s*(억|천만|백만|십만|만|천)?(원)?"
    r"(?:(?<=원)(?=입니다|이요|요|임|정)|(?![가-힣A-Za-z]))"
)
#: '100.000원' 처럼 점을 천 단위 구분자로 쓴 표기.
_DOT_THOUSANDS_RE = re.compile(r"\d{1,3}(?:\.\d{3})+")

# --- 금액이 아닌 숫자를 제거하기 위한 패턴들 -------------------------------
# 식권 표기 제거는 :mod:`chugui.parsing.tickets` 가 담당한다.
# 예전에는 이 파일이 자체 정규식을 들고 있었는데, 경계 조건이 없어서
# '홍대인' 처럼 이름에 '대인'이 든 하객의 금액을 식권 수로 오인해 지워버렸다.
_LEADING_INDEX_RE = re.compile(r"^\s*\d{1,3}\s*[.)\-:]?\s+")
_DATE_RE = re.compile(r"\d{2,4}\s*[-./년]\s*\d{1,2}\s*[-./월]\s*\d{1,2}\s*일?")
_TIME_RE = re.compile(r"\d{1,2}\s*:\s*\d{2}(\s*:\s*\d{2})?")
_PHONE_RE = re.compile(r"01[016-9][-\s.]?\d{3,4}[-\s.]?\d{4}")
_ACCOUNT_RE = re.compile(r"\d{2,6}[-]\d{2,6}[-]\d{2,7}")
#: 입금 알림을 붙여넣으면 잔액이 축의금보다 커서 금액으로 뽑혔다.
_BALANCE_RE = re.compile(r"(?:잔액|잔고|누적)\s*[:：]?\s*\d[\d,]*\s*원?")

#: 숫자 없이 한글로 쓴 금액. 오만원 · 십오만원 · 이백만원 · 만원.
#: '원' 까지 있어야 인정한다. '이천' '오만' 은 지명이나 이름일 수 있다.
_HANGUL_DIGITS = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_HANGUL_SMALL_UNITS = {"십": 10, "백": 100, "천": 1_000}
_HANGUL_BIG_UNITS = {"만": 10_000, "억": 100_000_000}
_HANGUL_AMOUNT_RE = re.compile(
    r"(?<![가-힣])([일이삼사오육칠팔구십백천만억]+)\s*원(?=입니다|이요|요|임|정|[^가-힣]|$)"
)


def strip_non_amount_numbers(text: str) -> str:
    """금액으로 오인될 수 있는 숫자 표현을 미리 제거한다."""
    cleaned = str(text)
    for pattern in (_BALANCE_RE, _ACCOUNT_RE, _PHONE_RE, _DATE_RE, _TIME_RE):
        cleaned = pattern.sub(" ", cleaned)
    cleaned = strip_ticket_tokens(cleaned)
    cleaned = _LEADING_INDEX_RE.sub(" ", cleaned)
    return cleaned


def _to_number(digits: str, unit: str | None) -> int | None:
    """숫자 표기를 원 단위 정수로 바꾼다. 해석할 수 없으면 ``None``."""
    text = digits.replace(",", "")
    if unit is None and _DOT_THOUSANDS_RE.fullmatch(text):
        return int(text.replace(".", ""))
    try:
        value = Decimal(text) * _UNITS.get(unit or "", 1)
    except InvalidOperation:
        return None  # '1.2.3' 처럼 점이 여러 개인데 천 단위 구분도 아닌 경우
    return int(value.to_integral_value())


def iter_amount_candidates(text: str) -> Iterator[int]:
    """문자열에서 금액 후보를 순서대로 산출한다.

    ``10만 5천`` 처럼 단위가 내림차순으로 이어지면 하나의 금액으로 합산하고,
    ``5만 3만`` 처럼 같거나 커지면 별개의 후보로 끊는다.
    """
    accumulator = 0
    last_rank = -1
    last_multiplier = 0

    for match in _NUM_UNIT_RE.finditer(text):
        digits, unit, won = match.group(1), match.group(2), match.group(3)
        if unit in _UNITS:
            value = _to_number(digits, unit)
            if value is None:
                continue
            rank = _UNIT_RANK[unit]
            if accumulator and rank > last_rank:
                accumulator += value  # "10만" + "5천"
            else:
                if accumulator:
                    yield accumulator
                accumulator = value
            last_rank = rank
            last_multiplier = _UNITS[unit]
            continue

        # 단위 없는 숫자 또는 "…원"
        number = _to_number(digits, None)
        if number is None:
            continue
        # '10만 5000원' 은 한 금액이다. '10만 아기1' 의 1 처럼 단위 없는 작은 수는 붙이지 않는다.
        if accumulator and 0 < number < last_multiplier and (won == "원" or number >= 1_000):
            accumulator += number
            continue
        if accumulator:
            yield accumulator
            accumulator = 0
            last_rank = -1
            last_multiplier = 0
        if won == "원" or number >= 1_000:
            yield number

    if accumulator:
        yield accumulator


def _hangul_number(text: str) -> int:
    """오만 → 50000, 십오만 → 150000, 이백만 → 2000000. 읽을 수 없으면 0."""
    total = 0
    section = 0
    digit = 0
    for character in text:
        if character in _HANGUL_DIGITS:
            if digit:
                return 0  # '오삼만' 같은 것은 수가 아니다.
            digit = _HANGUL_DIGITS[character]
        elif character in _HANGUL_SMALL_UNITS:
            section += (digit or 1) * _HANGUL_SMALL_UNITS[character]
            digit = 0
        else:
            total += (section + digit or 1) * _HANGUL_BIG_UNITS[character]
            section = 0
            digit = 0
    return total + section + digit


def hangul_amount(text: str) -> int:
    """글자로 쓴 금액. 1,000원 미만은 금액으로 보지 않는다(숫자와 같은 기준)."""
    for match in _HANGUL_AMOUNT_RE.finditer(str(text or "")):
        value = _hangul_number(match.group(1))
        if value >= 1_000:
            return value
    return 0


def is_hangul_amount(token: str) -> bool:
    """이 토큰 전체가 글자로 쓴 금액인가. 이름 후보에서 뺄 때 쓴다."""
    return bool(_HANGUL_AMOUNT_RE.fullmatch(str(token or ""))) and hangul_amount(token) > 0


def extract_amount(text: str) -> tuple[int, list[int]]:
    """자유 텍스트 한 줄에서 금액을 뽑는다.

    Returns:
        ``(금액, 후보목록)``. 금액을 찾지 못하면 ``(0, [])``.
        후보가 2개 이상이면 호출자가 "확인 필요" 경고를 붙일 수 있다.
    """
    cleaned = strip_non_amount_numbers(text)
    candidates = [value for value in iter_amount_candidates(cleaned) if value > 0]
    if not candidates:
        written = hangul_amount(cleaned)
        return (written, [written]) if written else (0, [])
    return max(candidates), candidates


def parse_amount(value: Any) -> int:
    """스프레드시트 셀 하나를 금액으로 해석한다."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        try:
            return max(0, round(float(value)))
        except (ValueError, OverflowError):
            return 0
    amount, _ = extract_amount(str(value))
    return amount
