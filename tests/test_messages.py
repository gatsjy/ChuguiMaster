"""감사 메시지 테스트."""

from __future__ import annotations

import pytest

from chugui.models import Attendance, Guest, Relation
from chugui.services.messages import (
    MessageService,
    default_templates,
    normalize_templates,
    render,
    unknown_placeholders,
)


def make_guest(**kwargs) -> Guest:
    defaults = {"name": "홍길동", "names": ["홍길동"], "amount": 100_000}
    return Guest(**{**defaults, **kwargs})


class TestNoCrashOnUserInput:
    """v1은 사용자 템플릿에 ``{`` 가 하나만 있어도 KeyError로 표 전체가 죽었다."""

    @pytest.mark.parametrize(
        "template",
        [
            "{name}님 감사합니다 {축하}",
            "{name}님 {} 감사합니다",
            "{name}님 {0} 감사합니다",
            "{ 홍길동 } 감사합니다",
            "감사합니다 }{",
            "{name}님 {{중괄호}} 감사",
        ],
    )
    def test_arbitrary_braces_never_raise(self, template):
        service = MessageService({Relation.OTHER.value: {Attendance.PRESENT.value: template}})
        result = service.generate(make_guest(relation=Relation.OTHER))
        assert isinstance(result, str)

    def test_unknown_placeholder_is_left_verbatim(self):
        assert render("{name}님 {축하}", {"name": "홍길동"}) == "홍길동님 {축하}"

    def test_unknown_placeholders_are_reported(self):
        assert unknown_placeholders("{name}님 {foo} {bar}") == ["bar", "foo"]
        assert unknown_placeholders("{name}님 {amount}") == []


class TestPlaceholders:
    def test_supported_placeholders(self):
        service = MessageService(
            {Relation.WORK.value: {Attendance.PRESENT.value: "{name}/{relation}/{amount}/{belong}"}}
        )
        guest = make_guest(relation=Relation.WORK, amount=150_000, belong="OO시보건소")
        assert service.generate(guest) == "홍길동/직장/기관/150,000/OO시보건소"

    def test_multi_name_reads_naturally(self):
        """v1은 복수 이름에 ' 분' 을 붙여 '…분님,' 이라는 문장을 만들었다."""
        guest = make_guest(name="김가족 & 김친지", names=["김가족", "김친지"], relation=Relation.FAMILY)
        message = MessageService().generate(guest)
        assert message.startswith("김가족 & 김친지님,")
        assert "분님" not in message


class TestTemplateSelection:
    @pytest.mark.parametrize("relation", list(Relation))
    @pytest.mark.parametrize("attendance", list(Attendance))
    def test_every_combination_produces_text(self, relation, attendance):
        guest = make_guest(relation=relation, attendance=attendance)
        message = MessageService().generate(guest)
        assert message and "{" not in message

    def test_school_template_avoids_vocative_particle(self):
        """'{name}야' 는 받침 없는 이름에서 '지훈야' 가 된다. 조사를 쓰지 않는다."""
        for name in ("민수", "지훈", "서연"):
            guest = make_guest(name=name, relation=Relation.SCHOOL)
            assert MessageService().generate(guest).startswith(f"{name},")

    def test_attendance_changes_message(self):
        service = MessageService()
        present = service.generate(make_guest(attendance=Attendance.PRESENT))
        absent = service.generate(make_guest(attendance=Attendance.ABSENT))
        assert present != absent


class TestTemplateNormalization:
    def test_missing_entries_fall_back_to_defaults(self):
        templates = normalize_templates({Relation.WORK.value: {Attendance.PRESENT.value: "안녕"}})
        assert templates[Relation.WORK.value][Attendance.PRESENT.value] == "안녕"
        assert templates[Relation.FAMILY.value] == default_templates()[Relation.FAMILY.value]

    @pytest.mark.parametrize("garbage", [None, [], "문자열", 42, {"없는관계": "문자열"}])
    def test_garbage_input_yields_valid_templates(self, garbage):
        templates = normalize_templates(garbage)
        assert set(templates) == {relation.value for relation in Relation}

    def test_service_isolation(self):
        """v1은 클래스 변수를 전역처럼 공유해 테스트 격리가 불가능했다."""
        first = MessageService({Relation.OTHER.value: {Attendance.PRESENT.value: "첫번째"}})
        second = MessageService()
        assert first.generate(make_guest(relation=Relation.OTHER)) == "첫번째"
        assert second.generate(make_guest(relation=Relation.OTHER)) != "첫번째"

    def test_reset(self):
        service = MessageService({Relation.OTHER.value: {Attendance.PRESENT.value: "임시"}})
        service.reset()
        assert service.templates == default_templates()
