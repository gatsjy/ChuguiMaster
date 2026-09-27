"""이름 추출.

구버전 로직의 핵심 결함:

    re.sub(r'[\\d만,원식권불참송금현금계좌이체]', '', token)

이것은 단어 목록이 아니라 **개별 글자 집합**이다. 한국 이름에 흔한
'이', '체', '권', '원', '식', '금', '현', '계', '좌'가 전부 삭제되어
``이체리`` / ``권원식`` 같은 실명이 통째로 사라졌다.
게다가 ``['보건','교회','이모', ...]`` 부분 문자열 차단 목록 때문에
``박이모`` 처럼 이름 안에 친족어가 들어간 하객도 탈락했다.

새 전략은 "지우기"가 아니라 "고르기"다.

* 이름 후보는 **한글 2~5자 토큰**이어야 한다.
* 라틴 문자나 숫자가 섞인 토큰은 조직 표기(``A보건지소``, ``OO교회``)로 보고 제외.
* 조직 접미사는 **2글자 이상**만 사용한다. 1글자 접미사(원/부/장)를 쓰면
  ``박서원`` / ``한계장`` 같은 실명을 잡아먹는다.
* 그래도 못 찾으면 추측하지 않고 경고를 반환한다.
"""

from __future__ import annotations

import re

from chugui.parsing.relations import all_keywords

# 조직/장소를 뜻하는 2글자 이상 접미사만. 1글자 접미사는 오탐이 너무 크다.
_ORG_SUFFIXES: tuple[str, ...] = (
    "보건소", "보건지소", "보건지구", "지소", "교회", "성당", "사찰", "법당",
    "병원", "의원", "약국", "회사", "학교", "대학", "대학교", "센터", "협회",
    "재단", "지점", "지사", "본부", "동창회", "동문회", "선교회", "모임",
    "구역", "동호회", "부서", "사무소", "연구소", "공단", "공사", "학회",
)

# 상태 표기 토큰. 이름이 될 수 없다.
_MARKER_WORDS: frozenset[str] = frozenset(
    {
        "불참", "미참석", "참석", "송금", "이체", "계좌", "계좌이체", "현금",
        "봉투", "축의", "축의금", "부의", "화환", "합계", "총계", "소계", "비고",
    }
)
_MARKER_RE = re.compile(r"^(식권|식대|대인|성인|소인|어린이|아동|아이)\s*\d*$")
#: 혼주 측 표기. 결혼식 명단에서 가장 흔한 비고인데 3글자라 이름처럼 보인다.
_SIDE_RE = re.compile(r"^(신랑|신부|혼주)(측|쪽|님)?$")
#: '친구' · '이모' 처럼 토큰 **전체**가 관계어이면 이름이 아니다.
#: 부분 문자열로는 막지 않는다. '박이모' · '김동기' 는 실명일 수 있다.
_RELATION_WORDS: frozenset[str] = all_keywords()
#: 이름 뒤 호칭. 떼지 않으면 감사 문구가 '홍길동님님' 이 된다.
_HONORIFIC_RE = re.compile(r"^([가-힣]{2,5})(님|씨)$")

_HANGUL_NAME_RE = re.compile(r"^[가-힣]{2,5}$")
#: 사람 이름은 아니어도 단체명으로 쓸 수 있는 순한글 토큰.
_HANGUL_ONLY_RE = re.compile(r"^[가-힣]{2,12}$")
_PAREN_RE = re.compile(r"[（(]([^)）]*)[)）]")
_SPLIT_RE = re.compile(r"[,/·&＆]+")
#: 공백 외에 '[홍길동]' · '홍길동:50000' · '홍길동-50000' 의 기호도 토큰 경계다.
_TOKEN_SPLIT_RE = re.compile(r"[\s\[\]{}<>「」『』【】:;|~=]+|-(?=\d)")
#: '김철수 , 이영희' 처럼 구분자 양옆에 띄어 쓴 공백을 붙여 한 토큰으로 만든다.
_SPACED_SEP_RE = re.compile(r"\s*([,/·&＆])\s*")


def _looks_like_org(token: str) -> bool:
    """조직/장소 표기로 보이는가."""
    if any(token.endswith(suffix) for suffix in _ORG_SUFFIXES):
        return True
    return any(suffix in token for suffix in ("보건", "교회", "성당", "동창회", "동문회"))


