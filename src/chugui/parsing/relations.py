"""관계 자동 분류.

구버전은 dict를 선언 순서대로 순회하며 **처음 일치한 키워드**를 채택했다.
그래서 "대학병원"이 학교로, "고등학교 동창 목사님"이 상황에 따라 뒤집혔다.
여기서는 **가장 긴 키워드가 이긴다**(longest-match wins). 더 구체적인 단서를 신뢰한다.

여기에 규칙이 하나 더 있다. **겹치는 매치는 먼저 시작한 쪽이 이긴다.**

    '여명교회사랑부'
        '교회' @2  (종교)
        '회사' @3  (직장)  <- 여명교[회사]랑부. 단어 경계를 가로지른 우연

두 매치가 문자 위치에서 겹치면 둘 중 하나는 반드시 우연이다. 한국어 합성어는
의미의 머리가 앞에 오므로 먼저 시작한 쪽을 신뢰한다. 이 규칙이 없으면
길이가 같아(둘 다 2자) tie-break 순서로 갈려 교회가 직장으로 분류됐다.
겹치지 않는 매치끼리는 종전대로 최장 일치가 이긴다('대학병원'은 직장).
"""

from __future__ import annotations

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
        "집사", "권사", "장로", "목사", "전도사", "신부", "수녀", "스님", "교우",
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


def _drop_overlapping_artifacts(matches: list[_Match]) -> list[_Match]:
    """겹치는 매치 중 나중에 시작한 쪽을 버린다.

    같은 관계끼리 겹치는 것(삼촌/외삼촌)은 어차피 결과가 같으므로 상관없다.
    문제는 관계가 다른데 겹치는 경우이고, 그때 뒤쪽은 우연히 만들어진 조각이다.
    """
    ordered = sorted(matches, key=lambda m: (m.start, -m.length))
    kept: list[_Match] = []
    for candidate in ordered:
        overlaps_earlier = any(
            candidate.start < accepted.end and accepted.start < candidate.end
            for accepted in kept
            if accepted.relation is not candidate.relation
        )
        if not overlaps_earlier:
            kept.append(candidate)
    return kept


def guess_relation(*texts: str) -> Relation:
    """소속/비고/원문 등에서 관계를 추정한다.

    1. 겹치는 매치는 먼저 시작한 쪽만 남긴다(경계를 가로지른 우연 제거).
    2. 남은 것 중 가장 긴 키워드가 이긴다.
    3. 길이도 같으면 :data:`_TIE_BREAK` 순서를 따른다.

    아무 단서도 없으면 :attr:`Relation.OTHER`.
    """
    haystack = " ".join(str(text or "") for text in texts)
    if not haystack.strip():
        return Relation.OTHER

    survivors = _drop_overlapping_artifacts(_find_matches(haystack))
    if not survivors:
        return Relation.OTHER

    best = min(survivors, key=lambda m: (-m.length, m.priority, m.start))
    return best.relation


def all_keywords() -> frozenset[str]:
    """모든 관계 키워드의 합집합. 이름 추출 시 제외 후보로 쓰인다."""
    return frozenset(keyword for group in KEYWORDS.values() for keyword in group)
