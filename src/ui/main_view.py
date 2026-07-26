import sys
import os
import json
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QFileDialog, QHeaderView, QMessageBox, QSpinBox, QFrame,
    QCheckBox, QSplitter, QGraphicsDropShadowEffect, QDialog, QTabWidget,
    QGraphicsOpacityEffect, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QFont, QColor, QClipboard, QDragEnterEvent, QDropEvent

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smart_parser import SmartParser
from message_generator import MessageGenerator

CONFIG_FILE = "config_settings.json"

CATEGORIES = ['친척/가족', '직장/기관', '종교/모임', '학교/동창', '지인/기타']

BADGE_STYLES = {
    '친척/가족': "QComboBox { background-color: #3b0764; color: #c084fc; border: 1px solid #7e22ce; border-radius: 8px; font-weight: bold; font-size: 11px; padding: 2px 6px; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background-color: #1e293b; color: #f8fafc; selection-background-color: #7e22ce; }",
    '직장/기관': "QComboBox { background-color: #1e1b4b; color: #818cf8; border: 1px solid #4338ca; border-radius: 8px; font-weight: bold; font-size: 11px; padding: 2px 6px; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background-color: #1e293b; color: #f8fafc; selection-background-color: #4338ca; }",
    '종교/모임': "QComboBox { background-color: #064e3b; color: #34d399; border: 1px solid #047857; border-radius: 8px; font-weight: bold; font-size: 11px; padding: 2px 6px; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background-color: #1e293b; color: #f8fafc; selection-background-color: #047857; }",
    '학교/동창': "QComboBox { background-color: #451a03; color: #fbbf24; border: 1px solid #b45309; border-radius: 8px; font-weight: bold; font-size: 11px; padding: 2px 6px; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background-color: #1e293b; color: #f8fafc; selection-background-color: #b45309; }",
    '지인/기타': "QComboBox { background-color: #334155; color: #cbd5e1; border: 1px solid #475569; border-radius: 8px; font-weight: bold; font-size: 11px; padding: 2px 6px; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background-color: #1e293b; color: #f8fafc; selection-background-color: #475569; }"
}

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

def load_app_config() -> dict:
    default_config = {"adult_meal": 42000, "child_meal": 25000}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
    return default_config

