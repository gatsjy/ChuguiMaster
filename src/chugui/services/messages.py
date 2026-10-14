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

# 기본 문구는 카톡으로 바로 보내는 말투(구어체)다. 어른 · 직장 · 교회 분께는 해요체,
# 친구에게는 반말. 받는 사람이 다양하므로 이모티콘은 넣지 않는다(필요하면 템플릿에서 더한다).
DEFAULT_TEMPLATES: Templates = {
    Relation.FAMILY.value: {
        Attendance.PRESENT.value: (
            "{name}님, 결혼식에 와 주셔서 정말 감사해요! "
            "와 주신 것만으로도 큰 힘이 됐어요. 주신 마음 잊지 않고 예쁘게 잘 살게요."
        ),
        Attendance.ABSENT.value: (
            "{name}님, 마음 보내 주셔서 정말 감사해요. "
            "직접 못 뵈어서 아쉬웠는데, 축하해 주신 마음은 잘 받았어요. 조만간 찾아뵐게요!"
        ),
    },
    Relation.WORK.value: {
        Attendance.PRESENT.value: (
            "{name}님, 바쁘신데 결혼식까지 와 주셔서 정말 감사해요. "
            "축하해 주신 마음 잊지 않고, 앞으로 더 열심히 할게요!"
        ),
        Attendance.ABSENT.value: (
            "{name}님, 따뜻한 마음 보내 주셔서 감사해요. "
            "덕분에 든든하게 시작해요. 다음에 뵐 때 직접 인사드릴게요!"
        ),
    },
    Relation.FAITH.value: {
        Attendance.PRESENT.value: (
            "{name}님, 와 주셔서 함께 축복해 주시고 정말 감사해요. "
            "기도해 주신 마음 기억하면서 서로 아끼며 잘 살게요."
        ),
        Attendance.ABSENT.value: (
            "{name}님, 멀리서도 마음 모아 축복해 주셔서 감사해요. "
            "그 마음에 부끄럽지 않게 잘 살게요!"
        ),
    },
    Relation.SCHOOL.value: {
        Attendance.PRESENT.value: (
            "{name}, 와 줘서 진짜 고마워! "
            "바쁜 거 다 아는데 시간 내 줘서 더 감동이었어. 조만간 밥 한번 먹자!"
        ),
        Attendance.ABSENT.value: (
            "{name}, 마음 보내 줘서 진짜 고마워. "
            "얼굴 못 봐서 아쉬웠는데 축하해 준 마음은 잘 받았어. 조만간 따로 보자!"
        ),
    },
    Relation.OTHER.value: {
        Attendance.PRESENT.value: (
            "{name}님, 결혼식에 와 주셔서 정말 감사해요. 축하해 주신 마음 오래오래 기억할게요!"
        ),
        Attendance.ABSENT.value: (
            "{name}님, 축하하는 마음 보내 주셔서 정말 감사해요. 잊지 않고 잘 간직할게요!"
        ),
    },
}

_FALLBACK = "{name}님, 축하해 주셔서 정말 감사해요!"


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
