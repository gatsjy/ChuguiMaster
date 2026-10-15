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
#: '총식권3' 처럼 '총' 이 붙어 쓰인 경우도 식권 표기로 받는다.
_GENERIC_BOUNDARY = r"(?:(?<![가-힣])|(?<=[만천억원장명총]))"
GENERIC_TICKET_RE = re.compile(_GENERIC_BOUNDARY + _GENERIC_TICKET_WORDS + _SEP + _COUNT + _SUFFIX)
CHILD_TICKET_RE = re.compile(_BOUNDARY + _CHILD_WORDS + _SEP + _COUNT + _SUFFIX)

#: 금액 파서가 제거할 식권 표기 전체.
#: 식권으로 **읽는** 표기와 금액에서 **지우는** 표기가 어긋나면 그 숫자가 금액에 붙는다
#: ('20만 총식권3' → 200,003). 그래서 읽는 쪽과 같은 경계를 쓴다.
ANY_TICKET_RE = re.compile(
    r"(?:"
    + _BOUNDARY
    + r"(?:"
    + _EXPLICIT_ADULT_WORDS
    + r"|"
    + _CHILD_WORDS
    + r")|"
    + _GENERIC_BOUNDARY
    + _GENERIC_TICKET_WORDS
    + r")"
    + _SEP
    + _COUNT
    + _SUFFIX
)


_TOTAL_PREFIX_RE = re.compile(r"총[  　]*$")
_OPEN_PAREN_RE = re.compile(r"[  　]*[(（]")


def _is_total_notation(text: str, generic: re.Match[str], child: re.Match[str]) -> bool:
    """'식권 N' 이 대인 수가 아니라 **총합**(소인 포함)으로 쓰였는가.

    판단은 **표기 바로 옆**에서만 한다. 예전에는 줄 어딘가에 '(' 나 '총' 이 있기만 해도
    총합으로 봤다. 그래서 같은 '식권3 소인1' 이 별칭 '김재경(조외순)', 소속 '(주)넥스트로',
    '총무', '총동문회' 가 붙으면 대인 3장이 2장으로 바뀌어 식대가 조용히 덜 잡혔다.

    * '총 식권 3 소인 1' · '총식권3 소인1' — '총' 이 식권 바로 앞에 붙어 있다.
    * '식권3(소1)' · '식권 3장 (소인 1장)' — 소인이 식권 바로 뒤 괄호 안에 있다.
    """
    if _TOTAL_PREFIX_RE.search(text[: generic.start()]):
        return True
    paren = _OPEN_PAREN_RE.match(text, generic.end())
    if paren is None:
        return False
    closes = [i for i in (text.find(")", paren.end()), text.find("）", paren.end())) if i != -1]
    close_at = min(closes) if closes else len(text)
    return paren.end() <= child.start() < close_at


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
        if child_m and child and generic_count > child and _is_total_notation(cleaned, generic_m, child_m):
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
