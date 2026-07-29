"""메인 윈도우.

구버전 ``main_view.py`` 는 939줄 안에 UI 조립 · 비즈니스 로직 · 파일 영속화 ·
스타일 상수 · 샘플 데이터가 전부 들어 있는 God object였다.
이 클래스는 **조립과 사용자 상호작용만** 담당한다.
파싱은 :mod:`chugui.parsing`, 계산은 :mod:`chugui.services`,
저장은 :mod:`chugui.storage` 가 맡고 여기서는 그것들을 연결한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QResizeEvent
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
    QSpinBox,
    QSplitter,
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
from chugui.storage.repositories import (
    AppConfig,
    ConfigRepository,
    SessionRepository,
    SessionState,
    TemplateRepository,
)
from chugui.ui.delegates import (
    AttendanceDelegate,
    CopyButtonDelegate,
    RelationBadgeDelegate,
    TicketSpinDelegate,
    install_hover_tracking,
)
from chugui.ui.dialogs import HelpDialog, TemplateSettingsDialog
from chugui.ui.guest_model import Column, GuestFilterProxy, GuestTableModel
from chugui.ui.theme import build_stylesheet, palette_for
from chugui.ui.widgets import DropTextEdit, MetricCard, ToastNotification

logger = logging.getLogger(__name__)

# 자동 저장 디바운스. 구버전은 키 입력 한 번마다 세션 JSON 전체를 디스크에 썼다.
_AUTOSAVE_DEBOUNCE_MS = 600
_CONFIG_DEBOUNCE_MS = 800

_ALL_RELATIONS = "전체 관계"


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

        self._config: AppConfig = self._config_repo.load()
        self._messages = MessageService(self._template_repo.load())

        self._model = GuestTableModel(self._messages, self)
        self._proxy = GuestFilterProxy(self)
        self._proxy.setSourceModel(self._model)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(_AUTOSAVE_DEBOUNCE_MS)
        self._autosave_timer.timeout.connect(self._save_session)

        self._config_timer = QTimer(self)
        self._config_timer.setSingleShot(True)
        self._config_timer.setInterval(_CONFIG_DEBOUNCE_MS)
        self._config_timer.timeout.connect(self._save_config)

        self.setWindowTitle(f"ChuguiMaster {__version__} — 축의금 정산 & 감사 메시지")
        self.resize(self._config.window_width, self._config.window_height)

        self._build_ui()
        self._build_shortcuts()
        self._apply_theme()

        self._toast = ToastNotification(self)
        self._apply_toast_palette()

        self._model.guestsChanged.connect(self._on_guests_changed)
        self._model.dataChanged.connect(lambda *_: self._on_guests_changed())

        QTimer.singleShot(120, self._restore_session)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(12)

        root.addLayout(self._build_header())
        root.addLayout(self._build_kpi_row())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_input_panel())
        splitter.addWidget(self._build_table_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        splitter.setSizes([440, 900])
        root.addWidget(splitter, 1)

        self.statusBar().showMessage("텍스트를 붙여넣거나 엑셀 파일을 끌어다 놓으세요.")

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        title = QLabel("ChuguiMaster")
        title.setObjectName("appTitle")

        self._btn_theme = QPushButton()
        self._btn_theme.setObjectName("ghost")
        self._btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_theme.clicked.connect(self._toggle_theme)

        btn_templates = QPushButton("인사말 템플릿")
        btn_templates.setObjectName("ghost")
        btn_templates.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_templates.clicked.connect(self._open_template_settings)

        btn_help = QPushButton("입력 가이드")
        btn_help.setObjectName("ghost")
        btn_help.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_help.clicked.connect(self._open_help)

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self._btn_theme)
        layout.addWidget(btn_templates)
        layout.addWidget(btn_help)
        return layout

    def _build_kpi_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        self._card_total = MetricCard("총 수령 축의금", "💳")
        self._card_guests = MetricCard("하객 / 인원", "👥")
        self._card_meal = MetricCard("총 식대", "🍽️")
        self._card_net = MetricCard("최종 순 정산금", "💰", object_name="netCard")
        self._card_review = MetricCard("확인 필요", "⚠️", object_name="reviewCard")

        layout.addWidget(self._card_total, 1)
        layout.addWidget(self._card_guests, 1)
        layout.addWidget(self._build_meal_setting_card(), 1)
        layout.addWidget(self._card_meal, 1)
        layout.addWidget(self._card_net, 1)
        layout.addWidget(self._card_review, 1)
        return layout

    def _build_meal_setting_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedHeight(78)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        title = QLabel("🍽️ 식대 단가")
        title.setObjectName("cardTitle")

        inputs = QHBoxLayout()
        inputs.setSpacing(6)

        self._spin_adult = QSpinBox()
        self._spin_adult.setRange(0, 1_000_000)
        self._spin_adult.setSingleStep(1_000)
        self._spin_adult.setGroupSeparatorShown(True)
        self._spin_adult.setValue(self._config.adult_meal)
        self._spin_adult.setToolTip("대인 1인 식대")
        self._spin_adult.valueChanged.connect(self._on_meal_cost_changed)

        self._spin_child = QSpinBox()
        self._spin_child.setRange(0, 1_000_000)
        self._spin_child.setSingleStep(1_000)
        self._spin_child.setGroupSeparatorShown(True)
        self._spin_child.setValue(self._config.child_meal)
        self._spin_child.setToolTip("소인 1인 식대")
        self._spin_child.valueChanged.connect(self._on_meal_cost_changed)

        inputs.addWidget(QLabel("대인"))
        inputs.addWidget(self._spin_adult, 1)
        inputs.addWidget(QLabel("소인"))
        inputs.addWidget(self._spin_child, 1)

        layout.addWidget(title)
        layout.addLayout(inputs)
        return card

    def _build_input_panel(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        heading = QLabel("텍스트 입력 · 파일 드롭")
        heading.setObjectName("sectionTitle")
        header.addWidget(heading)
        header.addStretch()

        hint_box = QFrame()
        hint_box.setObjectName("hintBox")
        hint_layout = QVBoxLayout(hint_box)
        hint_layout.setContentsMargins(10, 8, 10, 8)
        hint_layout.setSpacing(2)
        for line in (
            "홍길동 10만원 친척   ·   김가족,김친지 30만 이모",
            "최동료 10만 식권2 소인1   ·   박지성 5만원 불참",
            "엑셀(.xlsx) / CSV 파일을 이 창에 끌어다 놓으면 기존 목록에 합쳐집니다.",
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
        self._input.textChanged.connect(self._schedule_autosave)
        self._input.fileDropped.connect(self._load_file)

        btn_parse = QPushButton("자동 취합 및 파싱  (Ctrl+Enter)")
        btn_parse.setObjectName("primary")
        btn_parse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_parse.clicked.connect(self._handle_parse)

        btn_file = QPushButton("엑셀 / CSV 불러오기")
        btn_file.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_file.clicked.connect(self._handle_open_file)

        btn_sample = QPushButton("샘플 데이터 불러오기")
        btn_sample.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_sample.clicked.connect(self._handle_sample)

        btn_clear = QPushButton("전체 비우기")
        btn_clear.setObjectName("danger")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._handle_clear)

        bottom = QHBoxLayout()
        bottom.addWidget(btn_sample)
        bottom.addWidget(btn_clear)

        layout.addLayout(header)
        layout.addWidget(hint_box)
        layout.addWidget(self._input, 1)
        layout.addWidget(btn_parse)
        layout.addWidget(btn_file)
        layout.addLayout(bottom)
        return card

    def _build_table_panel(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        heading = QLabel("취합 결과")
        heading.setObjectName("sectionTitle")

        self._search = QLineEdit()
        self._search.setPlaceholderText("이름 · 소속 검색")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(180)
        self._search.textChanged.connect(self._proxy.set_query)

        self._relation_filter = QComboBox()
        self._relation_filter.addItem(_ALL_RELATIONS)
        self._relation_filter.addItems(Relation.values())
        self._relation_filter.setFixedWidth(120)
        self._relation_filter.currentTextChanged.connect(self._on_relation_filter_changed)

        self._chk_review = QCheckBox("확인 필요만")
        self._chk_review.toggled.connect(self._proxy.set_review_only)

        self._chk_unsent = QCheckBox("미발송만")
        self._chk_unsent.toggled.connect(self._proxy.set_unsent_only)

        header.addWidget(heading)
        header.addStretch()
        header.addWidget(self._chk_review)
        header.addWidget(self._chk_unsent)
        header.addWidget(self._search)
        header.addWidget(self._relation_filter)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSortingEnabled(True)
        # setSortingEnabled(True)는 0번 열 **내림차순**을 기본으로 잡는다.
        # 그대로 두면 입력한 순서의 역순으로 보여 사용자가 자기 명단을 못 알아본다.
        self._table.sortByColumn(int(Column.NO), Qt.SortOrder.AscendingOrder)
        self._table.setWordWrap(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(38)
        self._table.setEditTriggers(
            QTableView.EditTrigger.DoubleClicked | QTableView.EditTrigger.SelectedClicked
        )

        self._relation_delegate = RelationBadgeDelegate(palette_for(self._config.dark_mode), self._table)
        self._copy_delegate = CopyButtonDelegate(palette_for(self._config.dark_mode), self._table)
        self._copy_delegate.clicked.connect(self._on_copy_clicked)

        self._table.setItemDelegateForColumn(Column.RELATION, self._relation_delegate)
        self._table.setItemDelegateForColumn(Column.ATTENDANCE, AttendanceDelegate(self._table))
        self._table.setItemDelegateForColumn(Column.ADULT_TICKETS, TicketSpinDelegate(self._table))
        self._table.setItemDelegateForColumn(Column.CHILD_TICKETS, TicketSpinDelegate(self._table))
        self._table.setItemDelegateForColumn(Column.COPY, self._copy_delegate)
        install_hover_tracking(self._table, self._copy_delegate, int(Column.COPY))

        self._configure_table_header()

        btn_export = QPushButton("엑셀로 내보내기  (Ctrl+S)")
        btn_export.setObjectName("success")
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.clicked.connect(self._handle_export)

        layout.addLayout(header)
        layout.addWidget(self._table, 1)
        layout.addWidget(btn_export)
        return card

    def _configure_table_header(self) -> None:
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        fixed_widths: dict[Column, int] = {
            Column.NO: 52,
            Column.AMOUNT: 110,
            Column.RELATION: 116,
            Column.ATTENDANCE: 104,
            Column.ADULT_TICKETS: 58,
            Column.CHILD_TICKETS: 58,
            Column.COPY: 118,
            Column.SENT: 62,
        }
        for column in Column:
            if column in fixed_widths:
                header.setSectionResizeMode(int(column), QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(int(column), fixed_widths[column])
            elif column in (Column.NAME, Column.REVIEW):
                header.setSectionResizeMode(int(column), QHeaderView.ResizeMode.Interactive)
                self._table.setColumnWidth(int(column), 150 if column is Column.NAME else 170)
            else:
                header.setSectionResizeMode(int(column), QHeaderView.ResizeMode.Stretch)

    def _build_shortcuts(self) -> None:
        parse_action = QAction(self)
        parse_action.setShortcut(QKeySequence("Ctrl+Return"))
        parse_action.triggered.connect(self._handle_parse)
        self.addAction(parse_action)

        export_action = QAction(self)
        export_action.setShortcut(QKeySequence.StandardKey.Save)
        export_action.triggered.connect(self._handle_export)
        self.addAction(export_action)

        find_action = QAction(self)
        find_action.setShortcut(QKeySequence.StandardKey.Find)
        find_action.triggered.connect(lambda: self._search.setFocus())
        self.addAction(find_action)

    # -------------------------------------------------------------- 테마

    def _apply_theme(self) -> None:
        palette = palette_for(self._config.dark_mode)
        self.setStyleSheet(build_stylesheet(palette))
        self._btn_theme.setText("라이트 모드" if self._config.dark_mode else "다크 모드")
        if hasattr(self, "_relation_delegate"):
            self._relation_delegate.set_palette(palette)
            self._copy_delegate.set_palette(palette)
            self._table.viewport().update()
        if hasattr(self, "_toast"):
            self._apply_toast_palette()
        self._refresh_summary()

    def _apply_toast_palette(self) -> None:
        palette = palette_for(self._config.dark_mode)
        self._toast.apply_palette(palette.surface, palette.text, palette.border)

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

    def _handle_parse(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            self._toast.show_message("취합할 텍스트를 먼저 입력해 주세요.")
            return

        guests = parse_text(text)
        if not guests:
            self._toast.show_message("인식할 수 있는 내용이 없습니다.")
            return

        if self._model.guests and not self._confirm_replace(len(guests)):
            return

        self._model.set_guests(guests)
        review = sum(1 for guest in guests if guest.needs_review)
        message = f"{len(guests)}건 취합 완료"
        if review:
            message += f" · 확인 필요 {review}건"
        self._toast.show_message(message)
        self.statusBar().showMessage(message)

    def _confirm_replace(self, incoming_count: int) -> bool:
        answer = QMessageBox.question(
            self,
            "기존 목록 처리",
            f"이미 {len(self._model.guests)}건이 있습니다.\n"
            f"새로 파싱한 {incoming_count}건으로 교체할까요?\n\n"
            "'아니오'를 누르면 아무 것도 바뀌지 않습니다. "
            "기존 목록에 이어붙이려면 엑셀/CSV 불러오기를 사용하세요.",
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

        result = merge_guests(self._model.guests, incoming, skip_exact_duplicates=False)
        self._model.set_guests(result.guests)

        message = f"{path.name} · {result.summary}"
        self._toast.show_message(message)
        self.statusBar().showMessage(message)
        if result.duplicate_count:
            self._chk_review.setChecked(True)

    def _handle_sample(self) -> None:
        self._input.setPlainText(SAMPLE_TEXT)
        guests = parse_text(SAMPLE_TEXT)
        self._model.set_guests(guests)
        self._toast.show_message(f"샘플 {len(guests)}건을 불러왔습니다.")

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
        self._input.clear()
        self._model.clear()
        self._session_repo.clear()
        self.statusBar().showMessage("모두 지웠습니다.")

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
        self._toast.show_message(f"{guest.name} 인사말 복사됨 · 붙여넣기(Ctrl+V) 후 발송하세요")
        self.statusBar().showMessage(message, 6000)

    def _on_meal_cost_changed(self) -> None:
        self._config.adult_meal = self._spin_adult.value()
        self._config.child_meal = self._spin_child.value()
        self._refresh_summary()
        self._schedule_config_save()

    def _on_guests_changed(self) -> None:
        self._refresh_summary()
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

    def _refresh_summary(self) -> None:
        if not hasattr(self, "_card_total"):
            return
        palette = palette_for(self._config.dark_mode)
        result = self._current_settlement()

        self._card_total.set_value(f"{result.total_amount:,} 원", palette.accent)
        self._card_guests.set_value(f"{result.guest_count} / {result.head_count} 명", palette.text)
        self._card_guests.set_subtitle(
            f"👥 하객 {result.guest_count}건 (참석 {result.attendee_count} · 불참 {result.absentee_count})"
        )
        self._card_meal.set_value(f"{result.meal_cost:,} 원", palette.text_muted)
        self._card_meal.set_subtitle(
            f"🍽️ 총 식대 (대인 {result.adult_tickets} · 소인 {result.child_tickets})"
        )
        self._card_net.set_value(
            f"{result.net_amount:,} 원",
            palette.positive if result.net_amount >= 0 else palette.danger,
        )
        self._card_review.set_value(
            f"{result.review_count} 건",
            palette.warning if result.review_count else palette.text_subtle,
        )
        self._card_review.set_subtitle(
            f"⚠️ 확인 필요 · 발송 {result.sent_count}/{result.guest_count}"
        )

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
        self._save_session()
        self._save_config()
        logger.info("애플리케이션 종료")
        super().closeEvent(event)
