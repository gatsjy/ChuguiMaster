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

import weakref

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
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
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


class TicketStepperDelegate(_PaletteAware, QStyledItemDelegate):
    """식권 수 증감 버튼(▲ / ▼) 델리게이트.

    **▲ / ▼ 버튼 안을 눌렀을 때만** 값이 바뀐다. 숫자를 누르면 줄이 선택될 뿐이고,
    숫자를 더블클릭하면 직접 입력할 수 있다.

    예전에는 칸 어디를 눌러도 위쪽 절반이면 +1, 아래쪽 절반이면 -1 이었다.
    줄을 고르려고 숫자를 누르기만 해도 식권 수(= 식대)가 조용히 바뀌었다.
    마우스 휠로 바꾸는 기능은 넣지 않는다. 표를 스크롤하다 지나가는 칸의 값이
    바뀌는 사고가 나기 때문이다(그리고 표가 휠 이벤트를 칸에 넘기지도 않는다).
    """

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        QStyledItemDelegate.__init__(self, parent)
        _PaletteAware.__init__(self, palette)
        self._hover_row = -1
        self._hover_col = -1
        self._hover_btn = 0  # 0: none, 1: up, -1: down

    def set_hover_row(self, row: int) -> None:
        if self._hover_row != row:
            self._hover_row = row
            if row < 0:
                self._hover_col = -1
                self._hover_btn = 0

    def _container_rect(self, option_rect: QRect) -> QRect:
        w = 20
        h = 24
        x = option_rect.right() - w - 4
        y = option_rect.center().y() - (h // 2)
        return QRect(x, y, w, h)

    def _button_rects(self, option_rect: QRect) -> tuple[QRect, QRect]:
        c = self._container_rect(option_rect)
        half_h = c.height() // 2
        up_rect = QRect(c.left(), c.top(), c.width(), half_h)
        down_rect = QRect(c.left(), c.top() + half_h, c.width(), c.height() - half_h)
        return up_rect, down_rect

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        val = index.data(Qt.ItemDataRole.EditRole)
        count = int(val) if val is not None else 0

        container = self._container_rect(option.rect)
        up_rect, down_rect = self._button_rects(option.rect)

        # 1. 숫자 그리기 (스텝퍼 왼쪽 영역에 깔끔하게 중앙 정렬)
        num_rect = QRect(
            option.rect.left(),
            option.rect.top(),
            max(10, container.left() - option.rect.left() - 2),
            option.rect.height(),
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        font = QFont(option.font)
        font.setBold(True)
        painter.setFont(font)
        if count == 0:
            painter.setPen(QColor(self._palette.text_subtle))
            display_text = "0"
        else:
            painter.setPen(QColor(self._palette.text))
            display_text = str(count)
        painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, display_text)

        # 2. 일체형 스텝퍼 컨테이너 그리기
        is_hovered = (index.row() == self._hover_row)
        is_up_hover = is_hovered and (self._hover_btn == 1)
        is_down_hover = is_hovered and (self._hover_btn == -1)

        border_col = QColor(self._palette.border_strong if is_hovered else self._palette.border)
        bg_col = QColor(self._palette.surface_hover if is_hovered else self._palette.surface_alt)
        painter.setPen(border_col)
        painter.setBrush(bg_col)
        painter.drawRoundedRect(container, 4, 4)

        # 호버 시 개별 버튼 은은한 하이라이트
        if is_up_hover or is_down_hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._palette.accent_strong))
            painter.drawRoundedRect(up_rect if is_up_hover else down_rect, 4, 4)

        # 중간 구분선 (블러 없이 선명하게 그리기)
        painter.fillRect(container.left() + 2, up_rect.bottom(), container.width() - 4, 1, border_col)

        # 3. 정밀 벡터 화살표 (폰트 깨짐 없는 깔끔한 렌더링)
        cx = container.center().x()
        cy_up = up_rect.center().y()
        cy_down = down_rect.center().y()

        arrow_up_col = QColor("#ffffff" if is_up_hover else self._palette.text_subtle)
        arrow_down_col = QColor("#ffffff" if is_down_hover else self._palette.text_subtle)

        # 상단 ▲ 화살표
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(arrow_up_col)
        painter.drawPolygon(QPolygonF([
            QPointF(cx - 3.5, cy_up + 1.5),
            QPointF(cx + 3.5, cy_up + 1.5),
            QPointF(cx, cy_up - 2.5),
        ]))

        # 하단 ▼ 화살표
        painter.setBrush(arrow_down_col)
        painter.drawPolygon(QPolygonF([
            QPointF(cx - 3.5, cy_down - 1.5),
            QPointF(cx + 3.5, cy_down - 1.5),
            QPointF(cx, cy_down + 2.5),
        ]))

        painter.restore()

    def editorEvent(  # noqa: N802
        self, event: QEvent, model, option: QStyleOptionViewItem, index: QModelIndex
    ) -> bool:
        up_rect, down_rect = self._button_rects(option.rect)

        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            if hasattr(event, "button") and event.button() != Qt.MouseButton.LeftButton:
                return False
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            val = index.data(Qt.ItemDataRole.EditRole)
            current = int(val) if val is not None else 0

            if up_rect.contains(pos):
                model.setData(index, current + 1, Qt.ItemDataRole.EditRole)
                return True
            if down_rect.contains(pos):
                if current > 0:  # 0 에서 ▼ 는 아무 일도 아니다. 빈 되돌리기 항목을 쌓지 않는다.
                    model.setData(index, current - 1, Qt.ItemDataRole.EditRole)
                return True
            # 숫자 영역: 값을 바꾸지 않는다. 클릭은 줄 선택, 더블클릭은 직접 입력.

        elif event.type() == QEvent.Type.MouseMove:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            btn = 1 if up_rect.contains(pos) else (-1 if down_rect.contains(pos) else 0)
            if (
                index.row() != self._hover_row
                or index.column() != self._hover_col
                or btn != self._hover_btn
            ):
                self._hover_row = index.row()
                self._hover_col = index.column()
                self._hover_btn = btn
                widget = option.widget
                if widget and hasattr(widget, "viewport"):
                    widget.viewport().update()

        return False

    def createEditor(  # noqa: N802
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        spin = QSpinBox(parent)
        spin.setRange(0, 99)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return spin

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QSpinBox):
            val = index.data(Qt.ItemDataRole.EditRole)
            spin_val = int(val) if val is not None else 0
            editor.setValue(spin_val)

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:  # noqa: N802
        if isinstance(editor, QSpinBox):
            model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)


