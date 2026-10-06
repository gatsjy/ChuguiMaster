"""되돌릴 수 있는 표 편집 명령.

표에서 금액을 잘못 고치면 되돌릴 방법이 없었다. 자동 저장은 잘못 고친 값을
성실히 저장할 뿐이고, 스냅샷은 파괴 연산 단위라 셀 하나까지 되짚지 못한다.

Qt의 ``QUndoStack`` 에 얹으면 ``Ctrl+Z`` / ``Ctrl+Y`` 가 공짜로 따라온다.
명령은 편집 **행위**가 아니라 **값의 전후**를 들고 있으므로,
되돌리기와 다시하기가 같은 코드 경로를 쓴다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:  # pragma: no cover - 순환 참조 회피
    from chugui.models import Guest
    from chugui.ui.guest_model import Column, GuestTableModel

#: 편집에 딸린 부수 효과. (다시 할 때, 되돌릴 때) 순서다.
SideEffects = tuple[Callable[[], None], Callable[[], None]]


class EditGuestCommand(QUndoCommand):
    """셀 하나의 값 변경.

    ``side_effects`` 는 셀 값 말고도 함께 되돌려야 하는 것을 담는다.
    관계를 바꾸면 소속 사전이 그 값을 배우는데, 학습이 명령 밖에 있으면
    Ctrl+Z 로 표만 돌아가고 사전에는 오클릭한 값이 남는다.
    """

    def __init__(
        self,
        model: GuestTableModel,
        row: int,
        column: Column,
        old_value: Any,
        new_value: Any,
        label: str,
        side_effects: SideEffects | None = None,
    ) -> None:
        super().__init__(label)
        self._model = model
        self._row = row
        self._column = column
        self._old_value = old_value
        self._new_value = new_value
        self._side_effects = side_effects

    def redo(self) -> None:  # QUndoStack.push 가 최초 1회 호출한다
        if self._model.commit_edit(self._row, self._column, self._new_value) and self._side_effects:
            self._side_effects[0]()

    def undo(self) -> None:
        if self._model.commit_edit(self._row, self._column, self._old_value) and self._side_effects:
            self._side_effects[1]()


class RemoveGuestsCommand(QUndoCommand):
    """줄 삭제. 되돌리면 지운 줄이 원래 자리로 돌아온다.

    셀 편집 명령은 행 번호를 들고 있다. 삭제 · 복원이 스택 순서(LIFO)대로만 일어나므로
    그 번호가 가리키는 줄은 되돌리기 · 다시하기 내내 같은 하객으로 유지된다.
    """

    def __init__(self, model: GuestTableModel, rows: list[int], label: str) -> None:
        super().__init__(label)
        self._model = model
        self._rows = list(rows)
        self._removed: list[tuple[int, Guest]] = []

    def redo(self) -> None:
        self._removed = self._model.commit_remove(self._rows)

    def undo(self) -> None:
        self._model.commit_insert(self._removed)
