"""퀘스트 · 경험치 · 레벨.

처음 쓰는 사람은 무엇을 먼저 해야 하는지 모른다. 도움말을 읽게 하는 대신
게임 튜토리얼처럼 **지금 할 일 하나만** 보여 주고, 해내면 칭찬한다.

퀘스트는 대부분 **앱 상태로 판정**한다(표에 하객이 있다 → '표로 변환' 완료).
버튼 클릭 같은 사건으로 판정하면, 세션 복구나 되돌리기로 같은 상태에 도달한
사용자가 영영 퀘스트를 깨지 못한다. 상태로 판정할 수 없는 것(복사 · 저장 ·
식대 확인)만 사건으로 기록한다.

한 번 깬 퀘스트는 다시 잠기지 않는다. 새 명단을 불러와 확인 필요가 생겨도
'확인 필요 0건 만들기' 업적은 남는다. 업적이 사라지면 게임이 아니라 벌이다.

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
    xp: int
    #: 강조할 화면 요소. UI가 이 이름으로 위젯을 찾는다.
    target: str


QUESTS: tuple[Quest, ...] = (
    Quest("paste", "명단 붙여넣기",
          "카톡·메모장 명단을 왼쪽 입력창에 붙여넣으세요. 연습은 [샘플 보기]로!", 50, "input"),
    Quest("parse", "표로 변환하기",
          "[자동 취합 및 파싱] 버튼 또는 Ctrl+Enter", 100, "parse"),
    Quest("review", "확인 필요 0건 만들기",
          "노란 행을 더블클릭해 이름·금액을 바로잡으세요", 150, "table"),
    Quest("meal", "식대 단가 맞추기",
          "예식장 계약서의 대인·소인 1인 단가를 입력하세요", 50, "meal"),
    Quest("copy", "감사 인사 복사하기",
          "표의 [복사] 버튼 → 카톡 창에서 Ctrl+V", 100, "table"),
    Quest("sent", "발송 완료 체크하기",
          "인사를 보낸 하객의 '발송' 칸을 체크하세요", 100, "table"),
    Quest("export", "엑셀로 저장하기",
          "[엑셀로 내보내기] 버튼 또는 Ctrl+S", 150, "export"),
)

_QUEST_KEYS = frozenset(quest.key for quest in QUESTS)

#: (필요 XP, 칭호). 마지막 칭호는 모든 퀘스트를 깨야 닿는다.
LEVELS: tuple[tuple[int, str], ...] = (
    (0, "신입 정산러"),
    (150, "명단 수집가"),
    (300, "금액 감별사"),
    (450, "감사 전령"),
    (sum(quest.xp for quest in QUESTS), "축의금 마스터"),
)

MAX_XP = LEVELS[-1][0]


@dataclass(frozen=True)
class QuestSnapshot:
    """퀘스트 판정에 필요한 앱 상태."""

    has_input: bool = False
    guest_count: int = 0
    review_count: int = 0
    sent_count: int = 0


@dataclass(frozen=True)
class Progress:
    xp: int
    level: int  # 1부터
    title: str
    #: 현재 레벨 구간 안에서의 진행(0.0 ~ 1.0). 만렙이면 1.0.
    level_ratio: float
    current: Quest | None
    cleared: int

    @property
    def all_clear(self) -> bool:
        return self.current is None


@dataclass(frozen=True)
class Update:
    """상태 반영 결과. UI는 이걸 보고 축하 연출을 한다."""

    newly_cleared: tuple[Quest, ...] = ()
    level_up: bool = False


def _level_for(xp: int) -> tuple[int, str, float]:
    index = max(i for i, (need, _) in enumerate(LEVELS) if xp >= need)
    need, title = LEVELS[index]
    if index + 1 >= len(LEVELS):
        return index + 1, title, 1.0
    next_need = LEVELS[index + 1][0]
    return index + 1, title, (xp - need) / (next_need - need)


class QuestTracker:
    """깬 퀘스트 집합을 관리한다."""

    def __init__(self, cleared: Iterable[str] = ()) -> None:
        # 저장 파일에 모르는 키가 있어도 무시한다(구버전·수동 편집 대비).
        self._cleared: set[str] = {key for key in cleared if key in _QUEST_KEYS}

    @property
    def cleared_keys(self) -> list[str]:
        """저장용. 퀘스트 선언 순서를 따른다."""
        return [quest.key for quest in QUESTS if quest.key in self._cleared]

    def is_cleared(self, key: str) -> bool:
        return key in self._cleared

    def progress(self) -> Progress:
        xp = sum(quest.xp for quest in QUESTS if quest.key in self._cleared)
        level, title, ratio = _level_for(xp)
        current = next((quest for quest in QUESTS if quest.key not in self._cleared), None)
        return Progress(xp, level, title, ratio, current, len(self._cleared))

    def mark(self, key: str) -> Update:
        """사건으로 판정하는 퀘스트(복사 · 저장 · 식대)를 깬다."""
        return self._clear({key} & _QUEST_KEYS)

    def observe(self, snapshot: QuestSnapshot) -> Update:
        """앱 상태로 판정할 수 있는 퀘스트를 깬다."""
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

    def _clear(self, keys: set[str]) -> Update:
        fresh = keys - self._cleared
        if not fresh:
            return Update()
        before = self.progress().level
        self._cleared |= fresh
        newly = tuple(quest for quest in QUESTS if quest.key in fresh)
        return Update(newly_cleared=newly, level_up=self.progress().level > before)