def _is_marker(token: str) -> bool:
    return (
        token in _MARKER_WORDS
        or token in _RELATION_WORDS
        or bool(_MARKER_RE.match(token) or _SIDE_RE.match(token))
    )


def _strip_honorific(token: str) -> str:
    """'홍길동님' → '홍길동'. 떼고 나서 이름답지 않으면 원래 토큰을 돌려준다."""
    match = _HONORIFIC_RE.match(token)
    if match and _is_name_like(match.group(1)):
        return match.group(1)
    return token


def _is_name_like(token: str) -> bool:
    """이 토큰이 사람 이름일 수 있는가."""
    if not token or not _HANGUL_NAME_RE.match(token):
        return False  # 숫자/라틴문자 포함 토큰은 여기서 걸러진다
    if _is_marker(token):
        return False
    return not _looks_like_org(token)


def split_names(chunk: str) -> list[str]:
    """``김가족,김친지`` / ``진부부·신부부`` 를 개별 이름으로 분리한다."""
    return [part.strip() for part in _SPLIT_RE.split(chunk) if part.strip()]


def extract_names(line: str, fallback: str = "") -> tuple[list[str], list[str], bool]:
    """한 줄에서 하객 이름을 추출한다.

    Returns:
        ``(이름목록, 별칭목록, 성공여부)``.
        성공여부가 ``False``면 호출자가 fallback 이름과 경고를 붙여야 한다.
    """
    text = str(line or "").strip()
    if not text:
        return ([fallback] if fallback else [], [], False)

    aliases: list[str] = []

    # 괄호 안 별칭을 먼저 떼어낸다: 김성도(조성도) → 김성도 + 별칭 조성도
    def _capture_alias(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        for candidate in split_names(inner):
            if _is_name_like(candidate):
                aliases.append(candidate)
        return " "

    stripped = _SPACED_SEP_RE.sub(r"\1", _PAREN_RE.sub(_capture_alias, text))

    for token in _TOKEN_SPLIT_RE.split(stripped):
        token = token.strip().strip(".:;")
        if not token:
            continue
        # '김철수,이영희' 는 부부, '홍길동,5만원' 은 이름 하나.
        # 예전에는 구성원 전체가 이름다워야 했고, 아니면 토큰 전체('홍길동,')를
        # 이름으로 검사해 실패했다. 그래서 '홍길동, 5만원' 이 '하객1' 이 됐다.
        members = [
            member
            for member in (_strip_honorific(part) for part in split_names(token))
            if _is_name_like(member)
        ]
        if members:
            return members, aliases, True

    # 2차 시도: 단체 명의로 낸 경우(예: 'OO교회사랑부', '청년회').
    # 사람 이름은 아니지만 감사 인사를 보낼 대상 이름으로는 쓸 수 있다.
    # '하객83' 보다는 훨씬 낫다. 확신은 못 하므로 성공으로 보고하지는 않는다.
    for token in _TOKEN_SPLIT_RE.split(stripped):
        token = token.strip().strip(".:;,/")
        if token and _HANGUL_ONLY_RE.match(token) and not _is_marker(token):
            return [token], aliases, False

    return ([fallback] if fallback else [], aliases, False)


def strip_person_names(text: str, names: list[str]) -> str:
    """관계 추정 전에 사람 이름을 지운다.

    '이사랑' 의 '이사' 가 관계 단서로 잡혀 하객이 직장으로 분류되곤 했다.

    단, **성 + 호칭** 꼴('김부장', '박이모', '최동료')은 남긴다. 명단에서 흔한
    표기이고, 그때는 호칭이 곧 관계다. '김동기' 처럼 실명과 구분이 안 되는
    경우는 호칭 쪽으로 본다(관계는 표에서 한 번에 고칠 수 있다).
    단체 명의('OO교회청년부')는 사람 이름이 아니므로 역시 남긴다.
    """
    result = str(text or "")
    for name in names:
        if _is_name_like(name) and name[1:] not in _RELATION_WORDS:
            result = result.replace(name, " ")
    return result


def format_display_name(names: list[str]) -> str:
    """표와 메시지에 함께 쓰이는 표시 이름."""
    cleaned = [name for name in names if name]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return " & ".join(cleaned)
