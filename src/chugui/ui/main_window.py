"""메인 윈도우.

구버전 ``main_view.py`` 는 939줄 안에 UI 조립 · 비즈니스 로직 · 파일 영속화 ·
스타일 상수 · 샘플 데이터가 전부 들어 있는 God object였다.
이 클래스는 **조립과 사용자 상호작용만** 담당한다.
파싱은 :mod:`chugui.parsing`, 계산은 :mod:`chugui.services`,
저장은 :mod:`chugui.storage` 가 맡고 여기서는 그것들을 연결한다.

UI 원칙
    1. 숫자에는 항상 근거를 붙인다 — 카드 값 아래 캡션에 계산 근거를 적는다.
    2. 문제가 있으면 눈에 띄게 한다 — 확인 필요 배너 + 행 배경 강조.
    3. 빈 화면은 안내한다 — 빈 격자 대신 다음 할 일을 보여준다.
    4. 모든 상호작용 요소는 접근 이름과 툴팁을 갖는다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QKeySequence,
    QResizeEvent,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from chugui import __version__
from chugui.models import Relation, Source
from chugui.parsing.excel_parser import ExcelParseError, parse_spreadsheet
from chugui.parsing.text_parser import parse_text
from chugui.samples import SAMPLE_TEXT
from chugui.services.exporter import export_to_excel
from chugui.services.merge import merge_guests
from chugui.services.messages import MessageService
from chugui.services.settlement import Settlement, settle
from chugui.storage.crash import CrashSentinel
from chugui.storage.repositories import (
    AppConfig,
    ConfigRepository,
    SessionRepository,
    SessionState,
    TemplateRepository,
)
from chugui.storage.snapshots import SnapshotStore
from chugui.ui.delegates import (
    AttendanceDelegate,
    CopyButtonDelegate,
    RelationBadgeDelegate,
    TicketSpinDelegate,
    install_hover_tracking,
)
from chugui.ui.dialogs import HelpDialog, SnapshotRestoreDialog, TemplateSettingsDialog
from chugui.ui.guest_model import Column, GuestFilterProxy, GuestTableModel
from chugui.ui.theme import Size, Space, build_stylesheet, palette_for
from chugui.ui.widgets import DropTextEdit, EmptyState, MetricCard, ToastNotification

logger = logging.getLogger(__name__)

# 자동 저장 디바운스. 구버전은 키 입력 한 번마다 세션 JSON 전체를 디스크에 썼다.
_AUTOSAVE_DEBOUNCE_MS = 600
_CONFIG_DEBOUNCE_MS = 800

_ALL_RELATIONS = "전체 관계"

#: 주기적 스냅샷 간격. 사람 실수를 되돌릴 지점을 꾸준히 남긴다.
_SNAPSHOT_INTERVAL_MS = 5 * 60 * 1000
#: 되돌리기 토스트가 떠 있는 시간. 실수를 알아차릴 시간을 넉넉히 준다.
_UNDO_TOAST_MS = 9000
#: 입력 미리보기 디바운스. 타이핑 중 매 글자 파싱하지 않는다.
_PREVIEW_DEBOUNCE_MS = 300

_EMPTY_NO_DATA = (
    "아직 취합된 내역이 없습니다",
    "왼쪽 입력창에 축의금 명단을 붙여넣고 Ctrl+Enter 를 누르세요.\n"
    "은행 엑셀(.xlsx)이나 CSV 파일을 창에 끌어다 놓아도 됩니다.",
)
_EMPTY_NO_MATCH = (
    "조건에 맞는 하객이 없습니다",
    "검색어나 필터를 바꿔 보세요.",
)


class MainWindow(QMainWindow):
    """ChuguiMaster 메인 화면."""

    def __init__(
        self,
        config_repo: ConfigRepository | None = None,
        session_repo: SessionRepository | None = None,
        template_repo: TemplateRepository | None = None,
    ) -> None:
        super().__init__()

        self._config_repo = config_repo or ConfigRepository()
        self._session_repo = session_repo or SessionRepository()
        self._template_repo = template_repo or TemplateRepository()
        self._snapshots = SnapshotStore()
        self._sentinel = CrashSentinel()
        self._crash_report = self._sentinel.arm()
        #: 직전 파괴 연산 이전 상태. 토스트의 되돌리기 버튼이 이걸 되살린다.
        self._undo_payload: dict | None = None

        self._config: AppConfig = self._config_repo.load()
        self._messages = MessageService(self._template_repo.load())

        self._model = GuestTableModel(self._messages, self)
        self._proxy = GuestFilterProxy(self)
        self._proxy.setSourceModel(self._model)

        # 셀 편집은 Ctrl+Z 로 되돌린다. 목록이 통째로 바뀌면 모델이 스택을 비운다.
        self._undo_stack = QUndoStack(self)
        self._undo_stack.setUndoLimit(200)
        self._model.set_undo_stack(self._undo_stack)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(_AUTOSAVE_DEBOUNCE_MS)
        self._autosave_timer.timeout.connect(self._save_session)

        self._config_timer = QTimer(self)
        self._config_timer.setSingleShot(True)
        self._config_timer.setInterval(_CONFIG_DEBOUNCE_MS)
        self._config_timer.timeout.connect(self._save_config)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(_PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._update_preview)

        self._snapshot_timer = QTimer(self)
        self._snapshot_timer.setInterval(_SNAPSHOT_INTERVAL_MS)
        self._snapshot_timer.timeout.connect(lambda: self._capture_snapshot("자동"))
        self._snapshot_timer.start()

        self.setWindowTitle("ChuguiMaster — 축의금 정산 & 감사 메시지")
        self.setMinimumSize(Size.WINDOW_MIN_WIDTH, Size.WINDOW_MIN_HEIGHT)
        self.resize(
            max(Size.WINDOW_MIN_WIDTH, self._config.window_width),
            max(Size.WINDOW_MIN_HEIGHT, self._config.window_height),
        )

        self._build_ui()
        self._build_shortcuts()
        self._apply_theme()

        self._toast = ToastNotification(self)
        self._apply_toast_palette()

        self._model.guestsChanged.connect(self._on_guests_changed)
        self._proxy.rowsInserted.connect(self._update_empty_state)
        self._proxy.rowsRemoved.connect(self._update_empty_state)
        self._proxy.modelReset.connect(self._update_empty_state)
        self._proxy.layoutChanged.connect(self._update_empty_state)

        QTimer.singleShot(120, self._restore_session)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(Space.LG, Space.MD, Space.LG, Space.SM)
        root.setSpacing(Space.MD)

        root.addLayout(self._build_header())
        root.addLayout(self._build_kpi_row())
        root.addWidget(self._build_settings_strip())
        root.addWidget(self._build_review_banner())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_input_panel())
        splitter.addWidget(self._build_table_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        splitter.setSizes([420, 900])
        self._splitter = splitter
        root.addWidget(splitter, 1)

        self.statusBar().showMessage("텍스트를 붙여넣거나 엑셀 파일을 끌어다 놓으세요.")

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(Space.SM)

        title = QLabel("ChuguiMaster")
        title.setObjectName("appTitle")

        version = QLabel(f"v{__version__}")
        version.setObjectName("appVersion")

        self._btn_theme = QPushButton()
        self._btn_theme.setObjectName("ghost")
        self._btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_theme.setToolTip("밝은 화면과 어두운 화면을 전환합니다.")
        self._btn_theme.setAccessibleName("테마 전환")
        self._btn_theme.clicked.connect(self._toggle_theme)

        btn_templates = QPushButton("인사말 템플릿")
        btn_templates.setObjectName("ghost")
        btn_templates.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_templates.setToolTip("관계별·상황별 감사 인사말 문구를 직접 편집합니다.")
        btn_templates.setAccessibleName("인사말 템플릿 설정")
        btn_templates.clicked.connect(self._open_template_settings)

        btn_restore = QPushButton("이전 시점 복구")
        btn_restore.setObjectName("ghost")
        btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_restore.setToolTip("자동 저장된 시점 중 하나를 골라 되돌립니다.")
        btn_restore.setAccessibleName("이전 시점 복구")
        btn_restore.clicked.connect(self._open_restore_dialog)
        self._btn_restore = btn_restore

        btn_help = QPushButton("입력 가이드")
        btn_help.setObjectName("ghost")
        btn_help.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_help.setToolTip("어떤 형식으로 적으면 되는지 안내합니다.")
        btn_help.setAccessibleName("입력 가이드")
        btn_help.clicked.connect(self._open_help)

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addStretch()
        layout.addWidget(self._btn_theme)
        layout.addWidget(btn_restore)
        layout.addWidget(btn_templates)
        layout.addWidget(btn_help)
        return layout

    def _build_kpi_row(self) -> QHBoxLayout:
        """결과 지표 4장.

        v2 초안에서는 여기에 식대 입력까지 5칸을 밀어 넣었더니 카드가 179px로 좁아져
        큰 금액의 글자가 줄어들었다. 입력은 지표가 아니므로 아래 설정 줄로 분리했다.
        """
        layout = QHBoxLayout()
        layout.setSpacing(Space.MD)

        self._card_total = MetricCard("총 수령 축의금", "💳")
        self._card_total.setToolTip("입력된 모든 하객의 축의금 합계입니다.")

        self._card_guests = MetricCard("하객", "👥")
        self._card_guests.setToolTip("건수는 명단의 줄 수, 인원은 부부 등을 풀어 센 사람 수입니다.")

        self._card_meal = MetricCard("총 식대", "🍽️")
        self._card_meal.setToolTip("발급된 식권 수 × 단가입니다. 불참 하객은 제외됩니다.")

        self._card_net = MetricCard("최종 순 정산금", "💰", object_name="netCard")
        self._card_net.setToolTip("총 축의금에서 총 식대를 뺀 금액입니다.")

        layout.addWidget(self._card_total, 1)
        layout.addWidget(self._card_guests, 1)
        layout.addWidget(self._card_meal, 1)
        layout.addWidget(self._card_net, 1)
        return layout

    def _build_settings_strip(self) -> QFrame:
        """식대 단가 입력 줄. 값을 바꾸면 위 카드가 즉시 다시 계산된다."""
        strip = QFrame()
        strip.setObjectName("card")
        strip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        strip.setAccessibleName("식대 단가 설정")

        layout = QHBoxLayout(strip)
        layout.setContentsMargins(Space.MD, Space.SM, Space.MD, Space.SM)
        layout.setSpacing(Space.SM)

        title = QLabel("🍽️  식대 단가")
        title.setObjectName("cardTitle")

        formula = QLabel("총 식대 = 대인 식권 × 대인 단가 + 소인 식권 × 소인 단가")
        formula.setObjectName("hint")

        self._spin_adult = QSpinBox()
        # 상한을 현실적인 범위로 잡으면 스핀박스가 좁아져 좁은 화면에서 레이아웃이 편해진다.
        self._spin_adult.setRange(0, 300_000)
        self._spin_adult.setSingleStep(1_000)
        self._spin_adult.setGroupSeparatorShown(True)
        self._spin_adult.setPrefix("대인 ")
        self._spin_adult.setSuffix("원")
        self._spin_adult.setValue(self._config.adult_meal)
        self._spin_adult.setToolTip("성인 1인 식대")
        self._spin_adult.setAccessibleName("대인 식대 단가")
        self._spin_adult.valueChanged.connect(self._on_meal_cost_changed)
        self._spin_adult.editingFinished.connect(self._on_meal_cost_changed)

        self._spin_child = QSpinBox()
        self._spin_child.setRange(0, 300_000)
        self._spin_child.setSingleStep(1_000)
        self._spin_child.setGroupSeparatorShown(True)
        self._spin_child.setPrefix("소인 ")
        self._spin_child.setSuffix("원")
        self._spin_child.setValue(self._config.child_meal)
        self._spin_child.setToolTip("어린이 1인 식대")
        self._spin_child.setAccessibleName("소인 식대 단가")
        self._spin_child.valueChanged.connect(self._on_meal_cost_changed)
        self._spin_child.editingFinished.connect(self._on_meal_cost_changed)

        self._spin_adult.setMinimumWidth(170)
        self._spin_child.setMinimumWidth(170)

        layout.addWidget(title)
        layout.addWidget(self._spin_adult)
        layout.addWidget(self._spin_child)
        layout.addSpacing(Space.SM)
        layout.addWidget(formula)
        layout.addStretch()
        return strip

    def _build_review_banner(self) -> QFrame:
        """확인 필요 건이 있을 때만 나타나는 경고 배너.

        0건일 때도 회색 카드를 계속 띄우면 노이즈만 된다. 문제가 있을 때만 말한다.
        """
        banner = QFrame()
        banner.setObjectName("reviewBanner")
        banner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        banner.hide()

        layout = QHBoxLayout(banner)
        layout.setContentsMargins(Space.MD, Space.SM, Space.MD, Space.SM)
        layout.setSpacing(Space.SM)

        self._banner_label = QLabel()
        self._banner_label.setObjectName("reviewBannerText")

        self._banner_action = QPushButton("해당 항목만 보기")
        self._banner_action.setObjectName("bannerAction")
        self._banner_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self._banner_action.setToolTip("확인이 필요한 행만 표에 남깁니다.")
        self._banner_action.setAccessibleName("확인 필요 항목만 보기")
        self._banner_action.clicked.connect(lambda: self._chk_review.setChecked(True))

        layout.addWidget(QLabel("⚠️"))
        layout.addWidget(self._banner_label)
        layout.addStretch()
        layout.addWidget(self._banner_action)

        self._review_banner = banner
        return banner

    def _build_input_panel(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumWidth(316)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(Space.MD, Space.MD, Space.MD, Space.MD)
        layout.setSpacing(Space.SM)

        heading = QLabel("1. 명단 입력")
        heading.setObjectName("sectionTitle")

        hint_box = QFrame()
        hint_box.setObjectName("hintBox")
        hint_layout = QVBoxLayout(hint_box)
        hint_layout.setContentsMargins(Space.MD, Space.SM, Space.MD, Space.SM)
        hint_layout.setSpacing(1)
        for line in (
            "홍길동 10만원 친척      김가족,김친지 30만 이모",
            "최동료 10만 식권2 소인1      박지성 5만원 불참",
            "엑셀(.xlsx) · CSV 를 끌어다 놓으면 기존 목록에 합쳐집니다.",
        ):
            label = QLabel(line)
            label.setObjectName("hint")
            label.setTextFormat(Qt.TextFormat.PlainText)
            hint_layout.addWidget(label)

        self._input = DropTextEdit()
        self._input.setPlaceholderText(
            "카톡이나 메모장에 적어둔 축의금 내역을 그대로 붙여넣으세요.\n\n"
            "1 홍길동 200,000 친척모임\n"
            "2 최동료 100,000 A보건지소 식권2\n"
            "3 김가족,김친지 300,000 이모"
        )
        self._input.setToolTip("자유 형식으로 붙여넣으면 됩니다. 양식을 맞출 필요 없습니다.")
        self._input.setAccessibleName("축의금 명단 입력")
        self._input.textChanged.connect(self._on_input_changed)
        self._input.fileDropped.connect(self._load_file)

        # 파싱을 누르기 전에도 결과를 알려 준다.
        # 틀린 줄을 찾으려고 표까지 갔다 오는 왕복을 없앤다.
        self._preview = QLabel("")
        self._preview.setObjectName("preview")
        self._preview.setTextFormat(Qt.TextFormat.PlainText)
        self._preview.setAccessibleName("입력 미리보기")
        self._preview.setToolTip("입력한 내용을 실시간으로 미리 해석한 결과입니다.")
        self._preview.hide()

        btn_parse = QPushButton("자동 취합 및 파싱")
        btn_parse.setObjectName("primary")
        btn_parse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_parse.setToolTip("입력한 텍스트를 표로 변환합니다.  (Ctrl+Enter)")
        btn_parse.setAccessibleName("자동 취합 및 파싱")
        btn_parse.clicked.connect(self._handle_parse)

        self._btn_append = QPushButton("기존 목록에 추가")
        self._btn_append.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_append.setToolTip("기존 목록을 지우지 않고 입력한 줄만 이어붙입니다.  (Ctrl+Shift+Enter)")
        self._btn_append.setAccessibleName("기존 목록에 추가")
        self._btn_append.clicked.connect(self._handle_append)
        self._btn_append.setEnabled(False)

        btn_file = QPushButton("엑셀 · CSV 불러오기")
        btn_file.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_file.setToolTip("은행 거래내역 등을 기존 목록에 합칩니다.")
        btn_file.setAccessibleName("엑셀 또는 CSV 불러오기")
        btn_file.clicked.connect(self._handle_open_file)

        btn_sample = QPushButton("샘플 보기")
        btn_sample.setObjectName("ghost")
        btn_sample.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sample.setToolTip("가명 처리된 예시 27건을 불러옵니다.")
        btn_sample.setAccessibleName("샘플 데이터 불러오기")
        btn_sample.clicked.connect(self._handle_sample)

        btn_clear = QPushButton("전체 비우기")
        btn_clear.setObjectName("danger")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setToolTip("입력과 취합 결과를 모두 지웁니다.")
        btn_clear.setAccessibleName("전체 비우기")
        btn_clear.clicked.connect(self._handle_clear)

        bottom = QHBoxLayout()
        bottom.setSpacing(Space.SM)
        bottom.addWidget(btn_sample)
        bottom.addWidget(btn_clear)

        layout.addWidget(heading)
        layout.addWidget(hint_box)
        layout.addWidget(self._input, 1)
        layout.addWidget(self._preview)
        layout.addWidget(btn_parse)
        layout.addWidget(self._btn_append)
        layout.addWidget(btn_file)
        layout.addLayout(bottom)
        return card

    def _build_table_panel(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(Space.LG, Space.LG, Space.LG, Space.LG)
        layout.setSpacing(Space.SM)

        heading = QLabel("2. 확인 및 감사 인사")
        heading.setObjectName("sectionTitle")

        self._search = QLineEdit()
        self._search.setPlaceholderText("이름 · 소속 검색")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(180)
        self._search.setToolTip("이름, 소속, 비고, 원문에서 찾습니다.  (Ctrl+F)")
        self._search.setAccessibleName("하객 검색")
        self._search.textChanged.connect(self._proxy.set_query)

        self._relation_filter = QComboBox()
        self._relation_filter.addItem(_ALL_RELATIONS)
        self._relation_filter.addItems(Relation.values())
        self._relation_filter.setFixedWidth(118)
        self._relation_filter.setToolTip("특정 관계의 하객만 봅니다.")
        self._relation_filter.setAccessibleName("관계 필터")
        self._relation_filter.currentTextChanged.connect(self._on_relation_filter_changed)

        self._chk_review = QCheckBox("확인 필요")
        self._chk_review.setToolTip("파서가 확신하지 못한 행만 봅니다.")
        self._chk_review.setAccessibleName("확인 필요만 보기")
        self._chk_review.toggled.connect(self._proxy.set_review_only)

        self._chk_unsent = QCheckBox("미발송")
        self._chk_unsent.setToolTip("아직 감사 인사를 보내지 않은 하객만 봅니다.")
        self._chk_unsent.setAccessibleName("미발송만 보기")
        self._chk_unsent.toggled.connect(self._proxy.set_unsent_only)

        header = QHBoxLayout()
        header.setSpacing(Space.SM)
        header.addWidget(heading)
        header.addStretch()
        header.addWidget(self._chk_review)
        header.addWidget(self._chk_unsent)
        header.addWidget(self._search)
        header.addWidget(self._relation_filter)

        self._table = self._build_table()
        self._empty_state = EmptyState("📋", *_EMPTY_NO_DATA)

        self._table_stack = QStackedWidget()
        self._table_stack.addWidget(self._empty_state)
        self._table_stack.addWidget(self._table)

        btn_export = QPushButton("엑셀로 내보내기")
        btn_export.setObjectName("success")
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setToolTip("명단과 정산 요약을 xlsx 파일로 저장합니다.  (Ctrl+S)")
        btn_export.setAccessibleName("엑셀로 내보내기")
        btn_export.clicked.connect(self._handle_export)

        layout.addLayout(header)
        layout.addWidget(self._table_stack, 1)
        layout.addWidget(btn_export)
        return card

    def _build_table(self) -> QTableView:
        table = QTableView()
        table.setModel(self._proxy)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.setSortingEnabled(True)
        # setSortingEnabled(True)는 0번 열 **내림차순**을 기본으로 잡는다.
        # 그대로 두면 입력한 순서의 역순으로 보여 사용자가 자기 명단을 못 알아본다.
        table.sortByColumn(int(Column.NO), Qt.SortOrder.AscendingOrder)
        table.setWordWrap(False)
        table.setShowGrid(False)
        table.setCornerButtonEnabled(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(Size.ROW_HEIGHT)
        table.setEditTriggers(
            QTableView.EditTrigger.DoubleClicked | QTableView.EditTrigger.SelectedClicked
        )
        table.setAccessibleName("하객 목록")
        table.setToolTip("값을 더블클릭하면 직접 수정할 수 있습니다.")

        palette = palette_for(self._config.dark_mode)
        self._relation_delegate = RelationBadgeDelegate(palette, table)
        self._copy_delegate = CopyButtonDelegate(palette, table)
        self._copy_delegate.clicked.connect(self._on_copy_clicked)

        table.setItemDelegateForColumn(Column.RELATION, self._relation_delegate)
        table.setItemDelegateForColumn(Column.ATTENDANCE, AttendanceDelegate(table))
        table.setItemDelegateForColumn(Column.ADULT_TICKETS, TicketSpinDelegate(table))
        table.setItemDelegateForColumn(Column.CHILD_TICKETS, TicketSpinDelegate(table))
        table.setItemDelegateForColumn(Column.COPY, self._copy_delegate)
        install_hover_tracking(table, self._copy_delegate, int(Column.COPY))

        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        header.setSortIndicatorShown(True)
        fixed_widths: dict[Column, int] = {
            Column.NO: 48,
            Column.AMOUNT: 116,
            Column.RELATION: 118,
            Column.ATTENDANCE: 104,
            Column.ADULT_TICKETS: 54,
            Column.CHILD_TICKETS: 54,
            Column.COPY: 118,
            Column.SENT: 58,
        }
        for column in Column:
            if column in fixed_widths:
                header.setSectionResizeMode(int(column), QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(int(column), fixed_widths[column])
            elif column in (Column.NAME, Column.REVIEW):
                header.setSectionResizeMode(int(column), QHeaderView.ResizeMode.Interactive)
                table.setColumnWidth(int(column), 148 if column is Column.NAME else 176)
            else:
                header.setSectionResizeMode(int(column), QHeaderView.ResizeMode.Stretch)
        return table

    def _build_shortcuts(self) -> None:
        undo_action = self._undo_stack.createUndoAction(self, "실행 취소")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        redo_action = self._undo_stack.createRedoAction(self, "다시 실행")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        for action in (undo_action, redo_action):
            action.triggered.connect(self._announce_undo_state)
            self.addAction(action)

        for shortcut, slot, name in (
            (QKeySequence("Ctrl+Return"), self._handle_parse, "파싱"),
            (QKeySequence.StandardKey.Save, self._handle_export, "내보내기"),
            (QKeySequence("Ctrl+Shift+Return"), self._handle_append, "추가"),
            (QKeySequence.StandardKey.Find, lambda: self._search.setFocus(), "검색"),
        ):
            action = QAction(name, self)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            self.addAction(action)

    # -------------------------------------------------------------- 테마

    def _apply_theme(self) -> None:
        palette = palette_for(self._config.dark_mode)
        self.setStyleSheet(build_stylesheet(palette))
        self._btn_theme.setText("☀  라이트" if self._config.dark_mode else "🌙  다크")

        if hasattr(self, "_relation_delegate"):
            self._relation_delegate.set_palette(palette)
            self._copy_delegate.set_palette(palette)
            review_color = QColor(palette.warning_surface)
            review_color.setAlpha(150 if self._config.dark_mode else 210)
            self._model.set_review_color(review_color)
            self._table.viewport().update()
        if hasattr(self, "_toast"):
            self._apply_toast_palette()
        self._refresh_summary()

    def _apply_toast_palette(self) -> None:
        palette = palette_for(self._config.dark_mode)
        self._toast.apply_palette(palette.surface, palette.text, palette.border_strong, palette.accent)

    def _toggle_theme(self) -> None:
        self._config.dark_mode = not self._config.dark_mode
        self._apply_theme()
        self._schedule_config_save()

    # ------------------------------------------------------------ 데이터

    def _restore_session(self) -> None:
        state = self._session_repo.load()
        if state.raw_text and not self._input.toPlainText():
            self._input.blockSignals(True)
            self._input.setPlainText(state.raw_text)
            self._input.blockSignals(False)
        if state.guests:
            self._model.set_guests(state.guests)
            self._toast.show_message(f"이전 작업을 복구했습니다 · {len(state.guests)}건")
        self._refresh_summary()
        self._update_empty_state()
        self._report_previous_crash()

    def _handle_parse(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            self._toast.show_message("취합할 텍스트를 먼저 입력해 주세요.")
            self._input.setFocus()
            return

        guests = parse_text(text)
        if not guests:
            self._toast.show_message("인식할 수 있는 내용이 없습니다.")
            return

        replacing = bool(self._model.guests)
        if replacing and not self._confirm_replace(len(guests)):
            return

        if replacing:
            self._begin_destructive("파싱 덮어쓰기 전")

        self._model.set_guests(guests)
        review = sum(1 for guest in guests if guest.needs_review)
        message = f"{len(guests)}건 취합 완료"
        if review:
            message += f" · 확인 필요 {review}건"
        if replacing:
            self._offer_undo(message)
        else:
            self._toast.show_message(message)

    def _confirm_replace(self, incoming_count: int) -> bool:
        answer = QMessageBox.question(
            self,
            "기존 목록 처리",
            f"이미 {len(self._model.guests)}건이 있습니다.\n"
            f"새로 파싱한 {incoming_count}건으로 교체할까요?\n\n"
            "'아니오'를 누르면 아무 것도 바뀌지 않습니다. "
            "기존 목록에 이어붙이려면 엑셀·CSV 불러오기를 사용하세요.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _handle_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "엑셀 또는 CSV 파일 선택",
            "",
            "스프레드시트 (*.xlsx *.xlsm *.csv);;모든 파일 (*.*)",
        )
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str) -> None:
        """파일을 읽어 **기존 목록에 병합**한다.

        구버전은 여기서 목록을 통째로 덮어써서, 현금 명단을 취합한 뒤
        계좌이체 엑셀을 드롭하면 현금 내역이 전부 사라졌다.
        """
        path = Path(file_path)
        is_bank_file = any(k in path.stem for k in ("거래", "입출금", "이체", "내역"))
        source = Source.BANK if is_bank_file else Source.EXCEL

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            incoming = parse_spreadsheet(path, source=source)
        except ExcelParseError as exc:
            QMessageBox.warning(self, "파일을 읽을 수 없습니다", str(exc))
            return
        except Exception as exc:
            logger.exception("스프레드시트 로딩 실패: %s", path)
            QMessageBox.critical(self, "오류", f"파일을 읽는 중 오류가 발생했습니다:\n{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        if not incoming:
            self._toast.show_message("가져올 데이터가 없습니다.")
            return

        self._begin_destructive("파일 병합 전")
        result = merge_guests(self._model.guests, incoming, skip_exact_duplicates=False)
        self._model.set_guests(result.guests)

        self._offer_undo(f"{path.name} · {result.summary}")
        if result.duplicate_count:
            self._chk_review.setChecked(True)

    def _handle_sample(self) -> None:
        self._begin_destructive("샘플 불러오기 전")
        self._input.setPlainText(SAMPLE_TEXT)
        guests = parse_text(SAMPLE_TEXT)
        self._model.set_guests(guests)
        self._offer_undo(f"샘플 {len(guests)}건을 불러왔습니다.")

    def _handle_clear(self) -> None:
        if not self._model.guests and not self._input.toPlainText():
            return
        answer = QMessageBox.question(
            self,
            "전체 비우기",
            "입력 내용과 취합 결과를 모두 지울까요? 되돌릴 수 없습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        # 지우기 전에 되돌릴 지점을 남긴다. 세션 파일은 지워도 스냅샷은 남는다.
        self._begin_destructive("전체 비우기 전")
        self._input.clear()
        self._model.clear()
        self._session_repo.clear()
        self._offer_undo("모두 지웠습니다.")

    # ------------------------------------------------------------ 상호작용

    def _on_relation_filter_changed(self, text: str) -> None:
        self._proxy.set_relation(None if text == _ALL_RELATIONS else Relation.coerce(text))

    def _on_copy_clicked(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy.mapToSource(proxy_index)
        guest = self._model.guest_at(source_index.row())
        if guest is None:
            return
        message = self._model.message_for(source_index.row())
        QApplication.clipboard().setText(message)
        # 복사는 '보냄'이 아니다. 발송 여부는 사용자가 직접 체크한다.
        self._toast.show_message(f"{guest.name} 인사말 복사됨 · Ctrl+V 로 붙여넣어 발송하세요")

    def _on_meal_cost_changed(self) -> None:
        self._config.adult_meal = self._spin_adult.value()
        self._config.child_meal = self._spin_child.value()
        self._refresh_summary()
        self._schedule_config_save()

    def _on_guests_changed(self) -> None:
        self._refresh_summary()
        self._update_empty_state()
        if hasattr(self, "_btn_append"):
            # 붙일 대상이 있을 때만 '추가' 가 의미를 갖는다.
            self._btn_append.setEnabled(bool(self._model.guests))
        self._schedule_autosave()

    def _open_template_settings(self) -> None:
        dialog = TemplateSettingsDialog(self._messages, self)
        if dialog.exec() != int(TemplateSettingsDialog.DialogCode.Accepted):
            return
        templates = dialog.templates
        if templates is None:
            return
        self._messages.set_templates(templates)
        self._template_repo.save(self._messages.templates)
        self._model.refresh_messages()
        self._toast.show_message("인사말 템플릿을 저장했습니다.")

    def _open_help(self) -> None:
        HelpDialog(self).exec()

    # -------------------------------------------------------------- 요약

    def _current_settlement(self) -> Settlement:
        return settle(self._model.guests, self._config.adult_meal, self._config.child_meal)

    def _update_empty_state(self) -> None:
        """표와 빈 상태 안내를 전환한다."""
        if not hasattr(self, "_table_stack"):
            return
        if self._proxy.rowCount() > 0:
            self._table_stack.setCurrentWidget(self._table)
            return
        has_data = bool(self._model.guests)
        self._empty_state.set_text(*(_EMPTY_NO_MATCH if has_data else _EMPTY_NO_DATA))
        self._table_stack.setCurrentWidget(self._empty_state)

    def _refresh_summary(self) -> None:
        if not hasattr(self, "_card_total"):
            return
        palette = palette_for(self._config.dark_mode)
        result = self._current_settlement()

        self._card_total.set_value(f"{result.total_amount:,}원", palette.text)
        self._card_total.set_caption(
            f"현금 {result.cash_amount:,} · 이체 {result.transfer_amount:,}"
            if result.guest_count
            else "명단을 입력하면 계산됩니다"
        )

        self._card_guests.set_value(f"{result.guest_count}건", palette.text)
        self._card_guests.set_caption(
            f"{result.head_count}명 · 참석 {result.attendee_count} · 불참 {result.absentee_count}"
        )

        self._card_meal.set_value(f"{result.meal_cost:,}원", palette.text_muted)
        self._card_meal.set_caption(
            f"대인 {result.adult_tickets}장 · 소인 {result.child_tickets}장"
        )

        self._card_net.set_value(
            f"{result.net_amount:,}원",
            palette.positive if result.net_amount >= 0 else palette.danger,
        )
        self._card_net.set_caption("총 축의금 − 총 식대")

        self._update_review_banner(result)
        self._update_status_bar(result)

    def _update_review_banner(self, result: Settlement) -> None:
        if result.review_count:
            self._banner_label.setText(
                f"확인이 필요한 항목이 {result.review_count}건 있습니다. "
                "금액이나 이름을 자동으로 추측하지 않았습니다."
            )
            self._review_banner.show()
        else:
            self._review_banner.hide()

    def _update_status_bar(self, result: Settlement) -> None:
        if not result.guest_count:
            self.statusBar().showMessage("텍스트를 붙여넣거나 엑셀 파일을 끌어다 놓으세요.")
            return
        parts = [
            f"{result.guest_count}건",
            f"평균 {result.average_amount:,}원",
            f"감사 인사 {result.sent_count}/{result.guest_count}",
        ]
        if result.review_count:
            parts.append(f"확인 필요 {result.review_count}건")
        self.statusBar().showMessage("   ·   ".join(parts))

    def _open_restore_dialog(self) -> None:
        """저장된 시점 목록에서 하나를 골라 되돌린다."""
        infos = self._snapshots.list_snapshots()
        dialog = SnapshotRestoreDialog(infos, self)
        if dialog.exec() != int(SnapshotRestoreDialog.DialogCode.Accepted):
            return

        info = dialog.selected
        if info is None:
            return

        payload = self._snapshots.load(info.path)
        if payload is None:
            QMessageBox.warning(self, "복구 실패", "해당 시점을 읽을 수 없습니다.")
            return

        # 되돌아가기 전에 지금 상태도 시점으로 남긴다. 복구 자체를 취소할 수 있어야 한다.
        self._begin_destructive("복구 전")
        self._restore_payload(payload)
        self._offer_undo(f"{info.label} 시점으로 되돌렸습니다 · {info.guest_count}건")

    def _report_previous_crash(self) -> None:
        """지난 실행이 비정상 종료였으면 알리고, 작업이 살아 있음을 확인시킨다."""
        if not self._crash_report.crashed:
            return
        count = len(self._model.guests)
        detail = f"마지막 작업 {count}건을 복구했습니다." if count else "복구할 작업 내용은 없었습니다."
        self.statusBar().showMessage(f"{self._crash_report.message} {detail}", 12000)
        self._toast.show_action(
            f"비정상 종료가 감지되었습니다 · {detail}",
            "이전 시점 보기",
            self._open_restore_dialog,
            _UNDO_TOAST_MS,
        )

    def _announce_undo_state(self) -> None:
        """되돌리기 결과를 사용자에게 알린다. 조용히 값만 바뀌면 알아채기 어렵다."""
        self.statusBar().showMessage("편집을 되돌렸습니다.  (Ctrl+Y 로 다시 실행)", 4000)

    def _on_input_changed(self) -> None:
        self._schedule_autosave()
        self._preview_timer.start()

    def _update_preview(self) -> None:
        """입력창 아래에 해석 결과를 요약해 보여 준다."""
        text = self._input.toPlainText().strip()
        if not text:
            self._preview.hide()
            return

        guests = parse_text(text)
        if not guests:
            self._preview.setText("인식할 수 있는 줄이 없습니다.")
            self._preview.show()
            return

        total = sum(guest.amount for guest in guests)
        review = sum(1 for guest in guests if guest.needs_review)
        summary = f"미리보기 · {len(guests)}건 · {total:,}원"
        if review:
            summary += f" · 확인 필요 {review}건"
        self._preview.setText(summary)
        self._preview.show()

    def _handle_append(self) -> None:
        """기존 목록을 지우지 않고 입력한 줄만 이어붙인다.

        구버전과 v2 초안은 파싱이 곧 전체 교체였다. 명단을 나눠서 적는 사람은
        새 줄 몇 개를 넣으려고 전체를 다시 붙여넣어야 했다.
        """
        text = self._input.toPlainText().strip()
        if not text:
            self._toast.show_message("추가할 텍스트를 먼저 입력해 주세요.")
            self._input.setFocus()
            return

        incoming = parse_text(text)
        if not incoming:
            self._toast.show_message("인식할 수 있는 내용이 없습니다.")
            return

        self._begin_destructive("목록 추가 전")
        result = merge_guests(self._model.guests, incoming, skip_exact_duplicates=True)
        self._model.set_guests(result.guests)
        self._offer_undo(f"{result.summary} · 총 {len(result.guests)}건")
        if result.duplicate_count:
            self._chk_review.setChecked(True)

    # ------------------------------------------------- 스냅샷 · 되돌리기

    def _current_payload(self) -> dict:
        """지금 화면 상태를 직렬화한 dict."""
        return SessionState(
            guests=self._model.guests, raw_text=self._input.toPlainText()
        ).to_dict()

    def _capture_snapshot(self, reason: str) -> None:
        """되돌릴 수 있는 시점을 하나 남긴다. 목록이 비어 있으면 건너뛴다."""
        self._snapshots.capture(self._current_payload(), reason)

    def _begin_destructive(self, reason: str) -> None:
        """파괴 연산 직전에 부른다. 스냅샷과 즉시 되돌리기 대상을 함께 준비한다."""
        payload = self._current_payload()
        self._undo_payload = payload if payload.get("guests") else None
        self._snapshots.capture(payload, reason)

    def _offer_undo(self, message: str) -> None:
        """되돌리기 버튼이 달린 토스트. 되돌릴 것이 없으면 일반 토스트."""
        if self._undo_payload is None:
            self._toast.show_message(message)
            return
        self._toast.show_action(message, "되돌리기", self._undo_last, _UNDO_TOAST_MS)

    def _undo_last(self) -> None:
        payload = self._undo_payload
        if payload is None:
            return
        self._undo_payload = None
        self._restore_payload(payload)
        self._toast.show_message("되돌렸습니다.")

    def _restore_payload(self, payload: dict) -> None:
        """스냅샷/되돌리기 공용 복원 경로."""
        state = SessionState.from_dict(payload)
        self._input.blockSignals(True)
        self._input.setPlainText(state.raw_text)
        self._input.blockSignals(False)
        self._model.set_guests(state.guests)
        self._save_session()

    # ------------------------------------------------------------ 영속화

    def _schedule_autosave(self) -> None:
        self._autosave_timer.start()

    def _schedule_config_save(self) -> None:
        self._config_timer.start()

    def _save_session(self) -> None:
        state = SessionState(guests=self._model.guests, raw_text=self._input.toPlainText())
        if not self._session_repo.save(state):
            self.statusBar().showMessage("자동 저장에 실패했습니다. 로그를 확인해 주세요.", 8000)

    def _save_config(self) -> None:
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        self._config_repo.save(self._config)

    # -------------------------------------------------------------- 내보내기

    def _handle_export(self) -> None:
        if not self._model.guests:
            self._toast.show_message("내보낼 데이터가 없습니다.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", "축의금_취합결과.xlsx", "Excel 파일 (*.xlsx)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            export_to_excel(file_path, self._model.guests, self._current_settlement(), self._messages)
        except PermissionError:
            QMessageBox.warning(
                self,
                "저장할 수 없습니다",
                "같은 이름의 파일이 열려 있는 것 같습니다. 엑셀에서 파일을 닫고 다시 시도해 주세요.",
            )
            return
        except Exception as exc:
            logger.exception("엑셀 내보내기 실패")
            QMessageBox.critical(self, "오류", f"엑셀 저장에 실패했습니다:\n{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()

        self._toast.show_message("엑셀 저장 완료")
        self.statusBar().showMessage(f"저장됨: {file_path}", 8000)

    # ------------------------------------------------------------ 이벤트

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_toast"):
            self._toast.reposition()
        self._schedule_config_save()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        # 디바운스 타이머가 아직 돌고 있을 수 있으므로 즉시 저장한다.
        self._autosave_timer.stop()
        self._config_timer.stop()
        self._snapshot_timer.stop()
        self._preview_timer.stop()
        self._save_session()
        self._save_config()
        self._sentinel.disarm()
        logger.info("애플리케이션 종료")
        super().closeEvent(event)