def save_app_config(adult_meal: int, child_meal: int):
    try:
        data = {"adult_meal": adult_meal, "child_meal": child_meal}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class ToastNotification(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.update_theme(dark_mode=True)

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

    def update_theme(self, dark_mode: bool):
        if dark_mode:
            self.setStyleSheet("""
                QFrame {
                    background-color: #334155;
                    color: #f8fafc;
                    border-radius: 12px;
                    padding: 8px 18px;
                    border: 1px solid #64748b;
                }
                QLabel { color: #f8fafc; font-family: 'Pretendard', sans-serif; font-size: 13px; font-weight: 700; border: none; background: transparent; }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #1e293b;
                    color: #ffffff;
                    border-radius: 12px;
                    padding: 8px 18px;
                    border: 1px solid #475569;
                }
                QLabel { color: #ffffff; font-family: 'Pretendard', sans-serif; font-size: 13px; font-weight: 700; border: none; background: transparent; }
            """)

    def show_message(self, message: str, duration_ms: int = 1800):
        self.lbl_text.setText(message)
        self.adjustSize()

        if self.parent():
            p_rect = self.parent().rect()
            x = (p_rect.width() - self.width()) // 2
            y = p_rect.height() - self.height() - 40
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


class DropTextEdit(QTextEdit):
    def __init__(self, parent_view, parent=None):
        super().__init__(parent)
        self.parent_view = parent_view
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.endswith(('.xlsx', '.xls', '.csv')):
                self.parent_view.load_excel_file(file_path)
            else:
                super().dropEvent(event)


class TemplateSettingsDialog(QDialog):
    def __init__(self, dark_mode=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 감사 인사말 템플릿 맞춤 세팅")
        self.resize(680, 560)
        self.dark_mode = dark_mode
        self.current_templates = json.loads(json.dumps(MessageGenerator.get_templates()))
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        bg = "#0f172a" if self.dark_mode else "#ffffff"
        text_color = "#f8fafc" if self.dark_mode else "#1e293b"
        self.setStyleSheet(f"QDialog {{ background-color: {bg}; font-family: 'Pretendard', sans-serif; }} QLabel {{ color: {text_color}; border: none; background: transparent; }}")

        header_title = QLabel("⚙️ 관계별 & 참석 상황별 인사말 세팅")
        header_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #818cf8;")
        
        header_desc = QLabel("원하시는 문구로 자유롭게 수정하세요. `{name}`은 하객 이름으로 자동 치환됩니다.")
        header_desc.setStyleSheet("font-size: 12px; color: #94a3b8; margin-bottom: 8px;")

        layout.addWidget(header_title)
        layout.addWidget(header_desc)

        self.tab_widget = QTabWidget()
        tab_bg = "#1e293b" if self.dark_mode else "#f1f5f9"
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid #334155; border-radius: 8px; background: {bg}; }}
            QTabBar::tab {{ background: {tab_bg}; padding: 10px 18px; font-weight: 600; color: #94a3b8; }}
            QTabBar::tab:selected {{ background: #334155; color: #818cf8; border-bottom: 2px solid #818cf8; }}
        """)

        self.editors = {}

        for category in CATEGORIES:
            cat_tab = QWidget()
            cat_layout = QVBoxLayout(cat_tab)
            cat_layout.setContentsMargins(14, 14, 14, 14)

            cat_layout.addWidget(QLabel(f"<b>[{category}] 직접 참석시 인사말:</b>"))
            txt_attend = QTextEdit()
            txt_attend.setPlainText(self.current_templates.get(category, {}).get('참석', ''))
            cat_layout.addWidget(txt_attend)

            cat_layout.addSpacing(6)
            cat_layout.addWidget(QLabel(f"<b>[{category}] 불참(송금)시 인사말:</b>"))
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
        btn_save.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1); color: white; font-weight: bold; border-radius: 6px; padding: 10px 16px;")
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
    def __init__(self, dark_mode=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("❓ 텍스트 입력 및 취합 가이드")
        self.resize(540, 460)
        self.dark_mode = dark_mode
        
        bg = "#0f172a" if self.dark_mode else "#ffffff"
        text_color = "#f8fafc" if self.dark_mode else "#1e293b"
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                font-family: 'Pretendard', 'Segoe UI', '맑은 고딕', sans-serif;
            }}
            QLabel {{
                color: {text_color};
                border: none;
                background: transparent;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        
        title = QLabel("💡 축의금 자유 텍스트 작성 팁")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #818cf8;")
        layout.addWidget(title)
        
        code_color = "#a5b4fc" if self.dark_mode else "#4f46e5"
        body_color = "#cbd5e1" if self.dark_mode else "#334155"
        
        guide_html = f"""
ChuguiMaster는 카톡이나 메모장에 작성한 자유 서식 텍스트를 
규칙 기반 스마트 파서가 1초 만에 자동 분석합니다.

📌 <b>작성 지원 양식 예시:</b>
• <b>기본형</b>: <code style='color:{code_color};'>이름 금액 소속</code> (예: 홍길동 10만원 친척)
• <b>부부/가족</b>: <code style='color:{code_color};'>이름1,이름2 금액</code> (예: 김가족,김친지 300,000원 C이모)
• <b>식권 지정</b>: <code style='color:{code_color};'>이름 금액 식권수</code> (예: 최동료 10만 식권2)
• <b>불참/송금</b>: <code style='color:{code_color};'>이름 금액 불참</code> (예: 박지성 5만원 불참)

📌 <b>금액 파싱 형식:</b>
• <code style='color:{code_color};'>10만원</code>, <code style='color:{code_color};'>10만</code>, <code style='color:{code_color};'>100,000</code>, <code style='color:{code_color};'>100000</code> 모두 자동 지원됩니다.

📌 <b>인사말 세팅:</b>
• 상단 우측 <code style='color:#818cf8;'>⚙️ 감사 인사말 템플릿 세팅</code> 버튼을 통해 나만의 감사 문구를 자유롭게 수정할 수 있습니다.
        """
        guide_txt = QLabel(guide_html)
        guide_txt.setStyleSheet(f"font-size: 13px; color: {body_color}; line-height: 1.6;")
        guide_txt.setWordWrap(True)
        layout.addWidget(guide_txt)
        
        btn_close = QPushButton("확인했습니다")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("background-color: #6366f1; color: white; font-weight: bold; border-radius: 6px; padding: 10px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class CompactMetricCard(QFrame):
    def __init__(self, title: str, initial_value: str, icon_str: str, text_color: str):
        super().__init__()
        self.setObjectName("compactCard")
        self.setFixedHeight(75)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        left_box = QVBoxLayout()
        left_box.setSpacing(2)

        icon_title_layout = QHBoxLayout()
        lbl_icon = QLabel(icon_str)
        lbl_icon.setStyleSheet("font-size: 16px; border: none; background: transparent;")
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 12px; font-weight: 600; color: #94a3b8; border: none; background: transparent;")

        icon_title_layout.addWidget(lbl_icon)
        icon_title_layout.addWidget(lbl_title)
        icon_title_layout.addStretch()

        left_box.addLayout(icon_title_layout)

        self.lbl_val = QLabel(initial_value)
        self.lbl_val.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {text_color}; border: none; background: transparent; font-family: 'Pretendard', sans-serif;")
        left_box.addWidget(self.lbl_val)

        layout.addLayout(left_box)

    def set_value(self, val_str: str):
        self.lbl_val.setText(val_str)


class ChuguiMasterUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("💍 ChuguiMaster Pro - 스마트 축의금 정산 & 감사 메시지")
        self.resize(1360, 880)
        self.guest_data = []
        self.dark_mode = True

        self.saved_config = load_app_config()

        self.init_ui()
        self.apply_theme()
        self.toast = ToastNotification(self)

    def apply_theme(self):
        if self.dark_mode:
            self.btn_theme.setText("☀️ 라이트 모드로 전환")
            self.setStyleSheet("""
                QMainWindow { background-color: #0f172a; }
                QLabel { font-family: 'Pretendard', sans-serif; color: #f8fafc; border: none; background: transparent; }
                QFrame#compactCard {
                    background-color: #1e293b;
                    border-radius: 10px;
                    border: 1px solid #334155;
                }
                QFrame#netCard {
                    background-color: #064e3b;
                    border-radius: 10px;
                    border: 1px solid #047857;
                }
                QTextEdit { background-color: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 10px; font-size: 13px; color: #f8fafc; }
                QSpinBox, QLineEdit, QComboBox { background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 4px 8px; font-size: 12px; font-weight: 600; color: #f8fafc; min-height: 26px; }
                QPushButton { font-family: 'Pretendard', sans-serif; font-size: 13px; font-weight: 700; border-radius: 6px; padding: 8px 14px; min-height: 34px; border: none; color: #ffffff; }
                QPushButton#btnParse { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1); }
                QPushButton#btnSample { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #8b5cf6); }
                QPushButton#btnSettings { background-color: #1e293b; color: #a5b4fc; border: 1px solid #4338ca; min-height: 26px; font-size: 12px; }
                QPushButton#btnTheme { background-color: #1e293b; color: #f59e0b; border: 1px solid #d97706; min-height: 26px; font-size: 12px; }
                QPushButton#btnHelp { background-color: #1e293b; color: #cbd5e1; border: 1px solid #475569; min-height: 24px; font-size: 11px; }
                QPushButton#btnExcelImport { background-color: #334155; color: #f8fafc; border: 1px solid #475569; }
                QPushButton#btnExport { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981); font-size: 14px; }
                QPushButton#btnCopy { background-color: #064e3b; color: #6ee7b7; border: 1px solid #047857; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 700; min-height: 22px; }
                QPushButton#btnCopy:hover { background-color: #10b981; color: #ffffff; }
                
                QTableWidget {
                    background-color: #0f172a;
                    alternate-background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 10px;
                    gridline-color: #1e293b;
                    font-size: 13px;
                    color: #f8fafc;
                }
                QTableWidget::item {
                    color: #f8fafc;
                    padding: 4px;
                }
                QHeaderView::section { background-color: #1e293b; font-weight: 700; color: #cbd5e1; padding: 8px; border: none; border-bottom: 2px solid #334155; }
                QCheckBox { color: #cbd5e1; border: none; background: transparent; }
            """)
        else:
            self.btn_theme.setText("🌙 다크 모드로 전환")
            self.setStyleSheet("""
                QMainWindow { background-color: #f8fafc; }
                QLabel { font-family: 'Pretendard', sans-serif; color: #1e293b; border: none; background: transparent; }
                QFrame#compactCard {
                    background-color: #ffffff;
                    border-radius: 10px;
                    border: 1px solid #e2e8f0;
                }
                QFrame#netCard {
                    background-color: #ecfdf5;
                    border-radius: 10px;
                    border: 1px solid #a7f3d0;
                }
                QTextEdit { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 10px; padding: 10px; font-size: 13px; color: #1e293b; }
                QSpinBox, QLineEdit, QComboBox { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 8px; font-size: 12px; font-weight: 600; color: #1e293b; min-height: 26px; }
                QPushButton { font-family: 'Pretendard', sans-serif; font-size: 13px; font-weight: 700; border-radius: 6px; padding: 8px 14px; min-height: 34px; border: none; color: #ffffff; }
                QPushButton#btnParse { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1); }
                QPushButton#btnSample { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #a855f7); }
                QPushButton#btnSettings { background-color: #ffffff; color: #4338ca; border: 1px solid #c7d2fe; min-height: 26px; font-size: 12px; }
                QPushButton#btnTheme { background-color: #ffffff; color: #4f46e5; border: 1px solid #818cf8; min-height: 26px; font-size: 12px; }
                QPushButton#btnHelp { background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; min-height: 24px; font-size: 11px; }
                QPushButton#btnExcelImport { background-color: #334155; color: white; }
                QPushButton#btnExport { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981); font-size: 14px; }
                QPushButton#btnCopy { background-color: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 700; min-height: 22px; }
                QPushButton#btnCopy:hover { background-color: #10b981; color: white; }
                
                QTableWidget {
                    background-color: #ffffff;
                    alternate-background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                    gridline-color: #f1f5f9;
                    font-size: 13px;
                    color: #1e293b;
                }
                QTableWidget::item {
                    color: #1e293b;
                    padding: 4px;
                }
                QHeaderView::section { background-color: #f8fafc; font-weight: 700; color: #475569; padding: 8px; border: none; border-bottom: 2px solid #e2e8f0; }
                QCheckBox { color: #475569; border: none; background: transparent; }
            """)
        
        if hasattr(self, 'toast'):
            self.toast.update_theme(self.dark_mode)

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.render_table()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        header_bar = QHBoxLayout()
        title_app = QLabel("💍 ChuguiMaster Pro")
        title_app.setStyleSheet("font-size: 17px; font-weight: 800; color: #818cf8; border: none;")
        
        self.btn_theme = QPushButton("☀️ 라이트 모드로 전환")
        self.btn_theme.setObjectName("btnTheme")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)

        btn_settings = QPushButton("⚙️ 감사 인사말 템플릿 세팅")
        btn_settings.setObjectName("btnSettings")
        btn_settings.setCursor(Qt.PointingHandCursor)
        btn_settings.clicked.connect(self.show_template_settings)

        header_bar.addWidget(title_app)
        header_bar.addStretch()
        header_bar.addWidget(self.btn_theme)
        header_bar.addWidget(btn_settings)

        main_layout.addLayout(header_bar)

        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(10)

        self.card_total = CompactMetricCard("총 수령 축의금", "0 원", "💳", "#818cf8")
        self.card_guests = CompactMetricCard("총 하객 수", "0 명", "👥", "#38bdf8")
        
        meal_card = QFrame()
        meal_card.setObjectName("compactCard")
        meal_card.setFixedHeight(75)

        meal_layout = QVBoxLayout(meal_card)
        meal_layout.setContentsMargins(12, 8, 12, 8)
        meal_layout.setSpacing(4)

        lbl_meal_title = QLabel("🍽️ 식대 단가 설정")
        lbl_meal_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #94a3b8;")

        inputs_layout = QHBoxLayout()
        inputs_layout.setSpacing(6)
        
        lbl_ad = QLabel("대인:")
        inputs_layout.addWidget(lbl_ad)
        
        self.spin_adult = QSpinBox()
        self.spin_adult.setRange(0, 500000)
        self.spin_adult.setValue(self.saved_config.get("adult_meal", 42000))
        self.spin_adult.setSingleStep(1000)
        self.spin_adult.setSuffix("원")
        self.spin_adult.valueChanged.connect(self.update_summary)
        inputs_layout.addWidget(self.spin_adult)

        lbl_ch = QLabel("소인:")
        inputs_layout.addWidget(lbl_ch)
        
        self.spin_child = QSpinBox()
        self.spin_child.setRange(0, 500000)
        self.spin_child.setValue(self.saved_config.get("child_meal", 25000))
        self.spin_child.setSingleStep(1000)
        self.spin_child.setSuffix("원")
        self.spin_child.valueChanged.connect(self.update_summary)
        inputs_layout.addWidget(self.spin_child)

        meal_layout.addWidget(lbl_meal_title)
        meal_layout.addLayout(inputs_layout)

        self.card_net = CompactMetricCard("최종 순 정산금 (수익)", "0 원", "💰", "#34d399")
        self.card_net.setObjectName("netCard")

        kpi_layout.addWidget(self.card_total, 1)
        kpi_layout.addWidget(self.card_guests, 1)
        kpi_layout.addWidget(meal_card, 1)
        kpi_layout.addWidget(self.card_net, 1)

        main_layout.addLayout(kpi_layout)

        splitter = QSplitter(Qt.Horizontal)

        left_card = QFrame()
        left_card.setObjectName("compactCard")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(8)

        left_header_layout = QHBoxLayout()
        lbl_input_header = QLabel("📋 텍스트 입력 & Drag&Drop 수신")
        lbl_input_header.setStyleSheet("font-size: 14px; font-weight: 700;")
        
        btn_help = QPushButton("❓ 작성 가이드")
        btn_help.setObjectName("btnHelp")
        btn_help.setCursor(Qt.PointingHandCursor)
        btn_help.clicked.connect(self.show_help)

        left_header_layout.addWidget(lbl_input_header)
        left_header_layout.addStretch()
        left_header_layout.addWidget(btn_help)

        guide_box = QFrame()
        guide_box.setStyleSheet("background-color: rgba(15, 23, 42, 0.4); border-radius: 6px; border: 1px dashed #475569;")
        gb_layout = QVBoxLayout(guide_box)
        gb_layout.setContentsMargins(8, 6, 8, 6)
        
        lbl_guide = QLabel("<b style='color:#818cf8;'>[입력 팁]</b> 텍스트를 복붙하거나 <b>엑셀(.xlsx)을 드래그앤드롭하세요.</b><br>• <code>홍길동 10만원 친척</code> | <code>김가족,김친지 30만 C이모</code>")
        lbl_guide.setStyleSheet("font-size: 11px; color: #94a3b8; line-height: 1.3;")
        gb_layout.addWidget(lbl_guide)

        self.txt_input = DropTextEdit(self)
        self.txt_input.setPlaceholderText("여기에 축의금 텍스트를 붙여넣거나 엑셀 파일(.xlsx)을 끌어다 놓으세요...\n\n입력 예시:\n홍길동 200,000 친척모임\n최동료 100,000 A보건지소 식권2\n김가족,김친지 300,000 C이모")

        btn_parse = QPushButton("⚡ 1초 자동 취합 및 파싱 실행")
        btn_parse.setObjectName("btnParse")
        btn_parse.setCursor(Qt.PointingHandCursor)
        btn_parse.clicked.connect(self.handle_parse_text)

        btn_sample = QPushButton("🎯 100% 가명화 샘플 데이터 불러오기")
        btn_sample.setObjectName("btnSample")
        btn_sample.setCursor(Qt.PointingHandCursor)
        btn_sample.clicked.connect(self.handle_load_sample)

        btn_excel_import = QPushButton("📂 엑셀 파일(.xlsx) 수동 불러오기")
        btn_excel_import.setObjectName("btnExcelImport")
        btn_excel_import.setCursor(Qt.PointingHandCursor)
        btn_excel_import.clicked.connect(self.handle_excel_import)

        left_layout.addLayout(left_header_layout)
        left_layout.addWidget(guide_box)
        left_layout.addWidget(self.txt_input)
        left_layout.addWidget(btn_parse)
        left_layout.addWidget(btn_sample)
        left_layout.addWidget(btn_excel_import)

        splitter.addWidget(left_card)

        right_card = QFrame()
        right_card.setObjectName("compactCard")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(8)

        right_header_layout = QHBoxLayout()
        lbl_table_header = QLabel("📜 스마트 취합 결과 표")
        lbl_table_header.setStyleSheet("font-size: 14px; font-weight: 700;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 실시간 검색...")
        self.search_input.setFixedWidth(160)
        self.search_input.textChanged.connect(self.apply_filter)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["전체 관계", "친척/가족", "직장/기관", "종교/모임", "학교/동창", "지인/기타"])
        self.filter_combo.setFixedWidth(110)
        self.filter_combo.currentTextChanged.connect(self.apply_filter)

        right_header_layout.addWidget(lbl_table_header)
        right_header_layout.addStretch()
        right_header_layout.addWidget(self.search_input)
        right_header_layout.addWidget(self.filter_combo)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "NO", "성명(하객)", "축의금액", "관계 태그 (선택 변경 가능)", "참석/비고", "1초 감사 메시지 복사", "발송상태", "원문"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)

        btn_export = QPushButton("📥 완성된 취합 결과 엑셀 파일로 저장 (xlsx)")
        btn_export.setObjectName("btnExport")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self.handle_export_excel)

        right_layout.addLayout(right_header_layout)
        right_layout.addWidget(self.table)
        right_layout.addWidget(btn_export)

        splitter.addWidget(right_card)

        splitter.setSizes([430, 870])
        main_layout.addWidget(splitter)

    def load_excel_file(self, file_path: str):
        try:
            self.guest_data = SmartParser.parse_excel(file_path)
            self.render_table()
            self.update_summary()
            self.toast.show_message(f"📂 Drag&Drop 엑셀 수신: {len(self.guest_data)}건 가져오기 완료!")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"엑셀 읽기 실패: {str(e)}")

    def show_template_settings(self):
        try:
            dialog = TemplateSettingsDialog(dark_mode=self.dark_mode, parent=self)
            if dialog.exec():
                self.render_table()
        except Exception as e:
            QMessageBox.critical(self, "설정 오류", f"템플릿 세팅 팝업 열기 실패: {str(e)}")

    def show_help(self):
        try:
            dialog = HelpDialog(dark_mode=self.dark_mode, parent=self)
            if hasattr(dialog, 'exec_'):
                dialog.exec_()
            else:
                dialog.exec()
        except Exception as e:
            QMessageBox.information(self, "작성 가이드", "📌 **입력 양식 예시**:\n홍길동 10만원 친척\n김가족,김친지 30만 C이모\n최동료 10만 식권2\n\n- 텍스트나 엑셀(.xlsx)을 이 창에 붙여넣거나 끌어다 놓으세요!")

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
            self.load_excel_file(file_path)

    def create_category_combo(self, guest: dict) -> QComboBox:
        """클릭하여 자유롭게 변경할 수 있는 스마트 드롭다운 관계 뱃지 콤보박스"""
        combo = QComboBox()
        combo.addItems(CATEGORIES)
        
        current_rel = guest.get('relation', '지인/기타')
        if current_rel not in CATEGORIES:
            current_rel = '지인/기타'
            
        combo.setCurrentText(current_rel)
        combo.setStyleSheet(BADGE_STYLES.get(current_rel, BADGE_STYLES['지인/기타']))
        combo.setCursor(Qt.PointingHandCursor)
        
        # 💡 선택 변경 시 하객 객체와 뱃지 색상, 인사말 실시간 자동 업데이트!
        def on_category_changed(new_cat: str):
            guest['relation'] = new_cat
            combo.setStyleSheet(BADGE_STYLES.get(new_cat, BADGE_STYLES['지인/기타']))
            self.render_table()
            self.toast.show_message(f"🏷️ [{guest['name']}] 카테고리가 '{new_cat}'(으)로 변경되었습니다!")

        combo.currentTextChanged.connect(on_category_changed)
        return combo

    def render_table(self):
        self.table.setRowCount(0)
        search_query = self.search_input.text().strip().lower()
        filter_rel = self.filter_combo.currentText()

        text_fg_color = QColor("#f8fafc") if self.dark_mode else QColor("#1e293b")
        amt_fg_color = QColor("#818cf8") if self.dark_mode else QColor("#4338ca")
        sub_fg_color = QColor("#cbd5e1") if self.dark_mode else QColor("#475569")
        raw_fg_color = QColor("#94a3b8") if self.dark_mode else QColor("#64748b")

        for idx, guest in enumerate(self.guest_data):
            name = guest['name']
            belong_rel = f"{guest.get('belong', '')} ({guest['relation']})"
            
            if filter_rel != "전체 관계" and guest['relation'] != filter_rel:
                continue
            if search_query and not (search_query in name.lower() or search_query in belong_rel.lower()):
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            # 0. NO
            item_id = QTableWidgetItem(str(guest['id']))
            item_id.setTextAlignment(Qt.AlignCenter)
            item_id.setForeground(sub_fg_color)
            self.table.setItem(row, 0, item_id)

            # 1. 성명
            item_name = QTableWidgetItem(name)
            item_name.setFont(QFont("Pretendard", 10, QFont.Bold))
            item_name.setForeground(text_fg_color)
            self.table.setItem(row, 1, item_name)

            # 2. 축의금액
            amt_str = f"{guest['amount']:,} 원"
            item_amt = QTableWidgetItem(amt_str)
            item_amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_amt.setFont(QFont("Pretendard", 10, QFont.Bold))
            item_amt.setForeground(amt_fg_color)
            self.table.setItem(row, 2, item_amt)

            # 3. 🌟 드롭다운 변경 가능 관계 태그 콤보박스
            combo_widget = self.create_category_combo(guest)
            combo_container = QWidget()
            c_layout = QHBoxLayout(combo_container)
            c_layout.addWidget(combo_widget)
            c_layout.setAlignment(Qt.AlignCenter)
            c_layout.setContentsMargins(2, 2, 2, 2)
            self.table.setCellWidget(row, 3, combo_container)

            # 4. 참석/비고
            note_att = f"{guest['attended']} {guest.get('note', '')}".strip()
            item_att = QTableWidgetItem(note_att)
            item_att.setForeground(sub_fg_color)
            self.table.setItem(row, 4, item_att)

            # 5. 1초 복사 버튼
            msg = MessageGenerator.generate(guest)
            btn_copy = QPushButton("📋 인사말 복사")
            btn_copy.setObjectName("btnCopy")
            btn_copy.setCursor(Qt.PointingHandCursor)
            btn_copy.clicked.connect(lambda _, m=msg, g=guest: self.copy_to_clipboard(m, g))
            self.table.setCellWidget(row, 5, btn_copy)

            # 6. 발송상태 체크
            chk_sent = QCheckBox("발송완료")
            chk_sent.setChecked(guest.get('sent_thanks', False))
            chk_sent.stateChanged.connect(lambda state, g=guest: self.toggle_sent(state, g))
            
            chk_container = QWidget()
            chk_layout = QHBoxLayout(chk_container)
            chk_layout.addWidget(chk_sent)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 6, chk_container)

            # 7. 원문
            item_raw = QTableWidgetItem(guest.get('raw', ''))
            item_raw.setForeground(raw_fg_color)
            self.table.setItem(row, 7, item_raw)

    def apply_filter(self):
        self.render_table()

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
        child_cost = self.spin_child.value()
        
        save_app_config(adult_cost, child_cost)

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
