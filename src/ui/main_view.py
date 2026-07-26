import sys
import os
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QFileDialog, QHeaderView, QMessageBox, QSpinBox, QFrame,
    QCheckBox, QSplitter, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QSize
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

class MetricCard(QFrame):
    """프리미엄 대시보드 KPI 카드 컴포넌트"""
    def __init__(self, title: str, initial_value: str, icon_str: str, bg_color: str, text_color: str):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 12px;
                border: 1px solid rgba(226, 232, 240, 0.8);
            }}
        """)
        
        # 그림자 효과
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        top_layout = QHBoxLayout()
        self.lbl_icon = QLabel(icon_str)
        self.lbl_icon.setStyleSheet("font-size: 20px;")
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #64748b;")

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
        self.setWindowTitle("💍 ChuguiMaster Pro - 스마트 축의금 자동 취합 & 감사 메시지 생성기")
        self.resize(1340, 880)
        self.guest_data = []

        # 프리미엄 럭셔리 스타일시트
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8fafc;
            }
            QLabel {
                font-family: 'Pretendard', 'Segoe UI', '맑은 고딕', sans-serif;
            }
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
                padding: 12px;
                font-size: 13px;
                color: #1e293b;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 2px solid #6366f1;
            }
            QSpinBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 13px;
                font-weight: 600;
                color: #1e293b;
            }
            QPushButton {
                font-family: 'Pretendard', 'Segoe UI', '맑은 고딕';
                font-size: 14px;
                font-weight: 700;
                border-radius: 8px;
                padding: 10px 16px;
                border: none;
            }
            QPushButton#btnParse {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: white;
            }
            QPushButton#btnParse:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4338ca, stop:1 #4f46e5);
            }
            QPushButton#btnSample {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #a855f7);
                color: white;
            }
            QPushButton#btnSample:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #9333ea);
            }
            QPushButton#btnExcelImport {
                background-color: #334155;
                color: white;
            }
            QPushButton#btnExcelImport:hover {
                background-color: #1e293b;
            }
            QPushButton#btnExport {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: white;
                font-size: 15px;
            }
            QPushButton#btnExport:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
            }
            QPushButton#btnCopy {
                background-color: #ecfdf5;
                color: #047857;
                border: 1px solid #a7f3d0;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#btnCopy:hover {
                background-color: #10b981;
                color: white;
                border: none;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                gridline-color: #f1f5f9;
                selection-background-color: #e0e7ff;
                selection-color: #1e1b4b;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                font-weight: 700;
                color: #475569;
                padding: 10px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
            }
        """)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. 상단 프리미엄 KPI 대시보드 카드 레이아웃
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(14)

        self.card_total = MetricCard("총 수령 축의금", "0 원", "💳", "#ffffff", "#4f46e5")
        self.card_guests = MetricCard("총 하객 수", "0 명", "👥", "#ffffff", "#0284c7")
        
        # 대인/소인 식대 설정 전용 스마트 카드
        meal_card = QFrame()
        meal_card.setStyleSheet("background-color: #ffffff; border-radius: 12px; border: 1px solid rgba(226, 232, 240, 0.8);")
        shadow = QGraphicsDropShadowEffect(meal_card)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 4)
        meal_card.setSet = meal_card.setGraphicsEffect(shadow)

        meal_layout = QVBoxLayout(meal_card)
        meal_layout.setContentsMargins(16, 12, 16, 12)
        
        meal_title_layout = QHBoxLayout()
        lbl_meal_icon = QLabel("🍽️")
        lbl_meal_icon.setStyleSheet("font-size: 18px;")
        lbl_meal_title = QLabel("식대 단가 설정 (대인 / 소인)")
        lbl_meal_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #64748b;")
        meal_title_layout.addWidget(lbl_meal_icon)
        meal_title_layout.addWidget(lbl_meal_title)
        meal_title_layout.addStretch()

        inputs_layout = QHBoxLayout()
        inputs_layout.addWidget(QLabel("대인:"))
        self.spin_adult = QSpinBox()
        self.spin_adult.setRange(0, 500000)
        self.spin_adult.setValue(42000)
        self.spin_adult.setSingleStep(1000)
        self.spin_adult.setSuffix("원")
        self.spin_adult.valueChanged.connect(self.update_summary)
        inputs_layout.addWidget(self.spin_adult)

        inputs_layout.addWidget(QLabel("소인:"))
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

        self.card_net = MetricCard("최종 순 정산금 (수익)", "0 원", "💰", "#ecfdf5", "#059669")

        kpi_layout.addWidget(self.card_total, 1)
        kpi_layout.addWidget(self.card_guests, 1)
        kpi_layout.addWidget(meal_card, 1)
        kpi_layout.addWidget(self.card_net, 1)

        main_layout.addLayout(kpi_layout)

        # 2. 메인 콘텐츠 스플리터 (입력 박스 vs 데이터 표)
        splitter = QSplitter(Qt.Horizontal)

        # 좌측 텍스트 입력 패널
        left_card = QFrame()
        left_card.setStyleSheet("background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0;")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)

        lbl_input_header = QLabel("📋 축의금 리스트 텍스트 입력")
        lbl_input_header.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e293b;")
        
        lbl_input_desc = QLabel("카톡/메모장의 글을 그대로 붙여넣으세요. (예: 홍길동 10만원 친척)")
        lbl_input_desc.setStyleSheet("font-size: 12px; color: #64748b; margin-bottom: 4px;")

        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("여기에 축의금 리스트를 붙여넣으세요...\n\n예시:\n홍길동 200,000 친척모임\n최동료 100,000 A보건지소\n김가족,김친지 300,000 C이모")

        btn_parse = QPushButton("⚡ 1초 자동 취합 및 파싱")
        btn_parse.setObjectName("btnParse")
        btn_parse.setCursor(Qt.PointingHandCursor)
        btn_parse.clicked.connect(self.handle_parse_text)

        btn_sample = QPushButton("🎯 100% 가명화 샘플 불러오기")
        btn_sample.setObjectName("btnSample")
        btn_sample.setCursor(Qt.PointingHandCursor)
        btn_sample.clicked.connect(self.handle_load_sample)

        btn_excel_import = QPushButton("📂 엑셀 파일(.xlsx) 불러오기")
        btn_excel_import.setObjectName("btnExcelImport")
        btn_excel_import.setCursor(Qt.PointingHandCursor)
        btn_excel_import.clicked.connect(self.handle_excel_import)

        left_layout.addWidget(lbl_input_header)
        left_layout.addWidget(lbl_input_desc)
        left_layout.addWidget(self.txt_input)
        left_layout.addSpacing(6)
        left_layout.addWidget(btn_parse)
        left_layout.addWidget(btn_sample)
        left_layout.addWidget(btn_excel_import)

        splitter.addWidget(left_card)

        # 우측 데이터 표 및 엑셀 내보내기 패널
        right_card = QFrame()
        right_card.setStyleSheet("background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0;")
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(16, 16, 16, 16)

        lbl_table_header = QLabel("📜 스마트 취합 결과 & 1초 감사 인사 복사")
        lbl_table_header.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e293b; margin-bottom: 4px;")

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

        right_layout.addWidget(lbl_table_header)
        right_layout.addWidget(self.table)
        right_layout.addSpacing(6)
        right_layout.addWidget(btn_export)

        splitter.addWidget(right_card)

        splitter.setSizes([440, 860])
        main_layout.addWidget(splitter)

    def handle_load_sample(self):
        self.txt_input.setPlainText(SAMPLE_RAW_TEXT)
        self.handle_parse_text()
        QMessageBox.information(self, "샘플 취합 완료", "가명화 처리된 샘플 데이터 27건이 취합되었습니다!")

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
                QMessageBox.information(self, "성공", f"{len(self.guest_data)}건의 축의금 데이터를 가져왔습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"엑셀 읽기 실패: {str(e)}")

    def render_table(self):
        self.table.setRowCount(0)
        for idx, guest in enumerate(self.guest_data):
            row = self.table.rowCount()
            self.table.insertRow(row)

            # NO
            item_id = QTableWidgetItem(str(guest['id']))
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_id)

            # 이름
            item_name = QTableWidgetItem(guest['name'])
            item_name.setFont(QFont("Pretendard", 10, QFont.Bold))
            self.table.setItem(row, 1, item_name)

            # 금액
            amt_str = f"{guest['amount']:,} 원"
            item_amt = QTableWidgetItem(amt_str)
            item_amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_amt.setForeground(QColor("#1e1b4b"))
            item_amt.setFont(QFont("Pretendard", 10, QFont.Bold))
            self.table.setItem(row, 2, item_amt)

            # 관계/소속
            belong_rel = f"{guest.get('belong', '')} ({guest['relation']})" if guest.get('belong') else guest['relation']
            self.table.setItem(row, 3, QTableWidgetItem(belong_rel))

            # 참석/비고
            note_att = f"{guest['attended']} {guest.get('note', '')}".strip()
            self.table.setItem(row, 4, QTableWidgetItem(note_att))

            # 1초 복사 버튼
            msg = MessageGenerator.generate(guest)
            btn_copy = QPushButton("📋 인사말 복사")
            btn_copy.setObjectName("btnCopy")
            btn_copy.setCursor(Qt.PointingHandCursor)
            btn_copy.clicked.connect(lambda _, m=msg, g=guest: self.copy_to_clipboard(m, g))
            self.table.setCellWidget(row, 5, btn_copy)

            # 발송 상태 체크박스
            chk_sent = QCheckBox("발송완료")
            chk_sent.setChecked(guest.get('sent_thanks', False))
            chk_sent.stateChanged.connect(lambda state, g=guest: self.toggle_sent(state, g))
            
            chk_container = QWidget()
            chk_layout = QHBoxLayout(chk_container)
            chk_layout.addWidget(chk_sent)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 6, chk_container)

            # 원문
            self.table.setItem(row, 7, QTableWidgetItem(guest.get('raw', '')))

    def copy_to_clipboard(self, msg: str, guest: dict):
        clipboard = QApplication.clipboard()
        clipboard.setText(msg)
        guest['sent_thanks'] = True
        self.render_table()
        QMessageBox.information(self, "1초 복사 완료", f"[{guest['name']}] 하객 감사 메시지가 클립보드에 복사되었습니다!\n\n카톡이나 문자 입력창에 Ctrl + V 하세요.")

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
                QMessageBox.information(self, "성공", "엑셀 파일이 성공적으로 저장되었습니다!")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"엑셀 저장 실패: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = ChuguiMasterUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
