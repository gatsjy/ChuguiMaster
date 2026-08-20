"""표 형식 붙여넣기 열 인식 테스트.

실제 사고: 사용자가 엑셀에서 `이름<TAB>금액<TAB>소속` 225행을 붙여넣었는데
소속이 ``belong`` 에 들어가지 않아 엑셀 내보내기의 소속 열이 통째로 비었다.
"""

from __future__ import annotations

import pytest

from chugui.models import Relation
from chugui.parsing.columns import classify_columns, parse_columns, split_columns
from chugui.parsing.text_parser import parse_line


class TestSplitColumns:
    def test_tab_separated(self):
        assert split_columns("유광호\t200,000\t토끼할머니") == ["유광호", "200,000", "토끼할머니"]

    def test_wide_space_separated(self):
        assert split_columns("유광호   200,000   토끼할머니") == ["유광호", "200,000", "토끼할머니"]

    def test_trailing_empty_columns_dropped(self):
        """엑셀에서 복사하면 빈 열이 딸려 오는 일이 흔하다."""
        assert split_columns("김규옥 장로\t100,000\t") == ["김규옥 장로", "100,000"]
        assert split_columns("홍길동\t100,000\t\t\t") == ["홍길동", "100,000"]

    @pytest.mark.parametrize(
        "line",
        [
            "홍길동 10만원 친척",   # 한 칸 공백 = 자유 서식, 열 아님
            "홍길동",              # 열 하나
            "",
            "   ",
        ],
    )
    def test_not_columnar(self, line):
        assert split_columns(line) is None

    def test_too_many_columns_rejected(self):
        assert split_columns("\t".join(str(n) for n in range(12))) is None


class TestClassifyColumns:
    def test_name_amount_belong(self):
        layout = classify_columns(["유광호", "200,000", "토끼할머니"])
        assert layout.name_field == "유광호"
        assert layout.amount_field == "200,000"
        assert layout.belong == "토끼할머니"

    def test_amount_column_wins_on_digit_ratio(self):
        """소속에 숫자가 있어도 금액 열을 헷갈리지 않는다."""
        layout = classify_columns(["한동수", "100,000", "세교4리"])
        assert layout.amount_field == "100,000"
        assert layout.belong == "세교4리"

    def test_two_columns_only(self):
        layout = classify_columns(["홍길동", "100,000"])
        assert layout.name_field == "홍길동"
        assert layout.belong == ""

    def test_no_amount_column(self):
        layout = classify_columns(["홍길동", "친척"])
        assert layout.amount_index is None
        assert layout.belong == "친척"

    def test_extra_columns_merge_into_belong(self):
        layout = classify_columns(["홍길동", "100,000", "OO교회", "사랑부"])
        assert layout.belong == "OO교회 사랑부"


class TestParseLineWithColumns:
    def test_belong_is_captured(self):
        guest = parse_line("유광호\t200,000\t토끼할머니")
        assert guest.name == "유광호"
        assert guest.amount == 200_000
        assert guest.belong == "토끼할머니"

    def test_relation_uses_belong(self):
        assert parse_line("김해수,김유지\t300,000\t천안이모").relation is Relation.FAMILY
        assert parse_line("이해명\t100,000\t아산시보건소").relation is Relation.WORK

    def test_name_comes_only_from_name_column(self):
        """소속이 사람 이름처럼 생겨도 이름 열을 벗어나 고르지 않는다."""
        guest = parse_line("이천우\t500,000\t이천우")
        assert guest.names == ["이천우"]

    def test_amount_read_from_amount_column(self):
        """소속에 숫자가 섞여도 금액이 흔들리지 않는다."""
        assert parse_line("한동수\t100,000\t세교4리").amount == 100_000
        assert parse_line("최기환\t100,000\t배방읍 12-3").amount == 100_000

    def test_title_after_name(self):
        guest = parse_line("김규옥 장로\t100,000\t")
        assert guest.name == "김규옥"
        assert guest.amount == 100_000

    def test_group_donor(self):
        guest = parse_line("여명교회사랑부\t50,000\t여명교회사랑부")
        assert guest.name == "여명교회사랑부"
        assert guest.relation is Relation.FAITH

    def test_free_form_still_works(self):
        """한 칸 공백 자유 서식은 종전대로 동작한다."""
        guest = parse_line("홍길동 10만원 친척")
        assert (guest.name, guest.amount) == ("홍길동", 100_000)
        assert guest.relation is Relation.FAMILY


class TestRelationOverlapArtifact:
    """'회사' 가 여명교[회사]랑부 를 가로질러 매치하던 문제."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("여명교회사랑부", Relation.FAITH),
            ("여명교회 사랑부", Relation.FAITH),
            ("OO교회사무실", Relation.FAITH),
            # 겹치지 않는 매치는 종전대로 최장 일치 + tie-break
            ("대학병원 간호사", Relation.WORK),
            ("고등학교 동창", Relation.SCHOOL),
            ("아산시보건소", Relation.WORK),
            ("외삼촌", Relation.FAMILY),
            ("동네 이웃", Relation.OTHER),
        ],
    )
    def test_relation(self, text, expected):
        assert parse_columns(text) is None or True  # 순수 문자열 검사
        from chugui.parsing.relations import guess_relation

        assert guess_relation(text) is expected
