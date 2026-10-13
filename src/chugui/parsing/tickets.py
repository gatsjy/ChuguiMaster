"""식권 수 표기 파싱.

이 모듈이 따로 존재하는 이유는 **실제 데이터에서 겪은 사고** 때문이다.

하객 이름에 `대인` / `소인` / `성인` 이 들어 있으면(예: 홍대인, 홍소인, 홍성인)
그 뒤에 오는 금액이 식권 수로 오인됐다.

    "홍대인\\t50,000\\tOO기업"
        → '대인' + 공백 + '50' 이 식권 표기로 매치
        → 대인 식권 50장 (사람은 1명)
        → 금액 파서가 "대인\\t50" 을 지워 ",000" 만 남아 0원

225건 실제 명단에서 이 한 줄 때문에 총액이 50,000원 모자라고,
식권이 49장 부풀어 총 식대가 2,695,000원 늘고,
**순 정산금이 2,745,000원 틀어졌다.**

금액 파서와 텍스트 파서가 각자 비슷한 정규식을 들고 있었던 것이 문제를 키웠다.
두 곳이 같은 정의를 쓰도록 여기 한 곳에 모았다.

세 겹으로 막는다.

1. **앞 경계** — 한글 바로 뒤에 붙은 키워드는 사람 이름의 일부로 본다.
   단 `만` `천` `억` `원` `장` `명` 뒤라면 금액 표기 뒤에 붙은 것이므로 허용한다
   (`10만원식권2` 같은 붙여쓰기를 계속 지원하기 위함).
2. **자릿수** — 식권 수는 1~2자리이고, 더 긴 숫자의 앞부분이어서는 안 된다.
   이것만으로도 `50,000` 을 식권 수로 읽는 일이 사라진다.
3. **구분자** — 키워드와 숫자 사이에 탭·줄바꿈이 오면 다른 열로 본다.
   탭으로 구분된 명단을 붙여넣는 경우가 흔하다.
"""

from __future__ import annotations

import re

#: 금액 단위 뒤에 붙은 키워드는 허용하고, 그 밖의 한글에 붙은 것은 거부한다.
_BOUNDARY = r"(?:(?<![가-힣])|(?<=[만천억원장명]))"

#: 키워드와 숫자 사이 구분자. 탭과 줄바꿈은 열 경계로 보고 제외한다.
_SEP = r"[  　]*[:=]?[  　]*"

#: 식권 수는 1~2자리. 뒤에 숫자나 콤마+숫자(금액 천단위)가 이어지면 더 긴 수의 일부이므로 거부한다.
_COUNT = r"(\d{1,2})(?!\d|,\d)"

_EXPLICIT_ADULT_WORDS = r"(?:대인|성인|어른|대)"
_GENERIC_TICKET_WORDS = r"(?:식권|식대)"
_CHILD_WORDS = r"(?:소인|어린이|아동|아이|유아|애기|자녀|애|소)"
_SUFFIX = r"\s*(?:명|장|개)?"

ADULT_TICKET_RE = re.compile(
    _BOUNDARY + r"(?:" + _EXPLICIT_ADULT_WORDS + r"|" + _GENERIC_TICKET_WORDS + r")" + _SEP + _COUNT + _SUFFIX
)
EXPLICIT_ADULT_RE = re.compile(_BOUNDARY + _EXPLICIT_ADULT_WORDS + _SEP + _COUNT + _SUFFIX)
GENERIC_TICKET_RE = re.compile(_BOUNDARY + _GENERIC_TICKET_WORDS + _SEP + _COUNT + _SUFFIX)
CHILD_TICKET_RE = re.compile(_BOUNDARY + _CHILD_WORDS + _SEP + _COUNT + _SUFFIX)

#: 금액 파서가 제거할 식권 표기 전체.
ANY_TICKET_RE = re.compile(
    _BOUNDARY
    + r"(?:"
    + _EXPLICIT_ADULT_WORDS
    + r"|"
    + _GENERIC_TICKET_WORDS
    + r"|"
    + _CHILD_WORDS
    + r")"
    + _SEP
    + _COUNT
    + _SUFFIX
)


def parse_ticket_counts(text: str) -> tuple[int | None, int | None]:
    """텍스트에서 (대인 식권 수, 소인 식권 수)를 추출한다."""
    cleaned = str(text or "")
    explicit_adult_m = EXPLICIT_ADULT_RE.search(cleaned)
    generic_m = GENERIC_TICKET_RE.search(cleaned)
    child_m = CHILD_TICKET_RE.search(cleaned)

    child = int(child_m.group(1)) if child_m else None

    if explicit_adult_m:
        adult = int(explicit_adult_m.group(1))
    elif generic_m:
        generic_count = int(generic_m.group(1))
        # 식권 3장(소인 1장) 또는 총식권 3 소인 1 처럼 총합과 소인이 함께 표기된 경우 대인 자동 차감
        if ("총" in cleaned or "(" in cleaned or "（" in cleaned) and child and generic_count > child:
            adult = generic_count - child
        else:
            adult = generic_count
    else:
        adult = None

    return adult, child


def adult_tickets(text: str) -> int | None:
    """명시된 대인 식권 수. 표기가 없으면 ``None``."""
    adult, _ = parse_ticket_counts(text)
    return adult


def child_tickets(text: str) -> int | None:
    """명시된 소인 식권 수. 표기가 없으면 ``None``."""
    _, child = parse_ticket_counts(text)
    return child


def strip_ticket_tokens(text: str) -> str:
    """식권 표기를 지운다. 금액 파서가 식권 수를 금액으로 읽지 않게 하기 위함."""
    return ANY_TICKET_RE.sub(" ", str(text or ""))
