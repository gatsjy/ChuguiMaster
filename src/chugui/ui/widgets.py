"""재사용 위젯."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chugui.parsing.excel_parser import SUPPORTED_SUFFIXES


class ToastNotification(QFrame):
    """화면 하단에 잠깐 떠오르는 알림.

    구버전 버그: ``fade_out()`` 안에서 ``self.anim.finished.connect(self.hide)`` 를
    호출할 때마다 연결이 **누적**됐고, 그 연결은 fade-**in** 애니메이션에도 걸렸다.
    그래서 두 번째 토스트부터는 나타나자마자 사라졌다.
    연결은 생성자에서 한 번만 하고, 방향은 플래그로 구분한다.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        self._label = QLabel("")
        self._label.setObjectName("toastText")
        layout.addWidget(self._label)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._fading_out = False
        self._animation = QPropertyAnimation(self._opacity, b"opacity", self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._on_animation_finished)  # 단 한 번만 연결

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_fade_out)

        self.hide()

    def apply_palette(self, background: str, foreground: str, border: str) -> None:
        self.setStyleSheet(
            f"QFrame#toast {{ background-color: {background}; border: 1px solid {border};"
            f" border-radius: 12px; }}"
            f" QLabel#toastText {{ color: {foreground}; font-size: 13px; font-weight: 700;"
            f" background: transparent; border: none; }}"
        )

    def show_message(self, message: str, duration_ms: int = 2400) -> None:
        self._label.setText(message)
        self.adjustSize()
        self.reposition()

        self._fading_out = False
        self.show()
        self.raise_()
        self._animation.stop()
        self._animation.setStartValue(self._opacity.opacity())
        self._animation.setEndValue(1.0)
        self._animation.start()
        self._timer.start(max(600, duration_ms))

    def reposition(self) -> None:
        """부모 크기가 바뀌어도 하단 중앙을 유지한다."""
        parent = self.parentWidget()
        if parent is None:
            return
        rect = parent.rect()
        x = max(0, (rect.width() - self.width()) // 2)
        y = max(0, rect.height() - self.height() - 44)
        self.move(QPoint(x, y))

    def _start_fade_out(self) -> None:
        self._fading_out = True
        self._animation.stop()
        self._animation.setStartValue(self._opacity.opacity())
        self._animation.setEndValue(0.0)
        self._animation.start()

    def _on_animation_finished(self) -> None:
        if self._fading_out:
            self.hide()
            self._fading_out = False


class MetricCard(QFrame):
    """KPI 카드 한 장."""

    def __init__(
        self,
        title: str,
        icon: str,
        value: str = "-",
        object_name: str = "card",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFixedHeight(78)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setSpacing(6)
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 15px; background: transparent; border: none;")
        self._title = QLabel(title)
        self._title.setObjectName("cardTitle")
        header.addWidget(icon_label)
        header.addWidget(self._title)
        header.addStretch()

        self._value = QLabel(value)
        self._value.setObjectName("cardValue")

        layout.addLayout(header)
        layout.addWidget(self._value)

    def set_value(self, text: str, color: str | None = None) -> None:
        self._value.setText(text)
        if color:
            self._value.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {color};"
                                      " background: transparent; border: none;")

    def set_subtitle(self, text: str) -> None:
        self._title.setText(text)


class DropTextEdit(QTextEdit):
    """엑셀/CSV 파일을 받아들이는 입력창."""

    fileDropped = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    @staticmethod
    def _spreadsheet_path(event) -> str | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            local = url.toLocalFile()
            if local and Path(local).suffix.lower() in SUPPORTED_SUFFIXES:
                return local
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self._spreadsheet_path(event):
            self.setObjectName("dropActive")
            self._refresh_style()
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self.setObjectName("")
        self._refresh_style()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        path = self._spreadsheet_path(event)
        self.setObjectName("")
        self._refresh_style()
        if path:
            event.acceptProposedAction()
            self.fileDropped.emit(path)
            return
        super().dropEvent(event)

    def _refresh_style(self) -> None:
        style = self.style()
        style.unpolish(self)
        style.polish(self)
