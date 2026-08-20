"""재사용 위젯."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QFont, QFontMetrics, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chugui.parsing.excel_parser import SUPPORTED_SUFFIXES
from chugui.ui.theme import FontSize, Size, Space


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
        layout.setContentsMargins(Space.LG, Space.SM + 2, Space.LG, Space.SM + 2)
        layout.setSpacing(Space.MD)
        self._label = QLabel("")
        self._label.setObjectName("toastText")
        layout.addWidget(self._label)

        self._action = QPushButton("")
        self._action.setObjectName("toastAction")
        self._action.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action.clicked.connect(self._on_action_clicked)
        self._action.hide()
        layout.addWidget(self._action)

        self._action_callback: Callable[[], None] | None = None

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._fading_out = False
        self._animation = QPropertyAnimation(self._opacity, b"opacity", self)
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._on_animation_finished)  # 단 한 번만 연결

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_fade_out)

        self.hide()

    def apply_palette(self, background: str, foreground: str, border: str, accent: str = "") -> None:
        accent_color = accent or foreground
        self.setStyleSheet(
            f"QFrame#toast {{ background-color: {background}; border: 1px solid {border};"
            f" border-radius: 10px; }}"
            f" QLabel#toastText {{ color: {foreground}; font-size: 13px; font-weight: 700;"
            f" background: transparent; border: none; }}"
            f" QPushButton#toastAction {{ color: {accent_color}; background: transparent;"
            f" border: 1px solid {accent_color}; border-radius: 6px; padding: 4px 12px;"
            f" font-size: 12px; font-weight: 700; min-height: 22px; }}"
            f" QPushButton#toastAction:hover {{ color: {background};"
            f" background-color: {accent_color}; }}"
        )

    def show_message(self, message: str, duration_ms: int = 2600) -> None:
        """단순 알림. 클릭을 통과시켜 아래 위젯을 가리지 않는다."""
        self._action_callback = None
        self._action.hide()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._present(message, duration_ms)

    def show_action(
        self,
        message: str,
        action_text: str,
        callback: Callable[[], None],
        duration_ms: int = 9000,
    ) -> None:
        """되돌리기처럼 곧바로 취소할 수 있는 알림.

        파괴 연산 직후에만 쓴다. 사용자가 실수를 알아차릴 시간을 주는 것이 목적이라
        표시 시간이 일반 알림보다 길다.
        """
        self._action_callback = callback
        self._action.setText(action_text)
        self._action.setAccessibleName(action_text)
        self._action.show()
        # 버튼을 눌러야 하므로 이때만 마우스 이벤트를 받는다.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._present(message, duration_ms)

    def _on_action_clicked(self) -> None:
        callback = self._action_callback
        self._action_callback = None
        self._timer.stop()
        self._start_fade_out()
        if callback is not None:
            callback()

    def _present(self, message: str, duration_ms: int) -> None:
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
        """부모 크기가 바뀌어도 하단 중앙을 유지한다. 부모 밖으로 나가지 않는다."""
        parent = self.parentWidget()
        if parent is None:
            return
        rect = parent.rect()
        x = max(0, min(rect.width() - self.width(), (rect.width() - self.width()) // 2))
        y = max(0, rect.height() - self.height() - 48)
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
    """KPI 카드 한 장.

    제목 · 값 · 보조 설명 세 단으로 구성된다. 보조 설명은 값의 근거를 담아
    사용자가 숫자를 검산할 수 있게 한다(예: 총 식대 아래 '대인 30장 · 소인 1장').

    값의 글자 크기는 **카드 폭에 맞춰 자동으로 줄어든다**. 축의금 총액은
    자릿수 편차가 커서(50만 ~ 3억) 고정 크기로는 큰 금액이 잘린다.
    금액이 '...' 으로 잘리는 정산 화면은 신뢰를 잃는다.
    """

    #: 값 표시에 시도할 글자 크기(px). 큰 것부터 시도해 처음 들어맞는 것을 쓴다.
    VALUE_SIZES: tuple[int, ...] = (FontSize.DISPLAY, 20, 18, 16, FontSize.BODY)

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
        self.setFixedHeight(Size.CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.MD, Space.MD, Space.MD, Space.MD)
        layout.setSpacing(1)

        header = QHBoxLayout()
        header.setSpacing(Space.XS + 2)
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 13px; background: transparent; border: none;")
        self._title = QLabel(title)
        self._title.setObjectName("cardTitle")
        header.addWidget(icon_label)
        header.addWidget(self._title)
        header.addStretch()

        self._value = QLabel(value)
        self._value.setObjectName("cardValue")
        # 값이 길어져도 카드가 옆 카드를 밀어내지 않게 한다.
        # 폭에 맞추는 일은 _fit_value_font 가 책임진다.
        self._value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self._caption = QLabel("")
        self._caption.setObjectName("cardCaption")
        self._caption.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._caption.hide()
        self._caption_text = ""

        layout.addLayout(header)
        layout.addWidget(self._value)
        layout.addWidget(self._caption)
        layout.addStretch()

        self._value_color: str | None = None
        self.setAccessibleName(title)

    # ------------------------------------------------------------------ 값

    def set_value(self, text: str, color: str | None = None) -> None:
        self._value.setText(text)
        if color:
            self._value_color = color
        self._fit_value_font()
        self.setAccessibleDescription(f"{self._title.text()}: {text}")

    def set_caption(self, text: str) -> None:
        self._caption_text = text
        self._caption.setVisible(bool(text))
        self._caption.setToolTip(text)
        self._elide_caption()

    def _elide_caption(self) -> None:
        """보조 설명은 잘리더라도 '…' 로 끝나야 한다. 잘린 티가 나야 툴팁을 찾는다."""
        metrics = QFontMetrics(self._caption.font())
        self._caption.setText(
            metrics.elidedText(self._caption_text, Qt.TextElideMode.ElideRight, self.available_value_width)
        )

    @property
    def available_value_width(self) -> int:
        """값이 쓸 수 있는 가로 폭(좌우 여백 제외)."""
        return max(40, self.width() - Space.MD * 2 - 2)

    def _fit_value_font(self) -> None:
        """카드 폭에 들어가는 가장 큰 글자 크기를 고른다."""
        text = self._value.text()
        available = self.available_value_width

        chosen = self.VALUE_SIZES[-1]
        for size in self.VALUE_SIZES:
            probe = QFont(self._value.font())
            probe.setPixelSize(size)
            probe.setBold(True)
            if QFontMetrics(probe).horizontalAdvance(text) <= available:
                chosen = size
                break

        color = f" color: {self._value_color};" if self._value_color else ""
        # 선택자를 반드시 붙인다. 전역 스타일시트의 `QLabel#cardValue` 는 id 선택자라
        # 특이도가 높아서, 선택자 없는 선언만 쓰면 폰트 축소가 무시된다.
        self._value.setStyleSheet(
            f"QLabel#cardValue {{ font-size: {chosen}px; font-weight: 800;"
            f" letter-spacing: -0.5px;{color} background: transparent; border: none; }}"
        )
        self._value.ensurePolished()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_value_font()
        self._elide_caption()

    @property
    def value_label(self) -> QLabel:
        """UX 테스트에서 값 잘림 여부를 검사하기 위해 노출한다."""
        return self._value


class EmptyState(QWidget):
    """데이터가 없을 때 표 대신 보여주는 안내.

    빈 격자를 보여주는 대신 다음에 무엇을 하면 되는지 알려준다.
    """

    def __init__(
        self,
        icon: str,
        title: str,
        body: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XL, Space.XL, Space.XL, Space.XL)
        layout.setSpacing(Space.SM)
        layout.addStretch()

        self._icon = QLabel(icon)
        self._icon.setObjectName("emptyIcon")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title = QLabel(title)
        self._title.setObjectName("emptyTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._body = QLabel(body)
        self._body.setObjectName("emptyBody")
        self._body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.TextFormat.PlainText)

        layout.addWidget(self._icon)
        layout.addWidget(self._title)
        layout.addWidget(self._body)
        layout.addStretch()

        self.setAccessibleName(title)

    def set_text(self, title: str, body: str) -> None:
        self._title.setText(title)
        self._body.setText(body)
        self.setAccessibleName(title)

    @property
    def title_text(self) -> str:
        return self._title.text()


class DropTextEdit(QTextEdit):
    """엑셀/CSV 파일을 받아들이는 입력창."""

    fileDropped = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAcceptRichText(False)  # 카톡에서 복사하면 서식이 딸려온다

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
