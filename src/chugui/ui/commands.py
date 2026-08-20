"""되돌릴 수 있는 표 편집 명령.

표에서 금액을 잘못 고치면 되돌릴 방법이 없었다. 자동 저장은 잘못 고친 값을
성실히 저장할 뿐이고, 스냅샷은 파괴 연산 단위라 셀 하나까지 되짚지 못한다.

Qt의 ``QUndoStack`` 에 얹으면 ``Ctrl+Z`` / ``Ctrl+Y`` 가 공짜로 따라온다.
명령은 편집 **행위**가 아니라 **값의 전후**를 들고 있으므로,
되돌리기와 다시하기가 같은 코드 경로를 쓴다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:  # pragma: no cover - 순환 참조 회피
    from chugui.ui.guest_model import Column, GuestTableModel


class EditGuestCommand(QUndoCommand):
    """셀 하나의 값 변경."""

    def __init__(
        self,
        model: GuestTableModel,
        row: int,
        column: Column,
        old_value: Any,
        new_value: Any,
        label: str,
    ) -> None:
        super().__init__(label)
        self._model = model
        self._row = row
        self._column = column
        self._old_value = old_value
        self._new_value = new_value

    def redo(self) -> None:  # QUndoStack.push 가 최초 1회 호출한다
        self._model.commit_edit(self._row, self._column, self._new_value)

    def undo(self) -> None:
        self._model.commit_edit(self._row, self._column, self._old_value)
