"""하객 표 모델.

구버전은 ``QTableWidget`` 을 검색창 키 입력 한 번마다 통째로 다시 만들었다.
행마다 ``QComboBox`` + ``QPushButton`` + ``QCheckBox`` + 컨테이너 2개를 새로 생성하고
긴 스타일시트 문자열을 매번 파싱했으니, 하객 300명이면 키 입력 1회에 위젯 1,500개다.
게다가 표에서 셀을 직접 수정해도 ``guest_data`` 에는 반영되지 않아
다음 렌더링 때 **경고 없이 원복**됐다(무성 데이터 손실).

Model/View로 바꾸면 두 문제가 동시에 사라진다. 필터링은 프록시가 담당하므로
위젯을 다시 만들 일이 없고, 편집은 ``setData`` 를 통해 곧바로 모델에 기록된다.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import IntEnum
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QBrush, QColor

from chugui.models import (
    WARN_NO_AMOUNT,
    WARN_NO_NAME,
    Attendance,
    Guest,
    Payment,
    Relation,
    renumber,
)
from chugui.services.messages import MessageService

# 델리게이트가 셀에 담긴 Guest를 직접 꺼내 쓰기 위한 사용자 역할.
GUEST_ROLE = int(Qt.ItemDataRole.UserRole) + 1
MESSAGE_ROLE = int(Qt.ItemDataRole.UserRole) + 2


class Column(IntEnum):
    NO = 0
    NAME = 1
    AMOUNT = 2
    RELATION = 3
    ATTENDANCE = 4
    ADULT_TICKETS = 5
    CHILD_TICKETS = 6
    COPY = 7
    SENT = 8
    REVIEW = 9
    RAW = 10


HEADERS: dict[Column, str] = {
    Column.NO: "NO",
    Column.NAME: "성명",
    Column.AMOUNT: "축의금액",
    Column.RELATION: "관계",
    Column.ATTENDANCE: "참석",
    Column.ADULT_TICKETS: "대인",
    Column.CHILD_TICKETS: "소인",
    Column.COPY: "감사 메시지",
    Column.SENT: "발송",
    Column.REVIEW: "확인 필요",
    Column.RAW: "원문",
}

TOOLTIPS: dict[Column, str] = {
    Column.NAME: "더블클릭하면 이름을 직접 수정할 수 있습니다.",
    Column.AMOUNT: "더블클릭하면 금액을 직접 수정할 수 있습니다.",
    Column.RELATION: "관계를 바꾸면 감사 메시지 문구가 즉시 바뀝니다.",
    Column.ADULT_TICKETS: "발급된 대인 식권 수. 식대 차감의 기준입니다.",
    Column.CHILD_TICKETS: "발급된 소인 식권 수.",
    Column.COPY: "클릭하면 감사 메시지가 클립보드에 복사됩니다.",
    Column.SENT: "감사 인사를 실제로 보냈는지 직접 체크하세요.",
    Column.REVIEW: "파서가 확신하지 못한 항목입니다. 값을 확인해 주세요.",
}

_EDITABLE: frozenset[Column] = frozenset(
    {
        Column.NAME,
        Column.AMOUNT,
        Column.RELATION,
        Column.ATTENDANCE,
        Column.ADULT_TICKETS,
        Column.CHILD_TICKETS,
    }
)


class GuestTableModel(QAbstractTableModel):
    """하객 목록의 단일 진실 공급원."""

    guestsChanged = Signal()

    def __init__(self, message_service: MessageService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._guests: list[Guest] = []
        self._messages = message_service
        self._review_brush: QBrush | None = None

    def set_review_color(self, color: QColor | None) -> None:
        """확인이 필요한 행에 깔 배경색. 테마가 바뀌면 창이 다시 알려준다.

        경고를 '확인 필요' 열에만 적어두면 가로로 넓은 표에서 눈에 띄지 않는다.
        행 전체를 은은하게 물들여야 스크롤 중에도 즉시 보인다.
        """
        self._review_brush = QBrush(color) if color is not None else None
        if self._guests:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._guests) - 1, len(Column) - 1),
                [Qt.ItemDataRole.BackgroundRole],
            )

    # ------------------------------------------------------------- 목록 접근

    @property
    def guests(self) -> list[Guest]:
        return self._guests

    def guest_at(self, row: int) -> Guest | None:
        return self._guests[row] if 0 <= row < len(self._guests) else None

    def set_guests(self, guests: Sequence[Guest]) -> None:
        self.beginResetModel()
        self._guests = renumber(list(guests))
        self.endResetModel()
        self.guestsChanged.emit()

    def clear(self) -> None:
        self.set_guests([])

    def refresh_messages(self) -> None:
        """템플릿이 바뀌었을 때 메시지 열만 갱신한다."""
        if not self._guests:
            return
        top = self.index(0, Column.COPY)
        bottom = self.index(len(self._guests) - 1, Column.COPY)
        self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.DisplayRole, MESSAGE_ROLE])

    def message_for(self, row: int) -> str:
        guest = self.guest_at(row)
        return self._messages.generate(guest) if guest else ""

    def mark_sent(self, row: int, sent: bool = True) -> None:
        guest = self.guest_at(row)
        if guest is None or guest.sent_thanks == sent:
            return
        guest.sent_thanks = sent
        index = self.index(row, Column.SENT)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        self.guestsChanged.emit()

    # ------------------------------------------------- QAbstractTableModel

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._guests)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(Column)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation is not Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return HEADERS.get(Column(section), "")
        if role == Qt.ItemDataRole.ToolTipRole:
            return TOOLTIPS.get(Column(section))
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        column = Column(index.column())
        if column in _EDITABLE:
            flags |= Qt.ItemFlag.ItemIsEditable
        if column is Column.SENT:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        guest = self.guest_at(index.row())
        if guest is None:
            return None
        column = Column(index.column())

        if role == GUEST_ROLE:
            return guest
        if role == MESSAGE_ROLE:
            return self._messages.generate(guest)

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(guest, column)
        if role == Qt.ItemDataRole.EditRole:
            return self._edit_value(guest, column)
        if role == Qt.ItemDataRole.CheckStateRole and column is Column.SENT:
            return Qt.CheckState.Checked if guest.sent_thanks else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return self._alignment(column)
        if role == Qt.ItemDataRole.BackgroundRole and guest.needs_review:
            return self._review_brush
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(guest, column)
        return None

    def setData(  # noqa: N802
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if not index.isValid():
            return False
        guest = self.guest_at(index.row())
        if guest is None:
            return False
        column = Column(index.column())

        if role == Qt.ItemDataRole.CheckStateRole and column is Column.SENT:
            guest.sent_thanks = Qt.CheckState(value) == Qt.CheckState.Checked
            self.dataChanged.emit(index, index, [role])
            self.guestsChanged.emit()
            return True

        if role != Qt.ItemDataRole.EditRole or column not in _EDITABLE:
            return False

        if not self._apply_edit(guest, column, value):
            return False

        # 편집 결과에 따라 경고 상태가 달라질 수 있으므로 행 전체를 갱신한다.
        left = self.index(index.row(), 0)
        right = self.index(index.row(), len(Column) - 1)
        self.dataChanged.emit(left, right)
        self.guestsChanged.emit()
        return True

    # --------------------------------------------------------------- 내부

    def _apply_edit(self, guest: Guest, column: Column, value: Any) -> bool:
        if column is Column.NAME:
            name = str(value or "").strip()
            if not name:
                return False
            guest.name = name
            guest.names = [part.strip() for part in name.replace("&", ",").split(",") if part.strip()]
            guest.clear_warning(WARN_NO_NAME)
            return True

        if column is Column.AMOUNT:
            from chugui.parsing.amount import parse_amount

            amount = parse_amount(value)
            if amount < 0:
                return False
            guest.amount = amount
            if amount > 0:
                guest.clear_warning(WARN_NO_AMOUNT)
            else:
                guest.add_warning(WARN_NO_AMOUNT)
            return True

        if column is Column.RELATION:
            guest.relation = Relation.coerce(value)
            return True

        if column is Column.ATTENDANCE:
            attendance = Attendance.coerce(value)
            if attendance is guest.attendance:
                return True
            guest.attendance = attendance
            if attendance is Attendance.ABSENT:
                guest.adult_tickets = 0
                guest.child_tickets = 0
                guest.payment = Payment.TRANSFER
            elif guest.adult_tickets == 0:
                guest.adult_tickets = guest.head_count
            return True

        if column in (Column.ADULT_TICKETS, Column.CHILD_TICKETS):
            try:
                count = max(0, min(99, int(value)))
            except (TypeError, ValueError):
                return False
            if column is Column.ADULT_TICKETS:
                guest.adult_tickets = count
            else:
                guest.child_tickets = count
            return True

        return False

    @staticmethod
    def _display(guest: Guest, column: Column) -> Any:
        if column is Column.NO:
            return guest.guest_id
        if column is Column.NAME:
            return guest.name
        if column is Column.AMOUNT:
            return f"{guest.amount:,}"
        if column is Column.RELATION:
            return guest.relation.value
        if column is Column.ATTENDANCE:
            return guest.attendance.value
        if column is Column.ADULT_TICKETS:
            return guest.adult_tickets or ""
        if column is Column.CHILD_TICKETS:
            return guest.child_tickets or ""
        if column is Column.REVIEW:
            return " / ".join(guest.warnings)
        if column is Column.RAW:
            return guest.raw
        return None  # COPY / SENT 는 델리게이트와 체크박스가 그린다

    @staticmethod
    def _edit_value(guest: Guest, column: Column) -> Any:
        if column is Column.NAME:
            return guest.name
        if column is Column.AMOUNT:
            return guest.amount  # 정렬도 이 값을 쓴다 → 숫자 정렬
        if column is Column.RELATION:
            return guest.relation.value
        if column is Column.ATTENDANCE:
            return guest.attendance.value
        if column is Column.ADULT_TICKETS:
            return guest.adult_tickets
        if column is Column.CHILD_TICKETS:
            return guest.child_tickets
        if column is Column.NO:
            return guest.guest_id
        if column is Column.SENT:
            return guest.sent_thanks
        if column is Column.REVIEW:
            return len(guest.warnings)
        return GuestTableModel._display(guest, column)

    @staticmethod
    def _alignment(column: Column) -> Qt.AlignmentFlag:
        if column is Column.AMOUNT:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if column in (Column.NAME, Column.REVIEW, Column.RAW):
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        return Qt.AlignmentFlag.AlignCenter

    def _tooltip(self, guest: Guest, column: Column) -> str | None:
        if column is Column.REVIEW and guest.warnings:
            return "\n".join(f"• {warning}" for warning in guest.warnings)
        if column is Column.COPY:
            return self._messages.generate(guest)
        if column is Column.RAW:
            return guest.raw or None
        if column is Column.NAME and guest.aliases:
            return "별칭: " + ", ".join(guest.aliases)
        return TOOLTIPS.get(column)


class GuestFilterProxy(QSortFilterProxyModel):
    """검색어 / 관계 / 확인필요 필터. 정렬은 EditRole 기준이라 금액이 숫자로 정렬된다."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._query = ""
        self._relation: Relation | None = None
        self._review_only = False
        self._unsent_only = False
        self.setSortRole(Qt.ItemDataRole.EditRole)
        self.setDynamicSortFilter(True)

    def set_query(self, text: str) -> None:
        self._query = str(text or "").strip().lower()
        self.invalidate()

    def set_relation(self, relation: Relation | None) -> None:
        self._relation = relation
        self.invalidate()

    def set_review_only(self, enabled: bool) -> None:
        self._review_only = bool(enabled)
        self.invalidate()

    def set_unsent_only(self, enabled: bool) -> None:
        self._unsent_only = bool(enabled)
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if not isinstance(model, GuestTableModel):
            return True
        guest = model.guest_at(source_row)
        if guest is None:
            return False
        if self._relation is not None and guest.relation is not self._relation:
            return False
        if self._review_only and not guest.needs_review:
            return False
        if self._unsent_only and guest.sent_thanks:
            return False
        if not self._query:
            return True
        haystack = " ".join(
            [guest.name, guest.belong, guest.note, guest.raw, guest.relation.value, *guest.aliases]
        ).lower()
        return self._query in haystack
