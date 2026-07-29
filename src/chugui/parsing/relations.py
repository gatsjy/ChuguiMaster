"""관계 자동 분류.

구버전은 dict를 선언 순서대로 순회하며 **처음 일치한 키워드**를 채택했다.
그래서 "대학병원"이 학교로, "고등학교 동창 목사님"이 상황에 따라 뒤집혔다.
여기서는 **가장 긴 키워드가 이긴다**(longest-match wins). 더 구체적인 단서를 신뢰한다.
"""

from __future__ import annotations

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


def guess_relation(*texts: str) -> Relation:
    """소속/비고/원문 등에서 관계를 추정한다.

    가장 긴 키워드가 이기고, 길이가 같으면 :data:`_TIE_BREAK` 순서를 따른다.
    아무 단서도 없으면 :attr:`Relation.OTHER`.
    """
    haystack = " ".join(str(text or "") for text in texts)
    if not haystack.strip():
        return Relation.OTHER

    best_relation = Relation.OTHER
    best_length = 0
    for relation in _TIE_BREAK:
        for keyword in KEYWORDS[relation]:
            if keyword in haystack and len(keyword) > best_length:
                best_relation = relation
                best_length = len(keyword)
    return best_relation


def all_keywords() -> frozenset[str]:
    """모든 관계 키워드의 합집합. 이름 추출 시 제외 후보로 쓰인다."""
    return frozenset(keyword for group in KEYWORDS.values() for keyword in group)
