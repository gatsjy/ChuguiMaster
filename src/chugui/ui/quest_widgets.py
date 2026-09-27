"""게임 연출 위젯: 퀘스트 바 · 경험치 막대 · 시작 화면 · 퀘스트 로그.

판정 로직은 :mod:`chugui.services.quests` 에 있고, 여기는 보여 주기만 한다.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPaintEvent
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

from chugui.services.quests import MAX_XP, QUESTS, Progress, QuestTracker
from chugui.ui.theme import Palette, Space

#: 퀘스트 완료 문구가 퀘스트 바에 머무는 시간.
_CELEBRATE_MS = 2800
_BLINK_MS = 530


class PixelBar(QWidget):
    """칸으로 나뉜 게이지. 오래된 게임의 HP · EXP 막대."""

    SEGMENTS = 14

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ratio = 0.0
        self._fill = QColor("#ffd23f")
        self._empty = QColor("#26215a")
        self._edge = QColor("#05040f")
        self.setFixedHeight(14)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @property
    def ratio(self) -> float:
        return self._ratio

    def set_ratio(self, ratio: float) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self.update()

    def set_colors(self, fill: str, empty: str, edge: str) -> None:
        self._fill, self._empty, self._edge = QColor(fill), QColor(empty), QColor(edge)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._edge)
        gap = 2
        inner = self.rect().adjusted(gap, gap, -gap, -gap)
        width = (inner.width() - gap * (self.SEGMENTS - 1)) / self.SEGMENTS
        lit = round(self._ratio * self.SEGMENTS)
        for index in range(self.SEGMENTS):
            x = inner.left() + round(index * (width + gap))
            cell = QRect(x, inner.top(), max(1, round(width)), inner.height())
            painter.fillRect(cell, self._fill if index < lit else self._empty)
        painter.end()


class QuestBar(QFrame):
    """지금 할 일 하나 + 레벨 + 경험치."""

    logRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("questBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("현재 퀘스트")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.MD, Space.SM, Space.MD, Space.SM)
        layout.setSpacing(Space.MD)

        self._level = QLabel()
        self._level.setObjectName("questLevel")

        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        self._title = QLabel()
        self._title.setObjectName("questTitle")
        self._hint = QLabel()
        self._hint.setObjectName("questHint")
        # 긴 힌트가 창의 최소 폭을 밀어내지 않게 한다(좁으면 잘려 보일 뿐).
        for label in (self._title, self._hint):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            text_box.addWidget(label)

        xp_box = QVBoxLayout()
        xp_box.setSpacing(2)
        self._bar = PixelBar()
        self._bar.setAccessibleName("경험치")
        self._xp = QLabel()
        self._xp.setObjectName("questXp")
        self._xp.setAlignment(Qt.AlignmentFlag.AlignRight)
        xp_box.addWidget(self._bar)
        xp_box.addWidget(self._xp)

        self._btn_log = QPushButton("📜 퀘스트 로그")
        self._btn_log.setObjectName("ghost")
        self._btn_log.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_log.setToolTip("모든 퀘스트와 진행 상황을 봅니다.")
        self._btn_log.setAccessibleName("퀘스트 로그")
        self._btn_log.clicked.connect(self.logRequested)

        layout.addWidget(self._level)
        layout.addLayout(text_box, 1)
        layout.addLayout(xp_box)
        layout.addWidget(self._btn_log)

        self._progress: Progress | None = None
        self._celebrate_timer = QTimer(self)
        self._celebrate_timer.setSingleShot(True)
        self._celebrate_timer.timeout.connect(self._show_progress)

    @property
    def title_text(self) -> str:
        return self._title.text()

    @property
    def bar(self) -> PixelBar:
        return self._bar

    def apply_palette(self, palette: Palette) -> None:
        self._bar.set_colors(palette.quest, palette.surface_hover, palette.bevel)

    def set_progress(self, progress: Progress) -> None:
        self._progress = progress
        self._level.setText(f"LV.{progress.level}")
        self._level.setToolTip(progress.title)
        self._bar.set_ratio(progress.xp / MAX_XP if MAX_XP else 1.0)
        self._xp.setText(f"{progress.title} · {progress.xp} / {MAX_XP} XP")
        self.setAccessibleDescription(f"레벨 {progress.level} {progress.title}, 경험치 {progress.xp}")
        if not self._celebrate_timer.isActive():
            self._show_progress()

    def celebrate(self, headline: str, detail: str) -> None:
        """퀘스트를 깼을 때 잠깐 축하 문구를 띄운다."""
        self._title.setText(headline)
        self._hint.setText(detail)
        self._celebrate_timer.start(_CELEBRATE_MS)

    def _show_progress(self) -> None:
        progress = self._progress
        if progress is None:
            return
        if progress.current is None:
            self._title.setText("🏆 ALL CLEAR!  축의금 마스터 달성")
            self._hint.setText("모든 퀘스트를 깼습니다. 이제 명단 정리는 식은 죽 먹기!")
            return
        number = progress.cleared + 1
        self._title.setText(f"▶ QUEST {number}/{len(QUESTS)}  {progress.current.title}")
        self._hint.setText(progress.current.hint)


class StartScreen(QFrame):
    """첫 실행 시작 화면. 창 전체를 덮는다.

    모달 대화상자로 만들지 않은 이유: 모달은 ``exec()`` 에서 이벤트 루프를 붙잡아
    창을 띄우는 쪽 코드(테스트 포함)가 멈춘다. 오버레이는 창의 일부일 뿐이다.
    """

    practiceRequested = Signal()
    startRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("startScreen")
        self.setAutoFillBackground(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("시작 화면")

        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)

        panel = QFrame()
        panel.setObjectName("startPanel")
        panel.setMaximumWidth(620)
        body = QVBoxLayout(panel)
        body.setContentsMargins(Space.XL * 2, Space.XL, Space.XL * 2, Space.XL)
        body.setSpacing(Space.MD)

        logo = QLabel("CHUGUI MASTER")
        logo.setObjectName("startLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("축의금 정산 대모험 · 7개의 퀘스트를 깨면 당신도 마스터")
        subtitle.setObjectName("startSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        how = QLabel("─── HOW TO PLAY ───")
        how.setObjectName("startSubtitle")
        how.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body.addWidget(logo)
        body.addWidget(subtitle)
        body.addSpacing(Space.SM)
        body.addWidget(how)
        for step in (
            "① 카톡·메모장 명단을 그대로 붙여넣는다",
            "② ▶ 버튼 한 번이면 표가 되고 금액이 합산된다",
            "③ 노란 줄만 고치고, 감사 인사를 복사해 보낸다",
        ):
            label = QLabel(step)
            label.setObjectName("startStep")
            body.addWidget(label)
        body.addSpacing(Space.SM)

        self._blink = QLabel("PRESS START")
        self._blink.setObjectName("startBlink")
        self._blink.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self._blink)

        self._btn_practice = QPushButton("▶  샘플로 연습하기")
        self._btn_practice.setObjectName("primary")
        self._btn_practice.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_practice.setToolTip("가명 예시 명단으로 모든 기능을 안전하게 연습합니다.")
        self._btn_practice.setAccessibleName("샘플로 연습하기")
        self._btn_practice.clicked.connect(self.practiceRequested)

        self._btn_start = QPushButton("바로 시작  (Enter)")
        self._btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_start.setToolTip("빈 화면에서 내 명단으로 시작합니다.")
        self._btn_start.setAccessibleName("바로 시작")
        self._btn_start.clicked.connect(self.startRequested)

        body.addWidget(self._btn_practice)
        body.addWidget(self._btn_start)

        row.addWidget(panel, 3)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(_BLINK_MS)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_on = True

    def present(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.show()
        self.raise_()
        self.setFocus()
        self._blink_timer.start()

    def dismiss(self) -> None:
        self._blink_timer.stop()
        self.hide()

    def _toggle_blink(self) -> None:
        # 숨기면 레이아웃이 흔들리므로 글자색만 지웠다 켠다.
        self._blink_on = not self._blink_on
        self._blink.setText("PRESS START" if self._blink_on else " ")

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.startRequested.emit()
            return
        super().keyPressEvent(event)


class QuestLogDialog(QDialog):
    """전체 퀘스트 목록."""

    def __init__(self, tracker: QuestTracker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("퀘스트 로그")
        self.setMinimumWidth(460)
        self.reset_requested = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Space.XL, Space.LG, Space.XL, Space.LG)
        layout.setSpacing(Space.SM)

        progress = tracker.progress()
        header = QLabel(f"LV.{progress.level} {progress.title}  ·  {progress.xp} / {MAX_XP} XP")
        header.setObjectName("sectionTitle")
        layout.addWidget(header)

        bar = PixelBar()
        bar.set_ratio(progress.xp / MAX_XP if MAX_XP else 1.0)
        layout.addWidget(bar)
        layout.addSpacing(Space.SM)

        for index, quest in enumerate(QUESTS, start=1):
            done = tracker.is_cleared(quest.key)
            is_current = progress.current is not None and quest.key == progress.current.key
            mark = "✔" if done else ("▶" if is_current else "·")
            row = QLabel(f"{mark}  QUEST {index}. {quest.title}   +{quest.xp} XP\n      {quest.hint}")
            row.setObjectName("questRowDone" if done else "questRow")
            layout.addWidget(row)

        buttons = QHBoxLayout()
        reset = QPushButton("처음부터 다시")
        reset.setObjectName("ghost")
        reset.setToolTip("퀘스트 진행만 초기화합니다. 명단은 그대로입니다.")
        reset.setAccessibleName("퀘스트 초기화")
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
