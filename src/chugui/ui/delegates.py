"""표 셀 델리게이트.

셀 위젯(``setCellWidget``) 대신 델리게이트로 그린다. 위젯을 만들지 않으므로
행이 수백 개여도 필터링/스크롤이 즉각적이고, 편집기는 사용자가 실제로
편집할 때만 생성된다.

구버전은 관계 콤보박스의 ``currentTextChanged`` 핸들러 안에서 ``render_table()`` 을
호출했고, 그 함수의 첫 줄 ``setRowCount(0)`` 이 **지금 시그널을 발신 중인 그
콤보박스를 파괴**했다. Qt에서 전형적인 dangling C++ object 크래시 패턴이다.
델리게이트 방식에는 그런 재진입 자체가 존재하지 않는다.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QPoint, QPointF, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QComboBox,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from chugui.models import Attendance, Guest, Relation
from chugui.ui.guest_model import GUEST_ROLE, MESSAGE_ROLE
from chugui.ui.theme import Palette, badge_colors

_BADGE_RADIUS = 8
_BADGE_PADDING_X = 10
_BADGE_PADDING_Y = 4


class _PaletteAware:
    """팔레트 교체를 지원하는 델리게이트 공통 믹스인."""

    def __init__(self, palette: Palette) -> None:
        self._palette = palette

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette


#: 배지 안 ▼ 표시가 차지하는 폭.
_CHEVRON_SPACE = 14


def draw_chevron(painter: QPainter, center: QPoint, color: QColor) -> None:
    """아래를 가리키는 작은 삼각형. '누르면 목록이 열린다' 는 표시.

    글자(▾)로 쓰지 않고 그린다. 픽셀 폰트에 그 글자가 없으면 네모가 나온다.
    """
    x, y = center.x(), center.y()
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(QPolygonF([QPointF(x - 4, y - 2), QPointF(x + 4, y - 2), QPointF(x, y + 3)]))
    painter.restore()


class _ClickOpensList:
    """한 번 클릭하면 바로 목록이 열리는 콤보 편집.

    예전에는 더블클릭해야 콤보가 생기고, 그 콤보를 한 번 더 눌러야 목록이 보였다.
    배지가 그냥 글자처럼 보여서 고를 수 있다는 걸 알아채기 어려웠다.
    """

    def editorEvent(self, event, model, option, index):  # noqa: N802
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and index.flags() & Qt.ItemFlag.ItemIsEditable
        ):
            view = self.parent()
            if isinstance(view, QAbstractItemView):
                view.setCurrentIndex(index)
                view.edit(index)
                return True
        return QStyledItemDelegate.editorEvent(self, event, model, option, index)

    def _list_editor(self, parent: QWidget, values: list[str]) -> QComboBox:
        editor = QComboBox(parent)
        editor.addItems(values)
        # 고르면 곧바로 반영하고 닫는다. 칸 밖을 한 번 더 누를 필요가 없다.
        editor.activated.connect(lambda _index, e=editor: self._finish(e))
        # 값이 채워진 뒤에 목록을 연다. editor 가 먼저 사라지면 호출되지 않는다.
        QTimer.singleShot(0, editor, editor.showPopup)
        return editor

    def _finish(self, editor: QComboBox) -> None:
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)


class RelationBadgeDelegate(_ClickOpensList, _PaletteAware, QStyledItemDelegate):
    """관계를 색 배지(▼ 포함)로 그리고, 한 번 클릭하면 목록을 연다."""

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        QStyledItemDelegate.__init__(self, parent)
        _PaletteAware.__init__(self, palette)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        guest = index.data(GUEST_ROLE)
        if not isinstance(guest, Guest):
            super().paint(painter, option, index)
            return

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        colors = badge_colors(self._palette, guest.relation)
        text = guest.relation.value

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        font = QFont(option.font)
        font.setBold(True)
        font.setPointSizeF(max(8.0, option.font.pointSizeF() - 0.5))
        painter.setFont(font)

        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(text)
        badge_width = min(option.rect.width() - 8, text_width + _BADGE_PADDING_X * 2 + _CHEVRON_SPACE)
        badge_height = metrics.height() + _BADGE_PADDING_Y * 2

        badge_rect = QRect(0, 0, badge_width, badge_height)
        badge_rect.moveCenter(option.rect.center())

        # 마우스를 올리면 테두리가 밝아져 누를 수 있는 것임을 알린다.
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        border = QColor(self._palette.accent if hovered else colors.border)
        painter.setPen(border)
        painter.setBrush(QColor(colors.background))
        painter.drawRoundedRect(badge_rect, _BADGE_RADIUS, _BADGE_RADIUS)

        text_rect = badge_rect.adjusted(0, 0, -_CHEVRON_SPACE, 0)
        painter.setPen(QColor(colors.foreground))
        text_rect = text_rect.adjusted(_BADGE_PADDING_X // 2, 0, 0, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
        draw_chevron(
            painter,
            QPoint(badge_rect.right() - _CHEVRON_SPACE // 2 - 3, badge_rect.center().y()),
            QColor(colors.foreground),
        )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        base = super().sizeHint(option, index)
        return QSize(max(base.width(), 108), max(base.height(), 32))

    def createEditor(  # noqa: N802
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        return self._list_editor(parent, Relation.values())

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QComboBox):
            editor.setCurrentText(str(index.data(Qt.ItemDataRole.EditRole) or ""))

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class AttendanceDelegate(_ClickOpensList, QStyledItemDelegate):
    """참석 / 불참(송금) 선택. 관계와 같은 방식(▼ 표시 · 한 번 클릭)으로 연다."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        super().paint(painter, option, index)
        color = QColor(option.palette.text().color())
        if not option.state & QStyle.StateFlag.State_MouseOver:
            color.setAlpha(140)
        draw_chevron(painter, QPoint(option.rect.right() - 12, option.rect.center().y()), color)

    def createEditor(  # noqa: N802
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        return self._list_editor(parent, [Attendance.PRESENT.value, Attendance.ABSENT.value])

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QComboBox):
            editor.setCurrentText(str(index.data(Qt.ItemDataRole.EditRole) or ""))

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class TicketSpinDelegate(QStyledItemDelegate):
    """식권 수 입력(0~99)."""

    def createEditor(  # noqa: N802
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        editor = QSpinBox(parent)
        editor.setRange(0, 99)
        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return editor

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QSpinBox):
            try:
                editor.setValue(int(index.data(Qt.ItemDataRole.EditRole) or 0))
            except (TypeError, ValueError):
                editor.setValue(0)

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QSpinBox):
            editor.interpretText()
            model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)


