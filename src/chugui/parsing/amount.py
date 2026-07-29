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
from typing import Any

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
_NUM_UNIT_RE = re.compile(r"(\d[\d,]*)\s*(억|천만|백만|십만|만|천)?(원)?(?![가-힣A-Za-z])")

# --- 금액이 아닌 숫자를 제거하기 위한 패턴들 -------------------------------
_TICKET_RE = re.compile(r"(식권|식대|대인|성인|소인|어린이|아동|아이)\s*[:=]?\s*\d+\s*(명|장|개)?")
_LEADING_INDEX_RE = re.compile(r"^\s*\d{1,3}\s*[.)\-:]?\s+")
_DATE_RE = re.compile(r"\d{2,4}\s*[-./년]\s*\d{1,2}\s*[-./월]\s*\d{1,2}\s*일?")
_TIME_RE = re.compile(r"\d{1,2}\s*:\s*\d{2}(\s*:\s*\d{2})?")
_PHONE_RE = re.compile(r"01[016-9][-\s.]?\d{3,4}[-\s.]?\d{4}")
_ACCOUNT_RE = re.compile(r"\d{2,6}[-]\d{2,6}[-]\d{2,7}")


def strip_non_amount_numbers(text: str) -> str:
    """금액으로 오인될 수 있는 숫자 표현을 미리 제거한다."""
    cleaned = str(text)
    for pattern in (_ACCOUNT_RE, _PHONE_RE, _DATE_RE, _TIME_RE, _TICKET_RE):
        cleaned = pattern.sub(" ", cleaned)
    cleaned = _LEADING_INDEX_RE.sub(" ", cleaned)
    return cleaned


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
        try:
            number = int(digits.replace(",", ""))
        except ValueError:  # pragma: no cover - 정규식상 도달 불가
            continue

        if unit in _UNITS:
            value = number * _UNITS[unit]
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
        if accumulator and 0 < number < last_multiplier:
            accumulator += number  # "10만 5000원"
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


def extract_amount(text: str) -> tuple[int, list[int]]:
    """자유 텍스트 한 줄에서 금액을 뽑는다.

    Returns:
        ``(금액, 후보목록)``. 금액을 찾지 못하면 ``(0, [])``.
        후보가 2개 이상이면 호출자가 "확인 필요" 경고를 붙일 수 있다.
    """
    cleaned = strip_non_amount_numbers(text)
    candidates = [value for value in iter_amount_candidates(cleaned) if value > 0]
    if not candidates:
        return 0, []
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
