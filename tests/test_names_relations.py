"""이름 추출 · 관계 분류 테스트."""

from __future__ import annotations

import pytest

from chugui.models import Relation
from chugui.parsing.names import extract_names, format_display_name, split_names
from chugui.parsing.relations import guess_relation


class TestNamesSurviveCharacterClassBug:
    """v1은 ``[\\d만,원식권불참송금현금계좌이체]`` 로 **글자 단위** 삭제를 했다.

    그래서 '이', '체', '권', '원', '식' 이 든 실명이 통째로 사라졌다.
    """

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("이체리 100000 친구", "이체리"),
            ("권원식 100000 지인", "권원식"),
            ("김만수 50000 동창", "김만수"),
            ("박서원 100000 회사", "박서원"),
            ("한계장 100000 D보건지소", "한계장"),
            ("현금자 50000 이웃", "현금자"),
        ],
    )
    def test_names_with_marker_characters(self, line, expected):
        names, _, found = extract_names(line)
        assert found is True
        assert names == [expected]


class TestNamesContainingKinshipTerms:
    """v1의 부분 문자열 차단 목록은 '박이모'까지 탈락시켜 '하객N'으로 만들었다."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("박이모 1000000 B이모", "박이모"),
            ("한고모 2000000 친척", "한고모"),
            ("이삼촌 200000 삼촌", "이삼촌"),
            ("최성도 100000 OO교회", "최성도"),
        ],
    )
    def test_kinship_substring_names(self, line, expected):
        names, _, found = extract_names(line)
        assert found is True
        assert names == [expected]


class TestOrganizationTokensRejected:
    @pytest.mark.parametrize(
        "line",
        ["1 OO교회 100000", "A보건지소 50000", "5 OO시보건소 100000"],
    )
    def test_org_only_line_has_no_name(self, line):
        _, _, found = extract_names(line, fallback="하객1")
        assert found is False

    def test_org_token_skipped_but_name_found(self):
        names, _, found = extract_names("16 이과장 100000 OO시보건소")
        assert (names, found) == (["이과장"], True)


class TestMultipleNames:
    def test_comma_separated(self):
        names, _, found = extract_names("11 김가족,김친지 300000 이모")
        assert (names, found) == (["김가족", "김친지"], True)

    def test_middle_dot(self):
        names, _, _ = extract_names("진부부·신부부 100000")
        assert names == ["진부부", "신부부"]

    def test_display_name(self):
        assert format_display_name(["김가족", "김친지"]) == "김가족 & 김친지"
        assert format_display_name(["홍길동"]) == "홍길동"
        assert format_display_name([]) == ""

    def test_split_names(self):
        assert split_names("김가족, 김친지") == ["김가족", "김친지"]


class TestAliases:
    def test_paren_alias_is_captured(self):
        names, aliases, found = extract_names("25 김성도(조성도) 50000 OO교회")
        assert (names, found) == (["김성도"], True)
        assert aliases == ["조성도"]


class TestFallback:
    def test_no_name_returns_fallback_and_flag(self):
        names, _, found = extract_names("100000", fallback="하객7")
        assert (names, found) == (["하객7"], False)


class TestRelationLongestMatchWins:
    """v1은 dict 선언 순서상 처음 걸린 키워드를 채택해 결과가 뒤집혔다."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("대학병원 간호사", Relation.WORK),      # '대학'(2) < '대학병원'? → '병원' 우선
            ("고등학교 동창", Relation.SCHOOL),
            ("OO시보건소", Relation.WORK),
            ("OO교회 집사", Relation.FAITH),
            ("외삼촌", Relation.FAMILY),
            ("동네 이웃", Relation.OTHER),
            ("", Relation.OTHER),
            ("아무 단서 없음", Relation.OTHER),
        ],
    )
    def test_relation(self, text, expected):
        assert guess_relation(text) is expected

    def test_multiple_sources_combined(self):
        assert guess_relation("", "OO교회 권사님") is Relation.FAITH