TicketSpinDelegate = TicketStepperDelegate
TicketDropdownDelegate = TicketStepperDelegate


class CopyButtonDelegate(_PaletteAware, QStyledItemDelegate):
    """'복사' 버튼처럼 보이는 셀. 실제 위젯은 만들지 않는다.

    '✓ 복사완료' 는 **이번 실행에서 실제로 복사한 하객**에만 뜬다. 예전에는 발송 체크를
    보고 그렸다. 그래서 복사해도 그대로 '복사' 였고, 복사 없이 발송만 체크해도
    '복사완료' 로 떴다(옆 칸 발송 배지와 같은 값을 다른 말로 보여 준 셈).
    """

    clicked = Signal(QModelIndex)

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        QStyledItemDelegate.__init__(self, parent)
        _PaletteAware.__init__(self, palette)
        self._hover_row = -1
        # id(하객) → 그 하객을 가리키는 약한 참조.
        # id 만 들고 있으면 안 된다. 목록을 바꿔 옛 하객 객체가 해제되면 파이썬이 그 메모리
        # 주소(= id)를 새 하객에게 다시 준다. 그러면 복사한 적 없는 새 하객이 '✓ 복사완료' 로
        # 뜬다(실측: 명단 교체 5회 중 3회, 1~2명씩). 하객이 해제되면 그 표시도 함께 지운다.
        # Guest 는 eq 가 있는 dataclass 라 해시가 없어 WeakSet 을 쓸 수 없다.
        self._copied: dict[int, weakref.ref] = {}

    def mark_copied(self, guest: object) -> None:
        key = id(guest)
        self._copied[key] = weakref.ref(guest, lambda _ref, key=key: self._copied.pop(key, None))

    def is_copied(self, guest: object) -> bool:
        ref = self._copied.get(id(guest))
        return ref is not None and ref() is guest

    def set_hover_row(self, row: int) -> None:
        self._hover_row = row

    def _button_rect(self, option_rect: QRect) -> QRect:
        btn_h = 26
        btn_w = min(98, option_rect.width() - 8)
        x = option_rect.left() + (option_rect.width() - btn_w) // 2
        y = option_rect.top() + (option_rect.height() - btn_h) // 2
        return QRect(x, y, btn_w, btn_h)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        guest = index.data(GUEST_ROLE)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        copied = self.is_copied(guest)
        hovered = index.row() == self._hover_row and bool(option.state & QStyle.StateFlag.State_MouseOver)
        p = self._palette

        if copied:
            background = QColor(p.positive_surface)
            foreground = QColor(p.positive)
            border = QColor(p.positive if hovered else p.positive_border)
            label = "✓ 복사완료"
        else:
            background = QColor(p.accent_hover if hovered else p.accent_strong)
            foreground = QColor("#ffffff")
            border = QColor(p.accent if hovered else p.accent_strong)
            label = "📋 복사"

        rect = self._button_rect(option.rect)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(border)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 6, 6)

        font = QFont(option.font)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(foreground)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(110, 34)

    def editorEvent(  # noqa: N802
        self, event: QEvent, model, option: QStyleOptionViewItem, index: QModelIndex
    ) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease:
            if hasattr(event, "button") and event.button() != Qt.MouseButton.LeftButton:
                return False
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


