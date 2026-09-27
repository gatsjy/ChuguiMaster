"""단계 안내 위젯: 안내 바 · 진행 막대 · 전체 단계 목록.

판정 로직은 :mod:`chugui.services.quests` 에 있고, 여기는 보여 주기만 한다.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from chugui.services.quests import QUESTS, Progress, Quest, QuestTracker
from chugui.ui.theme import Palette, Space

#: 단계 완료 문구가 안내 바에 머무는 시간.
_DONE_MESSAGE_MS = 2500


class PixelBar(QWidget):
    """단계 수만큼 칸으로 나뉜 진행 막대."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ratio = 0.0
        self._segments = len(QUESTS)
        self._fill = QColor("#5ee9ff")
        self._empty = QColor("#26215a")
        self.setFixedHeight(8)
        self.setMinimumWidth(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @property
    def ratio(self) -> float:
        return self._ratio

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self.update()

    def set_colors(self, fill: str, empty: str) -> None:
        self._fill, self._empty = QColor(fill), QColor(empty)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        gap = 3
        rect = self.rect()
        width = (rect.width() - gap * (self._segments - 1)) / self._segments
        lit = round(self._ratio * self._segments)
        for index in range(self._segments):
            x = rect.left() + round(index * (width + gap))
            cell = QRect(x, rect.top(), max(1, round(width)), rect.height())
            painter.fillRect(cell, self._fill if index < lit else self._empty)
        painter.end()


class QuestBar(QFrame):
    """지금 할 일 하나와 전체 진행."""

    logRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("questBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("다음 할 일")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.MD, Space.SM, Space.MD, Space.SM)
        layout.setSpacing(Space.MD)

        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        self._title = QLabel()
        self._title.setObjectName("questTitle")
        self._hint = QLabel()
        self._hint.setObjectName("questHint")
        # 긴 안내가 창의 최소 폭을 밀어내지 않게 한다(좁으면 잘려 보일 뿐).
        for label in (self._title, self._hint):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            text_box.addWidget(label)

        self._bar = PixelBar()
        self._bar.setAccessibleName("진행")
        self._bar.setMaximumWidth(220)

        self._btn_log = QPushButton("전체 단계")
        self._btn_log.setObjectName("ghost")
        self._btn_log.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_log.setToolTip("모든 단계와 진행 상황을 봅니다.")
        self._btn_log.setAccessibleName("전체 단계 보기")
        self._btn_log.clicked.connect(self.logRequested)

        layout.addLayout(text_box, 1)
        layout.addWidget(self._bar)
        layout.addWidget(self._btn_log)

        self._progress: Progress | None = None
        self._done_timer = QTimer(self)
        self._done_timer.setSingleShot(True)
        self._done_timer.timeout.connect(self._show_progress)

    @property
    def title_text(self) -> str:
        return self._title.text()

    @property
    def bar(self) -> PixelBar:
        return self._bar

    def apply_palette(self, palette: Palette) -> None:
        self._bar.set_colors(palette.accent, palette.surface_hover)

    def set_progress(self, progress: Progress) -> None:
        self._progress = progress
        self._bar.set_ratio(progress.ratio)
        self.setAccessibleDescription(f"{progress.total}단계 중 {progress.cleared}단계 완료")
        if not self._done_timer.isActive():
            self._show_progress()

    def announce_done(self, quests: tuple[Quest, ...]) -> None:
        """방금 마친 단계를 잠깐 알린다."""
        if not quests:
            return
        self._title.setText(f"✓ {quests[-1].title} 완료")
        progress = self._progress
        self._hint.setText(f"다음: {progress.current.title}" if progress and progress.current else "")
        self._done_timer.start(_DONE_MESSAGE_MS)

    def _show_progress(self) -> None:
        progress = self._progress
        if progress is None:
            return
        if progress.current is None:
            self._title.setText("모든 단계를 마쳤습니다")
            self._hint.setText("안내가 더 필요 없으면 [전체 단계]에서 언제든 다시 볼 수 있습니다.")
            return
        self._title.setText(
            f"다음 할 일  {progress.cleared + 1}/{progress.total} · {progress.current.title}"
        )
        self._hint.setText(progress.current.hint)


class QuestLogDialog(QDialog):
    """전체 단계 목록."""

    def __init__(self, tracker: QuestTracker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("전체 단계")
        self.setMinimumWidth(460)
        self.reset_requested = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XL, Space.LG, Space.XL, Space.LG)
        layout.setSpacing(Space.SM)

        progress = tracker.progress()
        header = QLabel(f"{progress.total}단계 중 {progress.cleared}단계 완료")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        bar = PixelBar()
        bar.set_ratio(progress.ratio)
        layout.addWidget(bar)
        layout.addSpacing(Space.SM)

        for index, quest in enumerate(QUESTS, start=1):
            done = tracker.is_cleared(quest.key)
            mark = "✓" if done else " "
            row = QLabel(f"{mark}  {index}. {quest.title}\n      {quest.hint}")
            row.setObjectName("questRowDone" if done else "questRow")
            layout.addWidget(row)

        buttons = QHBoxLayout()
        reset = QPushButton("안내 처음부터")
        reset.setObjectName("ghost")
        reset.setToolTip("단계 안내만 초기화합니다. 명단은 그대로입니다.")
        reset.setAccessibleName("단계 안내 초기화")
        reset.clicked.connect(self._on_reset)
        close = QPushButton("닫기")
        close.setObjectName("primary")
        close.setAccessibleName("닫기")
        close.clicked.connect(self.accept)
        buttons.addWidget(reset)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addSpacing(Space.SM)
        layout.addLayout(buttons)

    def _on_reset(self) -> None:
        self.reset_requested = True
        self.accept()
