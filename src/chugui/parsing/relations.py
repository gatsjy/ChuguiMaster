"""관계 자동 분류.

구버전은 dict를 선언 순서대로 순회하며 **처음 일치한 키워드**를 채택했다.
그래서 "대학병원"이 학교로, "고등학교 동창 목사님"이 상황에 따라 뒤집혔다.
여기서는 **가장 긴 키워드가 이긴다**(longest-match wins). 더 구체적인 단서를 신뢰한다.

여기에 규칙이 하나 더 있다. **겹치는 매치는 먼저 시작한 쪽이 이긴다.**

    '여명교회사랑부'
        '교회' @2  (종교)
        '회사' @3  (직장)  <- 여명교[회사]랑부. 단어 경계를 가로지른 우연

두 매치가 문자 위치에서 겹치면 둘 중 하나는 반드시 우연이다. 기본은 먼저 시작한
쪽을 믿되, 뒤쪽이 낱말 끝에 닿으면 그쪽을 믿는다(대학[교회] → 교회).

그리고 **한 낱말(합성어) 안에서는 마지막 기관명이 머리다.**

    '경북대학교병원'   '대학교'(학교, 3자) + '병원'(직장, 2자)  → 병원 = 직장

예전에는 가장 긴 키워드가 이겨 병원 직원이 학교 동창으로 분류됐다.
사람 낱말('친구' · '동기')은 기관명을 꾸밀 뿐이라 '회사동기' 는 직장, '교회친구' 는 종교다.
최장 일치는 **낱말들 사이**에서만 쓴다('고등학교 동창 목사님' → 고등학교).

성직자는 '신부님' 으로만 인식한다. 결혼식 명단에서 '신부' 는 거의 언제나
'신부측 하객' 이라는 뜻이고, 예전에는 '신부측 대학동기' 가 종교로 분류됐다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from chugui.models import Relation

KEYWORDS: dict[Relation, tuple[str, ...]] = {
    Relation.FAMILY: (
        "친척", "가족", "친지", "일가", "종친",
        "이모", "고모", "삼촌", "숙부", "백부", "당숙", "외삼촌", "외숙",
        "할머니", "할아버지", "조모", "조부", "형님", "누님", "매형", "제수",
        "처남", "처형", "처제", "동서", "사촌", "조카", "장인", "장모",
    ),
    Relation.WORK: (
        "직장", "회사", "부서", "본부", "지사", "지점", "센터", "협회", "재단",
        "보건소", "보건지소", "보건지구", "지소", "병원", "의원", "약국", "학회",
        "대표", "이사", "부장", "차장", "과장", "계장", "팀장", "실장", "주임",
        "대리", "사원", "동료", "상사", "선임", "책임", "수석", "소속", "거래처",
        "원장", "국장", "청장", "주무관", "공무원",
    ),
    Relation.FAITH: (
        "교회", "성당", "사찰", "절", "법당", "선교회", "구역", "목장", "셀모임",
        "집사", "권사", "장로", "목사", "전도사", "신부님", "수녀", "스님", "교우",
        "성도", "교인", "신도", "기도모임",
    ),
    Relation.SCHOOL: (
        "대학교", "대학원", "대학", "고등학교", "고교", "중학교", "초등학교",
        "동창", "동창회", "동문", "동문회", "동기", "학과", "학번", "과동기",
        "선배", "후배", "은사", "담임", "친구", "베프", "절친",
    ),
    Relation.OTHER: (
        "지인", "이웃", "지역", "동네", "기타", "모임", "카페", "동호회",
    ),
}

# 길이가 같은 키워드가 서로 다른 관계에서 동시에 걸릴 때의 우선순위.
_TIE_BREAK: tuple[Relation, ...] = (
    Relation.FAMILY,
    Relation.WORK,
    Relation.FAITH,
    Relation.SCHOOL,
    Relation.OTHER,
)


#: 기관 · 장소 이름. 합성어에서 머리(마지막 기관명)를 고를 때 쓴다.
#: 사람 · 역할 낱말(친구 · 동기 · 이모 · 집사 …)은 여기 넣지 않는다.
INSTITUTIONS: frozenset[str] = frozenset({
    "직장", "회사", "부서", "본부", "지사", "지점", "센터", "협회", "재단", "보건소",
    "보건지소", "보건지구", "지소", "병원", "의원", "약국", "학회", "거래처",
    "교회", "성당", "사찰", "절", "법당", "선교회", "구역", "목장", "셀모임", "기도모임",
    "대학교", "대학원", "대학", "고등학교", "고교", "중학교", "초등학교", "동창회", "동문회", "학과",
    "동호회", "카페", "동네", "지역",
})

#: 낱말 경계. 공백과 '친척/가족' 같은 구분자에서 끊는다.
_WORD_RE = re.compile(r"[^\s/,·&]+")


@dataclass(frozen=True)
class _Match:
    """해당 위치에서 걸린 키워드 하나."""

    start: int
    end: int
    keyword: str
    relation: Relation
    priority: int  # _TIE_BREAK 상의 순서. 작을수록 우선.

    @property
    def length(self) -> int:
        return len(self.keyword)


def _find_matches(haystack: str) -> list[_Match]:
    """모든 관계 키워드의 모든 출현 위치를 모은다."""
    matches: list[_Match] = []
    for priority, relation in enumerate(_TIE_BREAK):
        for keyword in KEYWORDS[relation]:
            start = haystack.find(keyword)
            while start != -1:
                matches.append(
                    _Match(start, start + len(keyword), keyword, relation, priority)
                )
                start = haystack.find(keyword, start + 1)
    return matches


def _drop_overlapping_artifacts(matches: list[_Match], word_end: int) -> list[_Match]:
    """한 낱말 안에서 관계가 다른 두 매치가 겹치면 하나만 남긴다.

    같은 관계끼리 겹치는 것(삼촌/외삼촌)은 어차피 결과가 같으므로 상관없다.
    관계가 다른데 겹치면 하나는 우연히 만들어진 조각이다. 기본은 먼저 시작한 쪽을
    믿지만(여명교[회사]랑부), 뒤쪽이 **낱말 끝에 닿으면** 그쪽이 합성어의 머리다
    (대학[교회] → 교회).
    """
    ordered = sorted(matches, key=lambda m: (m.start, -m.length))
    kept: list[_Match] = []
    for candidate in ordered:
        clashes = [
            accepted
            for accepted in kept
            if accepted.relation is not candidate.relation
            and candidate.start < accepted.end
            and accepted.start < candidate.end
        ]
        if not clashes:
            kept.append(candidate)
        elif candidate.end == word_end and all(clash.end != word_end for clash in clashes):
            kept = [accepted for accepted in kept if accepted not in clashes]
            kept.append(candidate)
    return kept


def _word_winners(matches: list[_Match], word_end: int) -> list[_Match]:
    """한 낱말(합성어)에서 관계를 결정하는 매치.

    합성어는 **마지막 기관명이 머리**다. '경북대학교병원' 은 대학교가 아니라 병원이다.
    예전에는 가장 긴 키워드('대학교', 3자)가 이겨 병원 직원이 학교 동창으로 분류됐다.
    '친구' · '동기' 같은 사람 낱말은 기관명을 꾸밀 뿐이라('회사동기', '교회친구'),
    기관명이 있는 낱말에서는 머리가 되지 못한다.
    """
    survivors = _drop_overlapping_artifacts(matches, word_end)
    institutions = [m for m in survivors if m.keyword in INSTITUTIONS]
    if institutions:
        return [max(institutions, key=lambda m: (m.end, m.length))]
    return survivors


def guess_relation(*texts: str) -> Relation:
    """소속/비고/원문 등에서 관계를 추정한다.

    1. 낱말(공백 · 구분자 단위)마다 그 낱말의 관계를 정한다(:func:`_word_winners`).
    2. 낱말들 사이에서는 가장 긴 키워드가 이긴다.
    3. 길이도 같으면 :data:`_TIE_BREAK` 순서를 따른다.

    아무 단서도 없으면 :attr:`Relation.OTHER`.
    """
    haystack = " ".join(str(text or "") for text in texts)
    if not haystack.strip():
        return Relation.OTHER

    matches = _find_matches(haystack)
    winners: list[_Match] = []
    for word in _WORD_RE.finditer(haystack):
        inside = [m for m in matches if word.start() <= m.start and m.end <= word.end()]
        if inside:
            winners.extend(_word_winners(inside, word.end()))
    if not winners:
        return Relation.OTHER

    best = min(winners, key=lambda m: (-m.length, m.priority, m.start))
    return best.relation


def all_keywords() -> frozenset[str]:
    """모든 관계 키워드의 합집합. 이름 추출 시 제외 후보로 쓰인다."""
    return frozenset(keyword for group in KEYWORDS.values() for keyword in group)
