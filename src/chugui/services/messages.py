"""감사 메시지 생성.

구버전 결함 두 가지를 함께 고친다.

1. **``str.format`` 크래시** - 사용자가 자유 편집하는 템플릿에 ``.format()``을
   걸어서, 문구에 ``{`` 가 하나만 들어가도 ``KeyError``가 났다. 그 예외가
   표 렌더링 루프 안에서 터지므로 표 전체가 죽고, 잘못된 템플릿은 JSON에
   영구 저장되어 재실행해도 계속 죽었다. 여기서는 치환을 정규식으로 하고
   모르는 자리표시자는 **그대로 둔다**. 사용자 입력으로는 절대 예외가 나지 않는다.
2. **전역 가변 상태** - 클래스 변수 ``_templates`` 를 모듈 전역처럼 공유해
   테스트 격리가 불가능했다. 여기서는 저장소를 주입받는 인스턴스다.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping

from chugui.models import Attendance, Guest, Relation

logger = logging.getLogger(__name__)

Templates = dict[str, dict[str, str]]

# 자리표시자는 {name} 형태. 알 수 없는 이름은 치환하지 않고 원문을 유지한다.
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

SUPPORTED_PLACEHOLDERS: tuple[str, ...] = ("name", "relation", "amount", "belong")

DEFAULT_TEMPLATES: Templates = {
    Relation.FAMILY.value: {
        Attendance.PRESENT.value: (
            "{name}님, 저희 결혼식에 와주셔서 진심으로 감사했습니다. "
            "그 자리에 계셔주신 것만으로 큰 힘이 되었어요. 주신 마음 잘 간직하며 살겠습니다."
        ),
        Attendance.ABSENT.value: (
            "{name}님, 마음 전해주셔서 감사합니다. "
            "뵙지 못해 아쉬웠지만 축하해주시는 마음은 충분히 전해졌어요. 곧 인사드리러 가겠습니다."
        ),
    },
    Relation.WORK.value: {
        Attendance.PRESENT.value: (
            "{name}님, 귀한 시간 내어 함께해주셔서 감사합니다. "
            "축하해주신 마음 잊지 않고, 좋은 모습으로 보답하겠습니다."
        ),
        Attendance.ABSENT.value: (
            "{name}님, 따뜻한 마음 전해주셔서 감사합니다. "
            "덕분에 더 든든하게 시작합니다. 다음에 뵙고 직접 인사드리겠습니다."
        ),
    },
    Relation.FAITH.value: {
        Attendance.PRESENT.value: (
            "{name}님, 함께해주시고 축복해주셔서 감사합니다. "
            "기도해주신 마음 기억하며 서로 아끼며 살겠습니다."
        ),
        Attendance.ABSENT.value: (
            "{name}님, 멀리서도 마음 모아 축복해주셔서 감사합니다. "
            "그 마음에 부끄럽지 않게 잘 살겠습니다."
        ),
    },
    Relation.SCHOOL.value: {
        Attendance.PRESENT.value: (
            "{name}, 와줘서 정말 고마웠어. "
            "바쁜 거 아는데 시간 내준 마음이 더 크게 느껴지더라. 조만간 얼굴 보자."
        ),
        Attendance.ABSENT.value: (
            "{name}, 마음 보내줘서 고마워. "
            "못 봐서 아쉬웠지만 축하해주는 마음 잘 받았어. 조만간 따로 보자."
        ),
    },
    Relation.OTHER.value: {
        Attendance.PRESENT.value: (
            "{name}님, 저희 결혼식에 함께해주셔서 감사합니다. 축하해주신 마음 오래 기억하겠습니다."
        ),
        Attendance.ABSENT.value: (
            "{name}님, 축하와 마음 전해주셔서 감사합니다. 잊지 않고 잘 간직하겠습니다."
        ),
    },
}

_FALLBACK = "{name}님, 축하해주셔서 진심으로 감사합니다."


def default_templates() -> Templates:
    """기본 템플릿의 깊은 복사본."""
    return {relation: dict(by_status) for relation, by_status in DEFAULT_TEMPLATES.items()}


def normalize_templates(raw: object) -> Templates:
    """어떤 입력이 와도 유효한 템플릿 구조를 만든다(누락 항목은 기본값으로 보충)."""
    result = default_templates()
    if not isinstance(raw, Mapping):
        return result
    for relation_key, by_status in raw.items():
        relation = Relation.coerce(relation_key).value
        if not isinstance(by_status, Mapping):
            continue
        for status_key, text in by_status.items():
            status = Attendance.coerce(status_key).value
            if isinstance(text, str) and text.strip():
                result[relation][status] = text.strip()
    return result


def unknown_placeholders(text: str) -> list[str]:
    """지원하지 않는 자리표시자 목록. 저장 시 사용자에게 안내하는 용도."""
    return sorted(
        {name for name in _PLACEHOLDER_RE.findall(str(text or "")) if name not in SUPPORTED_PLACEHOLDERS}
    )


def render(template: str, values: Mapping[str, str]) -> str:
    """자리표시자를 치환한다. 모르는 이름은 원문 그대로 남긴다(예외 없음)."""

    def _substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        return values.get(key, match.group(0))

    return _PLACEHOLDER_RE.sub(_substitute, str(template or ""))


class MessageService:
    """하객 한 명에 대한 감사 메시지를 만든다."""

    def __init__(self, templates: Templates | None = None) -> None:
        self._templates: Templates = normalize_templates(templates)

    # ------------------------------------------------------------ 템플릿 접근

    @property
    def templates(self) -> Templates:
        return {relation: dict(by_status) for relation, by_status in self._templates.items()}

    def set_templates(self, templates: Templates) -> None:
        self._templates = normalize_templates(templates)

    def reset(self) -> None:
        self._templates = default_templates()

    def template_for(self, relation: Relation, attendance: Attendance) -> str:
        by_status = self._templates.get(relation.value) or self._templates[Relation.OTHER.value]
        return by_status.get(attendance.value) or by_status.get(Attendance.PRESENT.value) or _FALLBACK

    # ------------------------------------------------------------------ 생성

    def generate(self, guest: Guest) -> str:
        """하객에게 보낼 감사 메시지."""
        template = self.template_for(guest.relation, guest.attendance)
        values = {
            "name": guest.name or "하객",
            "relation": guest.relation.value,
            "belong": guest.belong,
            "amount": f"{guest.amount:,}",
        }
        return render(template, values).strip()
