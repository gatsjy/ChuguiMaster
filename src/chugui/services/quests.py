"""처음 쓰는 사람을 위한 단계 안내.

처음 쓰는 사람은 무엇을 먼저 해야 하는지 모른다. 도움말을 읽게 하는 대신
**지금 할 일 하나만** 보여 준다.

단계는 대부분 **앱 상태로 판정**한다(표에 하객이 있다 → '표로 변환' 완료).
버튼 클릭 같은 사건으로 판정하면, 세션 복구나 되돌리기로 같은 상태에 도달한
사용자가 영영 다음 단계로 넘어가지 못한다. 상태로 판정할 수 없는 것(복사 · 저장 ·
식대 확인)만 사건으로 기록한다.

한 번 마친 단계는 되돌아가지 않는다. 새 명단을 불러와 확인 필요가 생겨도
안내가 1단계로 돌아가면 이미 익숙한 사람에게는 잔소리일 뿐이다.

Qt에 의존하지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Quest:
    key: str
    title: str
    hint: str
    #: 강조할 화면 요소. UI가 이 이름으로 위젯을 찾는다.
    target: str


QUESTS: tuple[Quest, ...] = (
    Quest("paste", "명단 붙여넣기",
          "카톡·메모장 명단을 왼쪽 입력창에 붙여넣으세요. 연습하려면 [샘플 보기]를 누르세요.", "input"),
    Quest("parse", "표로 변환하기", "[자동 취합 및 파싱] 버튼 또는 Ctrl+Enter", "parse"),
    Quest("review", "확인 필요 항목 고치기", "노란 행을 더블클릭해 이름·금액을 바로잡으세요.", "table"),
    Quest("meal", "식대 단가 입력하기", "예식장 계약서의 대인·소인 1인 단가를 입력하세요.", "meal"),
    Quest("copy", "감사 인사 복사하기", "표의 [복사] 버튼을 누른 뒤 카톡 창에서 Ctrl+V", "table"),
    Quest("sent", "발송 완료 체크하기", "인사를 보낸 하객의 '발송' 칸을 체크하세요.", "table"),
    Quest("export", "엑셀로 저장하기", "[엑셀로 내보내기] 버튼 또는 Ctrl+S", "export"),
)

_QUEST_KEYS = frozenset(quest.key for quest in QUESTS)


@dataclass(frozen=True)
class QuestSnapshot:
    """단계 판정에 필요한 앱 상태."""

    has_input: bool = False
    guest_count: int = 0
    review_count: int = 0
    sent_count: int = 0


@dataclass(frozen=True)
class Progress:
    current: Quest | None
    cleared: int

    @property
    def total(self) -> int:
        return len(QUESTS)

    @property
    def ratio(self) -> float:
        return self.cleared / self.total

    @property
    def all_clear(self) -> bool:
        return self.current is None


class QuestTracker:
    """마친 단계 집합을 관리한다."""

    def __init__(self, cleared: Iterable[str] = ()) -> None:
        # 저장 파일에 모르는 키가 있어도 무시한다(구버전·수동 편집 대비).
        self._cleared: set[str] = {key for key in cleared if key in _QUEST_KEYS}

    @property
    def cleared_keys(self) -> list[str]:
        """저장용. 단계 선언 순서를 따른다."""
        return [quest.key for quest in QUESTS if quest.key in self._cleared]

    def is_cleared(self, key: str) -> bool:
        return key in self._cleared

    def progress(self) -> Progress:
        current = next((quest for quest in QUESTS if quest.key not in self._cleared), None)
        return Progress(current, len(self._cleared))

    def mark(self, key: str) -> tuple[Quest, ...]:
        """사건으로 판정하는 단계(복사 · 저장 · 식대)를 마친다. 새로 마친 단계를 돌려준다."""
        return self._clear({key} & _QUEST_KEYS)

    def observe(self, snapshot: QuestSnapshot) -> tuple[Quest, ...]:
        """앱 상태로 판정할 수 있는 단계를 마친다. 새로 마친 단계를 돌려준다."""
        done: set[str] = set()
        if snapshot.has_input or snapshot.guest_count:
            done.add("paste")
        if snapshot.guest_count:
            done.add("parse")
            if not snapshot.review_count:
                done.add("review")
        if snapshot.sent_count:
            done.add("sent")
        return self._clear(done)

    def reset(self) -> None:
        self._cleared.clear()

    def _clear(self, keys: set[str]) -> tuple[Quest, ...]:
        fresh = keys - self._cleared
        self._cleared |= fresh
        return tuple(quest for quest in QUESTS if quest.key in fresh)
