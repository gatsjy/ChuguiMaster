"""다이얼로그."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from chugui.models import Attendance, Relation
from chugui.services.messages import (
    SUPPORTED_PLACEHOLDERS,
    MessageService,
    Templates,
    default_templates,
    unknown_placeholders,
)


class TemplateSettingsDialog(QDialog):
    """관계 x 참석여부별 인사말 편집기."""

    def __init__(self, service: MessageService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("감사 인사말 템플릿 설정")
        self.resize(720, 600)
        self._service = service
        self._result_templates: Templates | None = None
        self._editors: dict[tuple[str, str], QTextEdit] = {}
        self._build()

    @property
    def templates(self) -> Templates | None:
        """저장을 누른 경우에만 값이 있다."""
        return self._result_templates

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("관계별 · 상황별 감사 인사말")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        placeholders = ", ".join(f"{{{name}}}" for name in SUPPORTED_PLACEHOLDERS)
        hint = QLabel(f"사용 가능한 자리표시자: {placeholders} — 하객 정보로 자동 치환됩니다.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        tabs = QTabWidget()
        current = self._service.templates
        for relation in Relation:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(14, 14, 14, 14)
            page_layout.setSpacing(6)

            for attendance in (Attendance.PRESENT, Attendance.ABSENT):
                label = QLabel(f"{attendance.value} 하객에게")
                label.setObjectName("cardTitle")
                editor = QTextEdit()
                editor.setPlainText(current.get(relation.value, {}).get(attendance.value, ""))
                editor.setMinimumHeight(110)
                page_layout.addWidget(label)
                page_layout.addWidget(editor)
                self._editors[(relation.value, attendance.value)] = editor

            tabs.addTab(page, relation.value)
        layout.addWidget(tabs)

        buttons = QHBoxLayout()
        reset_button = QPushButton("기본값 복원")
        reset_button.setObjectName("danger")
        reset_button.clicked.connect(self._reset)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = box.button(QDialogButtonBox.StandardButton.Save)
        save_button.setText("저장")
        save_button.setObjectName("primary")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        box.accepted.connect(self._save)
        box.rejected.connect(self.reject)

        buttons.addWidget(reset_button)
        buttons.addStretch()
        buttons.addWidget(box)
        layout.addLayout(buttons)

    def _reset(self) -> None:
        confirm = QMessageBox.question(
            self,
            "기본값 복원",
            "모든 인사말을 기본 문구로 되돌릴까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        defaults = default_templates()
        for (relation, attendance), editor in self._editors.items():
            editor.setPlainText(defaults[relation][attendance])

    def _save(self) -> None:
        templates: Templates = {}
        unknown: set[str] = set()

        for (relation, attendance), editor in self._editors.items():
            text = editor.toPlainText().strip()
            unknown.update(unknown_placeholders(text))
            templates.setdefault(relation, {})[attendance] = text

        if unknown:
            # 크래시 대신 안내한다. 알 수 없는 자리표시자는 원문 그대로 출력된다.
            names = ", ".join(f"{{{name}}}" for name in sorted(unknown))
            confirm = QMessageBox.question(
                self,
                "확인",
                f"알 수 없는 자리표시자가 있습니다: {names}\n"
                "이 부분은 치환되지 않고 문구에 그대로 표시됩니다. 계속 저장할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self._result_templates = templates
        self.accept()


_GUIDE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "🌟 가장 쉬운 3대 기본 공식 (이것만 쓰셔도 충분합니다)",
        (
            "👤 일반 참석:  '홍길동 10만원 친척'  →  [성명: 홍길동] "
            "[금액: 100,000원] [관계: 친척] (대인 식권 1장 자동 발급)",
            "🍽️ 식권 여러 장:  '최동료 10만 대2 소1'  (또는 "
            "'식권2 소인1', '어른2 아이1')  →  [대인 2장, 소인 1장]",
            "💌 불참(송금):  '박지성 5만원 불참'  →  [참석: 불참] [식권: 0장] (식대 차감 안 됨!)",
            "👥 가족/동반:  '김가족,김친지 30만 이모'  →  [인원: 2명] [대인 식권 2장 자동 발급]",
        ),
    ),
    (
        "🔢 대인 · 소인 식권 쉬운 조작법",
        (
            "• 입력할 때: '대1 소1', '대2 소1', '어른2 "
            "아이1', '식권3(소1)', '식권2', '애기1' 등 자연스럽게 적으세요.",
            "• 표에서 직접 조절: 표의 '대인' / '소인' 칸에 있는 "
            "[▲] [▼] 버튼을 누르면 1장씩 즉시 늘어나고 줄어듭니다.",
            "• 직접 입력: 숫자를 더블클릭하면 원하는 장수를 바로 입력할 수 있습니다. "
            "(숫자를 한 번 누르면 줄 선택만 되고 값은 바뀌지 않습니다.)",
            "• 우클릭 일괄 적용: 표에서 여러 행을 선택한 뒤 "
            "우클릭 → [식권 빠른 설정]으로 한 번에 변경 가능합니다.",
        ),
    ),
    (
        "📋 감사 메시지 1초 복사 & 발송 관리",
        (
            "• [📋 복사] 버튼: 누르면 관계별 맞춤 감사 문구가 클립보드에 복사되고 [✓ 복사완료]로 바뀝니다.",
            "• 카톡으로 전송: 카카오톡 채팅창에서 Ctrl+V (붙여넣기) 후 엔터를 누르면 전송 끝!",
            "• [✓ 발송] / [미발송] 버튼: 클릭하여 인사를 보낸 "
            "하객을 체크해 두면 나중에 중복 발송을 방지할 수 있습니다.",
        ),
    ),
    (
        "📁 엑셀 파일 마우스 드래그 & 드롭 (통합)",
        (
            "• 은행 거래내역 엑셀 파일(.xlsx)이나 CSV 파일을 프로그램 창 안으로 마우스로 끌어다 놓으세요.",
            "• 기존에 입력해 둔 현금 축의금 명단 뒤에 자동으로 안전하게 합쳐집니다.",
        ),
    ),
    (
        "💡 편리한 단축키 및 자동 저장",
        (
            "• Ctrl+Enter: 명단 자동 취합 및 파싱",
            "• Ctrl+Z / Ctrl+Y: 모든 편집 실수 되돌리기 / 다시 실행",
            "• F11 / Esc: 전체 화면 켜기 / 끄기",
            "• 모든 작업 내용은 실시간으로 자동 저장되므로 프로그램을 껐다 켜도 안전합니다.",
        ),
    ),
)


class HelpDialog(QDialog):
    """입력 가이드."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("입력 가이드")
        self.resize(680, 580)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        title = QLabel("축의금 마스터 1초 입력 가이드")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        banner = QFrame()
        banner.setObjectName("hintBox")
        banner_layout = QVBoxLayout(banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        banner_text = QLabel(
            "💡 양식에 얽매이지 않고 띄어쓰기만으로 편하게 "
            "적으시면 프로그램이 알아서 똑똑하게 분류합니다!"
        )
        banner_text.setObjectName("cardTitle")
        banner_text.setWordWrap(True)
        banner_layout.addWidget(banner_text)
        layout.addWidget(banner)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 4, 8, 4)
        container_layout.setSpacing(14)

        for heading, lines in _GUIDE_SECTIONS:
            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(6)

            heading_label = QLabel(heading)
            heading_label.setObjectName("cardTitle")
            card_layout.addWidget(heading_label)

            for line in lines:
                item = QLabel(line)
                item.setWordWrap(True)
                item.setTextFormat(Qt.TextFormat.PlainText)
                card_layout.addWidget(item)

            container_layout.addWidget(card)
        container_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        self._btn_copy_sample = QPushButton("📋 대표 예시 복사하기")
        self._btn_copy_sample.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_copy_sample.setToolTip("클릭하면 4가지 대표 예시 텍스트를 클립보드에 복사합니다.")
        self._btn_copy_sample.clicked.connect(self._copy_examples)
        bottom_layout.addWidget(self._btn_copy_sample)

        bottom_layout.addStretch()

        btn_close = QPushButton("닫기")
        btn_close.setObjectName("primary")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)

        layout.addLayout(bottom_layout)

    def _copy_examples(self) -> None:
        examples = (
            "홍길동 10만원 친척\n"
            "최동료 10만 대2 소1\n"
            "박지성 5만원 불참\n"
            "김가족,김친지 30만 이모"
        )
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(examples)
            self._btn_copy_sample.setText("✓ 예시가 복사되었습니다!")