class CopyButtonDelegate(_PaletteAware, QStyledItemDelegate):
    """'복사' 버튼처럼 보이는 셀. 실제 위젯은 만들지 않는다."""

    clicked = Signal(QModelIndex)

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        QStyledItemDelegate.__init__(self, parent)
        _PaletteAware.__init__(self, palette)
        self._hover_row = -1

    def set_hover_row(self, row: int) -> None:
        self._hover_row = row

    def _button_rect(self, option_rect: QRect) -> QRect:
        rect = QRect(option_rect)
        rect.adjust(6, 5, -6, -5)
        return rect

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        guest = index.data(GUEST_ROLE)
        palette = self._palette

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        sent = bool(getattr(guest, "sent_thanks", False))
        hovered = index.row() == self._hover_row and bool(option.state & QStyle.StateFlag.State_MouseOver)

        if sent:
            background = palette.positive_surface
            foreground = palette.positive
            border = palette.positive_border
            label = "✓ 복사됨"
        else:
            background, foreground, border = palette.surface_alt, palette.accent, palette.accent
            label = "📋 복사"
        if hovered:
            background, foreground = palette.accent, "#ffffff"

        rect = self._button_rect(option.rect)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor(border))
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, 6, 6)

        font = QFont(option.font)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(foreground))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(110, 34)

    def editorEvent(  # noqa: N802
        self, event: QEvent, model, option: QStyleOptionViewItem, index: QModelIndex
    ) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease:
            position: QPoint = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if self._button_rect(option.rect).contains(position):
                self.clicked.emit(QModelIndex(index))
                return True
        return False

    def helpEvent(self, event, view, option, index) -> bool:  # noqa: N802
        message = index.data(MESSAGE_ROLE)
        if message:
            from PySide6.QtWidgets import QToolTip

            QToolTip.showText(event.globalPos(), str(message), view)
            return True
        return super().helpEvent(event, view, option, index)


def install_hover_tracking(view: QAbstractItemView, delegate: CopyButtonDelegate, column: int) -> None:
    """마우스가 올라간 행을 델리게이트에 알려 호버 효과를 준다."""
    view.setMouseTracking(True)

    def _on_entered(index: QModelIndex) -> None:
        row = index.row() if index.column() == column else -1
        if row != delegate._hover_row:
            delegate.set_hover_row(row)
            view.viewport().update()

    view.entered.connect(_on_entered)
