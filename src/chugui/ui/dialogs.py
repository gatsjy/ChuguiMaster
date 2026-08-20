"""다이얼로그."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
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
        "기본 입력 양식",
        (
            "이름 금액 소속  →  홍길동 10만원 친척",
            "이름1,이름2 금액  →  김가족,김친지 30만 이모",
            "이름 금액 식권N 소인N  →  최동료 10만 식권2 소인1",
            "이름 금액 불참  →  박지성 5만원 불참",
        ),
    ),
    (
        "인식되는 금액 표기",
        (
            "100000 · 100,000 · 10만 · 10만원 · 10만 5천 · 3억 2천만",
            "단위 없는 1,000 미만 숫자는 금액으로 보지 않습니다 (5 → 5만원으로 추측하지 않음)",
            "줄 앞의 번호, 식권 수, 날짜, 전화번호, 계좌번호는 금액에서 자동 제외됩니다",
        ),
    ),
    (
        "확인 필요 표시",
        (
            "금액이나 이름을 확신하지 못하면 조용히 추측하지 않고 '확인 필요'로 표시합니다",
            "상단의 '확인 필요' 카드를 누르면 해당 행만 모아 볼 수 있습니다",
            "표의 값은 더블클릭으로 직접 수정할 수 있고, 수정 즉시 저장됩니다",
        ),
    ),
    (
        "현금 + 계좌이체 통합",
        (
            "텍스트를 취합한 뒤 은행 엑셀(.xlsx)이나 CSV를 끌어다 놓으면 기존 목록에 이어붙습니다",
            "같은 이름이 양쪽에 있으면 지우지 않고 '중복 의심'으로 표시합니다",
            "은행 엑셀 상단의 안내 문구 행은 자동으로 건너뜁니다",
        ),
    ),
    (
        "자동 저장",
        (
            "작업 내용은 사용자 데이터 폴더에 실시간 자동 저장됩니다",
            "저장은 임시 파일 교체 방식이라 저장 도중 종료돼도 파일이 깨지지 않습니다",
            "직전 정상본을 백업으로 보관해 파일 손상 시 자동 복구합니다",
        ),
    ),
)


class HelpDialog(QDialog):
    """입력 가이드.

    구버전은 이 내용을 하나의 거대한 HTML 문자열로 만들어 ``QLabel`` 에 넣었고,
    포맷 지정을 놓쳐 태그가 그대로 노출되는 버그를 두 번 수정했다.
    여기서는 데이터(위 튜플)와 표현을 분리해 그 계열의 버그가 생길 수 없게 한다.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("입력 가이드")
        self.resize(620, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(8)

        title = QLabel("축의금 텍스트 작성 가이드")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 8, 0)
        container_layout.setSpacing(12)

        for heading, lines in _GUIDE_SECTIONS:
            heading_label = QLabel(heading)
            heading_label.setObjectName("cardTitle")
            container_layout.addWidget(heading_label)
            for line in lines:
                item = QLabel(f"• {line}")
                item.setWordWrap(True)
                item.setTextFormat(Qt.TextFormat.PlainText)
                container_layout.addWidget(item)
        container_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = box.button(QDialogButtonBox.StandardButton.Close)
        close_button.setText("닫기")
        close_button.setObjectName("primary")
        box.rejected.connect(self.accept)
        box.accepted.connect(self.accept)
        layout.addWidget(box)


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