class SnapshotRestoreDialog(QDialog):
    """저장된 시점 중 하나를 골라 되돌리는 창.

    ``Ctrl+Z`` 는 방금 한 편집을 되돌린다. 이 창은 그보다 큰 단위,
    즉 '비우기 전' / '덮어쓰기 전' 같은 **시점**으로 돌아가기 위한 것이다.
    되돌아가면 지금 상태를 잃으므로, 복원 직전에도 스냅샷을 한 장 남긴다.
    """

    def __init__(self, snapshots: list, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("이전 시점으로 되돌리기")
        self.resize(560, 460)
        self._snapshots = snapshots
        self._selected = None
        self._build()

    @property
    def selected(self):
        """사용자가 고른 스냅샷. 취소했으면 ``None``."""
        return self._selected

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("저장된 시점")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        hint = QLabel(
            "파괴적인 작업 직전과 5분마다 자동으로 저장된 시점입니다.\n"
            "되돌려도 지금 상태는 새 시점으로 남으므로 다시 앞으로 올 수 있습니다."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.setAccessibleName("저장된 시점 목록")
        self._list.setToolTip("되돌아갈 시점을 고르세요.")
        for info in self._snapshots:
            item = QListWidgetItem(f"{info.label}\n      {info.detail}")
            item.setData(Qt.ItemDataRole.UserRole, info)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(lambda _: self._accept_selection())
        layout.addWidget(self._list, 1)

        if not self._snapshots:
            empty = QLabel("아직 저장된 시점이 없습니다.")
            empty.setObjectName("emptyBody")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("이 시점으로 되돌리기")
        ok_button.setObjectName("primary")
        ok_button.setEnabled(bool(self._snapshots))
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        box.accepted.connect(self._accept_selection)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        if self._snapshots:
            self._list.setCurrentRow(0)

    def _accept_selection(self) -> None:
        item = self._list.currentItem()
        if item is None:
            self.reject()
            return
        self._selected = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


class TextExportDialog(QDialog):
    """명단과 정산을 글로 보여 주고 복사 · 저장하게 한다.

    파일로 저장하는 일은 호출자가 한다(대화상자는 파일 다이얼로그를 띄우지 않는다).
    그래야 테스트가 대화상자만 따로 검증할 수 있다.
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("텍스트로 내보내기")
        self.resize(640, 560)
        self._text = text
        self.save_requested = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        title = QLabel("텍스트로 내보내기")
        title.setObjectName("sectionTitle")
        hint = QLabel(
            "카톡이나 메모장에 그대로 붙여넣을 수 있습니다.\n"
            "이 글을 입력창에 다시 붙여넣으면 같은 명단으로 읽힙니다('#' 줄은 요약이라 건너뜁니다)."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.PlainText)

        self._preview = QPlainTextEdit(text)
        self._preview.setReadOnly(True)
        self._preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._preview.setAccessibleName("내보낼 텍스트 미리보기")
        self._preview.setToolTip("내보낼 내용입니다. 일부만 골라 복사할 수도 있습니다.")

        buttons = QHBoxLayout()
        copy = QPushButton("클립보드에 복사")
        copy.setObjectName("primary")
        copy.setCursor(Qt.CursorShape.PointingHandCursor)
        copy.setAccessibleName("클립보드에 복사")
        copy.setToolTip("전체 내용을 복사합니다. 카톡 창에서 Ctrl+V")
        copy.clicked.connect(self._copy)
        save = QPushButton("파일로 저장 (.txt)")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setAccessibleName("텍스트 파일로 저장")
        save.setToolTip("메모장에서 열 수 있는 .txt 파일로 저장합니다.")
        save.clicked.connect(self._request_save)
        close = QPushButton("닫기")
        close.setAccessibleName("닫기")
        close.clicked.connect(self.reject)
        buttons.addWidget(copy)
        buttons.addWidget(save)
        buttons.addStretch()
        buttons.addWidget(close)

        self._status = QLabel("")
        self._status.setObjectName("hint")

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self._preview, 1)
        layout.addWidget(self._status)
        layout.addLayout(buttons)

    @property
    def text(self) -> str:
        return self._text

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._text)
        self._status.setText("복사했습니다. 카톡이나 메모장에서 Ctrl+V 로 붙여넣으세요.")

    def _request_save(self) -> None:
        self.save_requested = True
        self.accept()
