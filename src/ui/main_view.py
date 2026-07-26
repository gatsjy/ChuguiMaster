import sys
import os
import json
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QFileDialog, QHeaderView, QMessageBox, QSpinBox, QFrame,
    QCheckBox, QSplitter, QGraphicsDropShadowEffect, QDialog, QTabWidget,
    QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QFont, QColor, QClipboard

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smart_parser import SmartParser
from message_generator import MessageGenerator

SAMPLE_RAW_TEXT = """1 홍길동 200000 친척모임
2 김철수 100000 친척모임
3 이영희 300000 친척모임
4 박지성 100000
5 최동료 100000 A보건지소
6 정지인 100000 B보건지소
7 한동네 100000 C보건지소
8 이삼촌 200000 A이모
9 김선배 500000 선배모임
10 박이모 1000000 B이모
11 김가족,김친지 300000 C이모
12 최성도 100000 OO교회
13 한친척 100000 친척
14 한고모 2000000 친척
15 한외삼촌 100000 친척
16 이과장 100000 OO시보건소
17 추대리 100000 지인모임
18 서주임 50000 OO시보건소
19 장팀장 50000 OO시보건소
20 이후배 300000 동문회
21 김동기 200000
22 최차장 100000 OO시보건소
23 한계장 100000 D보건지소
24 이직원 50000 OO시보건소
25 김성도(조성도) 50000 OO교회
26 진부부,신부부 100000
27 권집사 100000 OO교회"""

class ToastNotification(QFrame):
    """다크 테마 토스트 알림 컴포넌트"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("""
            QFrame {
                background-color: #334155;
                color: #f8fafc;
                border-radius: 20px;
                padding: 10px 22px;
                border: 1px solid #64748b;
            }
            QLabel {
                color: #f8fafc;
                font-family: 'Pretendard', 'Segoe UI', '맑은 고딕', sans-serif;
                font-size: 13px;
                font-weight: 700;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        self.lbl_text = QLabel("")
        layout.addWidget(self.lbl_text)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)

        self.hide()

    def show_message(self, message: str, duration_ms: int = 1800):
        self.lbl_text.setText(message)
        self.adjustSize()

        if self.parent():
            p_rect = self.parent().rect()
            x = (p_rect.width() - self.width()) // 2
            y = p_rect.height() - self.height() - 50
            self.move(QPoint(x, y))

        self.show()
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

        self.timer.start(duration_ms)

    def fade_out(self):
        self.anim.stop()
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.hide)
        self.anim.start()


