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

from PySide6.QtCore import QEvent, QModelIndex, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
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


class RelationBadgeDelegate(_PaletteAware, QStyledItemDelegate):
    """관계를 색 배지로 그리고, 편집 시 콤보박스를 띄운다."""

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
        badge_width = min(option.rect.width() - 8, text_width + _BADGE_PADDING_X * 2)
        badge_height = metrics.height() + _BADGE_PADDING_Y * 2

        badge_rect = QRect(0, 0, badge_width, badge_height)
        badge_rect.moveCenter(option.rect.center())

        painter.setPen(QColor(colors.border))
        painter.setBrush(QColor(colors.background))
        painter.drawRoundedRect(badge_rect, _BADGE_RADIUS, _BADGE_RADIUS)

        painter.setPen(QColor(colors.foreground))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        base = super().sizeHint(option, index)
        return QSize(max(base.width(), 108), max(base.height(), 32))

    def createEditor(  # noqa: N802
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        editor = QComboBox(parent)
        editor.addItems(Relation.values())
        return editor

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QComboBox):
            editor.setCurrentText(str(index.data(Qt.ItemDataRole.EditRole) or ""))

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class AttendanceDelegate(QStyledItemDelegate):
    """참석 / 불참(송금) 선택."""

    def createEditor(  # noqa: N802
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        editor = QComboBox(parent)
        editor.addItems([Attendance.PRESENT.value, Attendance.ABSENT.value])
        return editor

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