class SentBadgeDelegate(_PaletteAware, QStyledItemDelegate):
    """'발송' 토글 뱃지 버튼.

    기존의 작은 체크박스 대신, 한눈에 식별 가능한
    선명한 [✓ 발송] / [미발송] 뱃지 버튼으로 표시하며 클릭 시 즉시 토글된다.
    """

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        QStyledItemDelegate.__init__(self, parent)
        _PaletteAware.__init__(self, palette)
        self._hover_row = -1

    def set_hover_row(self, row: int) -> None:
        self._hover_row = row

    def _button_rect(self, option_rect: QRect) -> QRect:
        btn_h = 26
        btn_w = min(72, option_rect.width() - 6)
        x = option_rect.left() + (option_rect.width() - btn_w) // 2
        y = option_rect.top() + (option_rect.height() - btn_h) // 2
        return QRect(x, y, btn_w, btn_h)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        guest = index.data(GUEST_ROLE)
        if guest is None:
            return

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        sent = bool(getattr(guest, "sent_thanks", False))
        hovered = index.row() == self._hover_row and bool(option.state & QStyle.StateFlag.State_MouseOver)
        rect = self._button_rect(option.rect)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        p = self._palette
        if sent:
            bg_color = QColor(p.positive_surface)
            border_color = QColor(p.positive if hovered else p.positive_border)
            text_color = QColor(p.positive)
            label = "✓ 발송"
        else:
            bg_color = QColor(p.surface_hover if hovered else p.surface_alt)
            border_color = QColor(p.border_strong if hovered else p.border)
            text_color = QColor(p.text if hovered else p.text_muted)
            label = "미발송"

        painter.setPen(border_color)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(rect, 6, 6)

        font = QFont(option.font)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def editorEvent(  # noqa: N802
        self, event: QEvent, model, option: QStyleOptionViewItem, index: QModelIndex
    ) -> bool:
        if event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonPress):
            if hasattr(event, "button") and event.button() != Qt.MouseButton.LeftButton:
                return False
            if event.type() == QEvent.Type.MouseButtonRelease:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if self._button_rect(option.rect).contains(pos):
                    current = bool(index.data(Qt.ItemDataRole.EditRole))
                    model.setData(index, not current, Qt.ItemDataRole.EditRole)
                    return True
        return False


def install_hover_tracking(view: QAbstractItemView, delegate, column: int) -> None:
    """마우스가 올라간 행을 델리게이트에 알려 호버 효과를 준다."""
    view.setMouseTracking(True)

    def _on_entered(index: QModelIndex) -> None:
        row = index.row() if index.column() == column else -1
        if hasattr(delegate, "set_hover_row") and (
            not hasattr(delegate, "_hover_row") or row != delegate._hover_row
        ):
            delegate.set_hover_row(row)
            view.viewport().update()

    view.entered.connect(_on_entered)