class TemplateSettingsDialog(QDialog):
    """다크 스타일 감사 인사말 세팅 팝업"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 감사 인사말 템플릿 맞춤 세팅")
        self.resize(680, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                font-family: 'Pretendard', 'Segoe UI', '맑은 고딕', sans-serif;
            }
            QLabel {
                color: #f8fafc;
            }
            QTextEdit {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 8px;
                font-size: 13px;
                padding: 8px;
            }
        """)

        self.current_templates = json.loads(json.dumps(MessageGenerator.get_templates()))
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header_title = QLabel("⚙️ 관계별 & 참석 상황별 인사말 세팅")
        header_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #818cf8;")
        
        header_desc = QLabel("원하시는 문구로 자유롭게 수정하세요. `{name}`은 하객 이름으로 자동 치환됩니다.")
        header_desc.setStyleSheet("font-size: 12px; color: #94a3b8; margin-bottom: 8px;")

        layout.addWidget(header_title)
        layout.addWidget(header_desc)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #334155; border-radius: 8px; background: #0f172a; }
            QTabBar::tab { background: #1e293b; padding: 10px 18px; font-weight: 600; color: #94a3b8; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #334155; color: #818cf8; border-bottom: 2px solid #818cf8; }
        """)

        self.editors = {}

        for category in ['친척/가족', '직장/기관', '종교/모임', '학교/동창', '지인/기타']:
            cat_tab = QWidget()
            cat_layout = QVBoxLayout(cat_tab)
            cat_layout.setContentsMargins(14, 14, 14, 14)

            cat_layout.addWidget(QLabel(f"<b style='color:#cbd5e1;'>[{category}] 직접 참석시 인사말:</b>"))
            txt_attend = QTextEdit()
            txt_attend.setPlainText(self.current_templates.get(category, {}).get('참석', ''))
            cat_layout.addWidget(txt_attend)

            cat_layout.addSpacing(6)
            cat_layout.addWidget(QLabel(f"<b style='color:#cbd5e1;'>[{category}] 불참(송금)시 인사말:</b>"))
            txt_absent = QTextEdit()
            txt_absent.setPlainText(self.current_templates.get(category, {}).get('불참(송금)', ''))
            cat_layout.addWidget(txt_absent)

            self.editors[(category, '참석')] = txt_attend
            self.editors[(category, '불참(송금)')] = txt_absent

            self.tab_widget.addTab(cat_tab, category)

        layout.addWidget(self.tab_widget)

        btn_layout = QHBoxLayout()
        
        btn_reset = QPushButton("🔄 기본값 복원")
        btn_reset.setStyleSheet("background-color: #1e293b; color: #f87171; font-weight: bold; border-radius: 6px; padding: 10px 16px; border: 1px solid #7f1d1d;")
        btn_reset.clicked.connect(self.reset_defaults)

        btn_save = QPushButton("💾 템플릿 저장하기")
        btn_save.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1); color: white; font-weight: bold; border-radius: 6px; padding: 10px 18px;")
        btn_save.clicked.connect(self.save_settings)

        btn_cancel = QPushButton("취소")
        btn_cancel.setStyleSheet("background-color: #334155; color: #cbd5e1; border-radius: 6px; padding: 10px 16px;")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def reset_defaults(self):
        reply = QMessageBox.question(self, "확인", "모든 인사말을 초기 기본 템플릿으로 복원하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            MessageGenerator.reset_templates()
            self.accept()

    def save_settings(self):
        new_templates = {}
        for (category, status), editor in self.editors.items():
            if category not in new_templates:
                new_templates[category] = {}
            new_templates[category][status] = editor.toPlainText().strip()
        
        MessageGenerator.save_templates(new_templates)
        QMessageBox.information(self, "저장 완료", "감사 인사말 템플릿이 성공적으로 저장되었습니다!")
        self.accept()


class HelpDialog(QDialog):
    """다크 스타일 가이드 팝업"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("❓ 텍스트 입력 및 취합 가이드")
        self.resize(540, 460)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                font-family: 'Pretendard', 'Segoe UI', '맑은 고딕', sans-serif;
            }
            QLabel {
                color: #f8fafc;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        
        title = QLabel("💡 축의금 자유 텍스트 작성 팁")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #818cf8;")
        layout.addWidget(title)
        
        guide_txt = QLabel("""
ChuguiMaster는 카톡이나 메모장에 작성한 자유 서식 텍스트를 
규칙 기반 스마트 파서가 1초 만에 자동 분석합니다.

📌 <b>작성 지원 양식 예시:</b>
• <b>기본형</b>: <code style='color:#a5b4fc;'>이름 금액 소속</code> (예: 홍길동 10만원 친척)
• <b>부부/가족</b>: <code style='color:#a5b4fc;'>이름1,이름2 금액</code> (예: 김가족,김친지 300,000원 C이모)
• <b>식권 지정</b>: <code style='color:#a5b4fc;'>이름 금액 식권수</code> (예: 최동료 10만 식권2)
• <b>불참/송금</b>: <code style='color:#a5b4fc;'>이름 금액 불참</code> (예: 박지성 5만원 불참)

📌 <b>금액 파싱 형식:</b>
• <code style='color:#a5b4fc;'>10만원</code>, <code style='color:#a5b4fc;'>10만</code>, <code style='color:#a5b4fc;'>100,000</code>, <code style='color:#a5b4fc;'>100000</code> 모두 자동 지원됩니다.

📌 <b>인사말 세팅:</b>
• 상단 우측 <code style='color:#818cf8;'>⚙️ 감사 인사말 템플릿 세팅</code> 버튼을 통해 나만의 감사 문구를 자유롭게 수정할 수 있습니다.
        """)
        guide_txt.setStyleSheet("font-size: 13px; color: #cbd5e1; line-height: 1.6;")
        guide_txt.setWordWrap(True)
        layout.addWidget(guide_txt)
        
        btn_close = QPushButton("확인했습니다")
        btn_close.setStyleSheet("background-color: #6366f1; color: white; font-weight: bold; border-radius: 6px; padding: 10px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class MetricCard(QFrame):
    """다크 모드 대시보드 KPI 카드 컴포넌트"""
    def __init__(self, title: str, initial_value: str, icon_str: str, bg_color: str, text_color: str):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 12px;
                border: 1px solid #334155;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        top_layout = QHBoxLayout()
        self.lbl_icon = QLabel(icon_str)
        self.lbl_icon.setStyleSheet("font-size: 20px;")
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #94a3b8;")

        top_layout.addWidget(self.lbl_icon)
        top_layout.addWidget(self.lbl_title)
        top_layout.addStretch()

        self.lbl_val = QLabel(initial_value)
        self.lbl_val.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {text_color}; font-family: 'Pretendard', 'Segoe UI', '맑은 고딕';")

        layout.addLayout(top_layout)
        layout.addSpacing(4)
        layout.addWidget(self.lbl_val)

    def set_value(self, val_str: str):
        self.lbl_val.setText(val_str)


class ChuguiMasterUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("💍 ChuguiMaster Pro - 스마트 축의금 자동 취합 & 감사 메시지 생성기 (Dark Mode)")
        self.resize(1360, 900)
        self.guest_data = []

        # 🌟 프리미엄 다크 모드 (Sleek Dark Theme)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QLabel {
                font-family: 'Pretendard', 'Segoe UI', '맑은 고딕', sans-serif;
                color: #f8fafc;
            }
            QTextEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 12px;
                font-size: 13px;
                color: #f8fafc;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 2px solid #818cf8;
            }
            QSpinBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: 600;
                color: #f8fafc;
                min-height: 28px;
            }
            QPushButton {
                font-family: 'Pretendard', 'Segoe UI', '맑은 고딕', sans-serif;
                font-size: 13px;
                font-weight: 700;
                border-radius: 8px;
                padding: 10px 16px;
                min-height: 38px;
                border: none;
                color: #ffffff;
            }
            QPushButton#btnParse {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: #ffffff;
                font-size: 14px;
            }
            QPushButton#btnParse:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
            }
            QPushButton#btnSample {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #8b5cf6);
                color: #ffffff;
            }
            QPushButton#btnSample:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #7c3aed);
            }
            QPushButton#btnSettings {
                background-color: #1e293b;
                color: #a5b4fc;
                border: 1px solid #4338ca;
                padding: 6px 14px;
                font-size: 12px;
                min-height: 28px;
            }
            QPushButton#btnSettings:hover {
                background-color: #312e81;
                color: #ffffff;
            }
            QPushButton#btnHelp {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #475569;
                padding: 4px 10px;
                font-size: 12px;
                min-height: 26px;
            }
            QPushButton#btnHelp:hover {
                background-color: #334155;
            }
            QPushButton#btnExcelImport {
                background-color: #334155;
                color: #f8fafc;
                border: 1px solid #475569;
            }
            QPushButton#btnExcelImport:hover {
                background-color: #475569;
            }
            QPushButton#btnExport {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                font-size: 15px;
            }
            QPushButton#btnExport:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
            }
            QPushButton#btnCopy {
                background-color: #064e3b;
                color: #6ee7b7;
                border: 1px solid #047857;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 700;
                min-height: 24px;
            }
            QPushButton#btnCopy:hover {
                background-color: #10b981;
                color: #ffffff;
                border: none;
            }
            QTableWidget {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 10px;
                gridline-color: #1e293b;
                selection-background-color: #312e81;
                selection-color: #ffffff;
                font-size: 13px;
                color: #f8fafc;
            }
            QHeaderView::section {
                background-color: #1e293b;
                font-weight: 700;
                color: #cbd5e1;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #334155;
            }
            QCheckBox {
                color: #cbd5e1;
            }
        """)

        self.init_ui()
        self.toast = ToastNotification(self)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. 상단 KPI 대시보드 다크 카드
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(14)

        self.card_total = MetricCard("총 수령 축의금", "0 원", "💳", "#1e293b", "#818cf8")
        self.card_guests = MetricCard("총 하객 수", "0 명", "👥", "#1e293b", "#38bdf8")
        
        # 다크 식대 설정 카드
        meal_card = QFrame()
        meal_card.setStyleSheet("background-color: #1e293b; border-radius: 12px; border: 1px solid #334155;")

        meal_layout = QVBoxLayout(meal_card)
        meal_layout.setContentsMargins(16, 12, 16, 12)
        
        meal_title_layout = QHBoxLayout()
        lbl_meal_icon = QLabel("🍽️")
        lbl_meal_icon.setStyleSheet("font-size: 18px;")
        lbl_meal_title = QLabel("식대 단가 설정 (대인 / 소인)")
        lbl_meal_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #94a3b8;")
        meal_title_layout.addWidget(lbl_meal_icon)
        meal_title_layout.addWidget(lbl_meal_title)
        meal_title_layout.addStretch()

        inputs_layout = QHBoxLayout()
        lbl_ad = QLabel("대인:")
        lbl_ad.setStyleSheet("color: #cbd5e1;")
        inputs_layout.addWidget(lbl_ad)
        
        self.spin_adult = QSpinBox()
        self.spin_adult.setRange(0, 500000)
        self.spin_adult.setValue(42000)
        self.spin_adult.setSingleStep(1000)
        self.spin_adult.setSuffix("원")
        self.spin_adult.valueChanged.connect(self.update_summary)
        inputs_layout.addWidget(self.spin_adult)

        lbl_ch = QLabel("소인:")
        lbl_ch.setStyleSheet("color: #cbd5e1;")
        inputs_layout.addWidget(lbl_ch)
        
        self.spin_child = QSpinBox()
        self.spin_child.setRange(0, 500000)
        self.spin_child.setValue(25000)
        self.spin_child.setSingleStep(1000)
        self.spin_child.setSuffix("원")
        self.spin_child.valueChanged.connect(self.update_summary)
        inputs_layout.addWidget(self.spin_child)

        meal_layout.addLayout(meal_title_layout)
        meal_layout.addSpacing(2)
        meal_layout.addLayout(inputs_layout)

        self.card_net = MetricCard("최종 순 정산금 (수익)", "0 원", "💰", "#064e3b", "#34d399")

        kpi_layout.addWidget(self.card_total, 1)
        kpi_layout.addWidget(self.card_guests, 1)
        kpi_layout.addWidget(meal_card, 1)
        kpi_layout.addWidget(self.card_net, 1)

        main_layout.addLayout(kpi_layout)

        # 2. 메인 스플리터
        splitter = QSplitter(Qt.Horizontal)

        # 좌측 패널
        left_card = QFrame()
        left_card.setStyleSheet("background-color: #1e293b; border-radius: 12px; border: 1px solid #334155;")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(18, 18, 18, 18)

        left_header_layout = QHBoxLayout()
        lbl_input_header = QLabel("📋 텍스트 입력 및 취합 테스트")
        lbl_input_header.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        
        btn_help = QPushButton("❓ 작성 가이드")
        btn_help.setObjectName("btnHelp")
        btn_help.setCursor(Qt.PointingHandCursor)
        btn_help.clicked.connect(self.show_help)

        left_header_layout.addWidget(lbl_input_header)
        left_header_layout.addStretch()
        left_header_layout.addWidget(btn_help)

        guide_box = QFrame()
        guide_box.setStyleSheet("background-color: #0f172a; border-radius: 8px; border: 1px dashed #475569;")
        gb_layout = QVBoxLayout(guide_box)
        gb_layout.setContentsMargins(12, 10, 12, 10)
        
        lbl_guide = QLabel("<b style='color:#818cf8;'>[입력 지원 팁]</b> 카톡/메모장의 자유 텍스트를 그대로 복붙하세요.<br>• <code style='color:#cbd5e1;'>홍길동 10만원 친척</code> | <code style='color:#cbd5e1;'>김가족,김친지 30만 C이모</code><br>• 아래 🎯 버튼을 누르시면 <b>27건의 가명화 데이터</b>로 체험 가능합니다.")
        lbl_guide.setStyleSheet("font-size: 12px; color: #94a3b8; line-height: 1.4;")
        gb_layout.addWidget(lbl_guide)

        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("여기에 축의금 리스트를 자유롭게 붙여넣으세요...\n\n입력 예시:\n홍길동 200,000 친척모임\n최동료 100,000 A보건지소 식권2\n김가족,김친지 300,000 C이모\n김성도(조성도) 50,000 OO교회 불참")

        btn_parse = QPushButton("⚡ 1초 자동 취합 및 파싱 실행")
        btn_parse.setObjectName("btnParse")
        btn_parse.setCursor(Qt.PointingHandCursor)
        btn_parse.clicked.connect(self.handle_parse_text)

        btn_sample = QPushButton("🎯 100% 가명화된 27건 샘플 데이터 불러오기")
        btn_sample.setObjectName("btnSample")
        btn_sample.setCursor(Qt.PointingHandCursor)
        btn_sample.clicked.connect(self.handle_load_sample)

        btn_excel_import = QPushButton("📂 엑셀 파일(.xlsx) 불러오기")
        btn_excel_import.setObjectName("btnExcelImport")
        btn_excel_import.setCursor(Qt.PointingHandCursor)
        btn_excel_import.clicked.connect(self.handle_excel_import)

        left_layout.addLayout(left_header_layout)
        left_layout.addWidget(guide_box)
        left_layout.addSpacing(4)
        left_layout.addWidget(self.txt_input)
        left_layout.addSpacing(6)
        left_layout.addWidget(btn_parse)
        left_layout.addWidget(btn_sample)
        left_layout.addWidget(btn_excel_import)

        splitter.addWidget(left_card)

        # 우측 데이터 표 패널
        right_card = QFrame()
        right_card.setStyleSheet("background-color: #1e293b; border-radius: 12px; border: 1px solid #334155;")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(18, 18, 18, 18)

        right_header_layout = QHBoxLayout()
        lbl_table_header = QLabel("📜 스마트 취합 결과 & 1초 감사 인사 복사")
        lbl_table_header.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")

        btn_settings = QPushButton("⚙️ 감사 인사말 템플릿 세팅")
        btn_settings.setObjectName("btnSettings")
        btn_settings.setCursor(Qt.PointingHandCursor)
        btn_settings.clicked.connect(self.show_template_settings)

        right_header_layout.addWidget(lbl_table_header)
        right_header_layout.addStretch()
        right_header_layout.addWidget(btn_settings)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "NO", "성명(하객)", "축의금액", "소속/관계", "참석/비고", "1초 감사 메시지 복사", "발송상태", "원문"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)

        btn_export = QPushButton("📥 완성된 취합 결과 엑셀 파일로 저장 (xlsx)")
        btn_export.setObjectName("btnExport")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self.handle_export_excel)

        right_layout.addLayout(right_header_layout)
        right_layout.addSpacing(4)
        right_layout.addWidget(self.table)
        right_layout.addSpacing(6)
        right_layout.addWidget(btn_export)

        splitter.addWidget(right_card)

        splitter.setSizes([450, 850])
        main_layout.addWidget(splitter)

    def show_template_settings(self):
        dialog = TemplateSettingsDialog(self)
        if dialog.exec():
            self.render_table()

    def show_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def handle_load_sample(self):
        self.txt_input.setPlainText(SAMPLE_RAW_TEXT)
        self.handle_parse_text()
        self.toast.show_message("✨ 27건의 샘플 축의금 데이터 취합이 완료되었습니다!")

    def handle_parse_text(self):
        text = self.txt_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "경고", "취합할 텍스트를 입력해주세요.")
            return

        self.guest_data = SmartParser.parse_text_lines(text)
        self.render_table()
        self.update_summary()

    def handle_excel_import(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "엑셀 파일 선택", "", "Excel Files (*.xlsx *.xls *.csv)")
        if file_path:
            try:
                self.guest_data = SmartParser.parse_excel(file_path)
                self.render_table()
                self.update_summary()
                self.toast.show_message(f"📂 {len(self.guest_data)}건의 데이터를 성공적으로 가져왔습니다!")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"엑셀 읽기 실패: {str(e)}")

    def render_table(self):
        self.table.setRowCount(0)
        for idx, guest in enumerate(self.guest_data):
            row = self.table.rowCount()
            self.table.insertRow(row)

            item_id = QTableWidgetItem(str(guest['id']))
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_id)

            item_name = QTableWidgetItem(guest['name'])
            item_name.setFont(QFont("Pretendard", 10, QFont.Bold))
            item_name.setForeground(QColor("#f8fafc"))
            self.table.setItem(row, 1, item_name)

            amt_str = f"{guest['amount']:,} 원"
            item_amt = QTableWidgetItem(amt_str)
            item_amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_amt.setForeground(QColor("#818cf8"))
            item_amt.setFont(QFont("Pretendard", 10, QFont.Bold))
            self.table.setItem(row, 2, item_amt)

            belong_rel = f"{guest.get('belong', '')} ({guest['relation']})" if guest.get('belong') else guest['relation']
            item_rel = QTableWidgetItem(belong_rel)
            item_rel.setForeground(QColor("#cbd5e1"))
            self.table.setItem(row, 3, item_rel)

            note_att = f"{guest['attended']} {guest.get('note', '')}".strip()
            item_att = QTableWidgetItem(note_att)
            item_att.setForeground(QColor("#cbd5e1"))
            self.table.setItem(row, 4, item_att)

            msg = MessageGenerator.generate(guest)
            btn_copy = QPushButton("📋 인사말 복사")
            btn_copy.setObjectName("btnCopy")
            btn_copy.setCursor(Qt.PointingHandCursor)
            btn_copy.clicked.connect(lambda _, m=msg, g=guest: self.copy_to_clipboard(m, g))
            self.table.setCellWidget(row, 5, btn_copy)

            chk_sent = QCheckBox("발송완료")
            chk_sent.setChecked(guest.get('sent_thanks', False))
            chk_sent.stateChanged.connect(lambda state, g=guest: self.toggle_sent(state, g))
            
            chk_container = QWidget()
            chk_layout = QHBoxLayout(chk_container)
            chk_layout.addWidget(chk_sent)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 6, chk_container)

            item_raw = QTableWidgetItem(guest.get('raw', ''))
            item_raw.setForeground(QColor("#94a3b8"))
            self.table.setItem(row, 7, item_raw)

    def copy_to_clipboard(self, msg: str, guest: dict):
        clipboard = QApplication.clipboard()
        clipboard.setText(msg)
        guest['sent_thanks'] = True
        self.render_table()
        
        self.toast.show_message(f"📋 [{guest['name']}] 하객 인사말이 복사되었습니다! (Ctrl+V로 발송하세요)")

    def toggle_sent(self, state, guest):
        guest['sent_thanks'] = (state == 2)

    def update_summary(self):
        total_amt = sum(g['amount'] for g in self.guest_data)
        total_guests = len(self.guest_data)
        
        adult_cost = self.spin_adult.value()
        total_meal_fee = total_guests * adult_cost
        net_profit = total_amt - total_meal_fee

        self.card_total.set_value(f"{total_amt:,} 원")
        self.card_guests.set_value(f"{total_guests} 명")
        self.card_net.set_value(f"{net_profit:,} 원")

    def handle_export_excel(self):
        if not self.guest_data:
            QMessageBox.warning(self, "경고", "내보낼 데이터가 없습니다.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "엑셀로 저장", "축의금_리스트_취합완료.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            try:
                export_list = []
                for g in self.guest_data:
                    export_list.append({
                        '순번': g['id'],
                        '성명': g['name'],
                        '축의금액': g['amount'],
                        '소속': g.get('belong', ''),
                        '관계분류': g['relation'],
                        '참석여부': g['attended'],
                        '비고': g.get('note', ''),
                        '감사메시지': MessageGenerator.generate(g),
                        '발송완료여부': '완료' if g.get('sent_thanks') else '미발송'
                    })
                df = pd.DataFrame(export_list)
                df.to_excel(file_path, index=False)
                self.toast.show_message("📥 엑셀 파일 저장 완료!")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"엑셀 저장 실패: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = ChuguiMasterUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
