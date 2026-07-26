import sys
import os
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QLabel,
    QFileDialog, QHeaderView, QMessageBox, QSpinBox, QGroupBox,
    QCheckBox, QSplitter, QFrame
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QClipboard

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smart_parser import SmartParser
from message_generator import MessageGenerator

# 🔒 완전히 개인정보 가명화(Anonymized) 처리된 샘플 테스트 데이터
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

class ChuguiMasterUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("💍 ChuguiMaster - 스마트 축의금 자동 취합 & 감사 메시지 생성기")
        self.resize(1300, 850)
        self.guest_data = []
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f4f6f9; }
            QGroupBox {
                font-weight: bold;
                border: 1.5px solid #dcdfe6;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #1e293b;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 14px;
                border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton#btnSample { background-color: #8b5cf6; }
            QPushButton#btnSample:hover { background-color: #7c3aed; }
            QPushButton#btnCopy { background-color: #10b981; padding: 4px 8px; font-size: 12px; }
            QPushButton#btnCopy:hover { background-color: #059669; }
            QPushButton#btnExcel { background-color: #059669; font-size: 14px; }
            QPushButton#btnExcel:hover { background-color: #047857; }
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                font-weight: bold;
                color: #334155;
                padding: 6px;
                border: none;
            }
        """)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 1. 상단 결산 요약 대시보드
        summary_group = QGroupBox("📊 1초 실시간 축의금 & 대인/소인 식대 정산 대시보드")
        summary_layout = QHBoxLayout(summary_group)

        self.lbl_total_amount = QLabel("총 축의금: 0 원")
        self.lbl_total_amount.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e3a8a;")
        
        self.lbl_guest_count = QLabel("총 하객: 0 명")
        self.lbl_guest_count.setStyleSheet("font-size: 15px; font-weight: bold; color: #334155;")

        adult_meal_layout = QHBoxLayout()
        adult_meal_layout.addWidget(QLabel("대인 단가:"))
        self.spin_adult_meal = QSpinBox()
        self.spin_adult_meal.setRange(0, 500000)
        self.spin_adult_meal.setSingleStep(1000)
        self.spin_adult_meal.setValue(42000)
        self.spin_adult_meal.setSuffix(" 원")
        self.spin_adult_meal.valueChanged.connect(self.update_summary)
        adult_meal_layout.addWidget(self.spin_adult_meal)

        child_meal_layout = QHBoxLayout()
        child_meal_layout.addWidget(QLabel("소인 단가:"))
        self.spin_child_meal = QSpinBox()
        self.spin_child_meal.setRange(0, 500000)
        self.spin_child_meal.setSingleStep(1000)
        self.spin_child_meal.setValue(25000)
        self.spin_child_meal.setSuffix(" 원")
        self.spin_child_meal.valueChanged.connect(self.update_summary)
        child_meal_layout.addWidget(self.spin_child_meal)

        self.lbl_net_profit = QLabel("순 정산금: 0 원")
        self.lbl_net_profit.setStyleSheet("font-size: 16px; font-weight: bold; color: #059669;")

        summary_layout.addWidget(self.lbl_total_amount)
        summary_layout.addWidget(self.lbl_guest_count)
        summary_layout.addLayout(adult_meal_layout)
        summary_layout.addLayout(child_meal_layout)
        summary_layout.addWidget(self.lbl_net_profit)
        
        main_layout.addWidget(summary_group)

        # 2. 스플리터 레이아웃
        splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        input_group = QGroupBox("📋 입력 및 가명화 샘플 테스트")
        input_inner_layout = QVBoxLayout(input_group)
        
        guide_label = QLabel("텍스트를 붙여넣거나 엑셀 파일을 가져오세요.")
        guide_label.setStyleSheet("color: #64748b; font-size: 12px;")
        
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("예시 입력:\n1 홍길동 200,000 친척모임\n5 최동료 100,000 A보건지소\n11 김가족,김친지 300,000 C이모\n25 김성도(조성도) 50,000 OO교회")
        
        btn_parse = QPushButton("⚡ 1초 자동 취합 및 파싱")
        btn_parse.clicked.connect(self.handle_parse_text)

        btn_sample = QPushButton("🎯 100% 가명화 샘플 데이터 불러오기")
        btn_sample.setObjectName("btnSample")
        btn_sample.clicked.connect(self.handle_load_sample)
        
        btn_excel_import = QPushButton("📂 엑셀 파일(.xlsx) 불러오기")
        btn_excel_import.setStyleSheet("background-color: #475569;")
        btn_excel_import.clicked.connect(self.handle_excel_import)

        input_inner_layout.addWidget(guide_label)
        input_inner_layout.addWidget(self.txt_input)
        input_inner_layout.addWidget(btn_parse)
        input_inner_layout.addWidget(btn_sample)
        input_inner_layout.addWidget(btn_excel_import)

        left_layout.addWidget(input_group)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        table_group = QGroupBox("📜 스마트 취합 목록 & 1초 감사 메시지 복사")
        table_inner_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "NO", "성명(하객)", "축의금액", "소속/관계", "참석/비고", "1초 감사 메시지 복사", "발송상태", "원문"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)

        table_inner_layout.addWidget(self.table)
        
        btn_export = QPushButton("📥 완성된 취합 리스트 엑셀로 저장 (xlsx)")
        btn_export.setObjectName("btnExcel")
        btn_export.clicked.connect(self.handle_export_excel)
        table_inner_layout.addWidget(btn_export)

        right_layout.addWidget(table_group)
        splitter.addWidget(right_widget)

        splitter.setSizes([450, 850])
        main_layout.addWidget(splitter)

    def handle_load_sample(self):
        self.txt_input.setPlainText(SAMPLE_RAW_TEXT)
        self.handle_parse_text()
        QMessageBox.information(self, "샘플 완료", "가명화 처리된 샘플 데이터 27건이 취합되었습니다.")

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

            self.table.setItem(row, 0, QTableWidgetItem(str(guest['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(guest['name']))
            
            amt_str = f"{guest['amount']:,} 원"
            self.table.setItem(row, 2, QTableWidgetItem(amt_str))
            
            belong_rel = f"{guest.get('belong', '')} ({guest['relation']})" if guest.get('belong') else guest['relation']
            self.table.setItem(row, 3, QTableWidgetItem(belong_rel))
            
            note_att = f"{guest['attended']} {guest.get('note', '')}".strip()
            self.table.setItem(row, 4, QTableWidgetItem(note_att))

            msg = MessageGenerator.generate(guest)
            btn_copy = QPushButton("📋 인사말 복사")
            btn_copy.setObjectName("btnCopy")
            btn_copy.clicked.connect(lambda _, m=msg, g=guest: self.copy_to_clipboard(m, g))
            self.table.setCellWidget(row, 5, btn_copy)

            chk_sent = QCheckBox("완료")
            chk_sent.setChecked(guest.get('sent_thanks', False))
            chk_sent.stateChanged.connect(lambda state, g=guest: self.toggle_sent(state, g))
            
            chk_container = QWidget()
            chk_layout = QHBoxLayout(chk_container)
            chk_layout.addWidget(chk_sent)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 6, chk_container)

            self.table.setItem(row, 7, QTableWidgetItem(guest.get('raw', '')))

    def copy_to_clipboard(self, msg: str, guest: dict):
        clipboard = QApplication.clipboard()
        clipboard.setText(msg)
        guest['sent_thanks'] = True
        self.render_table()
        QMessageBox.information(self, "복사 완료", f"[{guest['name']}] 하객 감사 메시지가 클립보드에 복사되었습니다!\n\n카톡/문자 입력창에 바로 Ctrl+V 하세요.")

    def toggle_sent(self, state, guest):
        guest['sent_thanks'] = (state == 2)

    def update_summary(self):
        total_amt = sum(g['amount'] for g in self.guest_data)
        total_guests = len(self.guest_data)
        
        adult_cost = self.spin_adult_meal.value()
        child_cost = self.spin_child_meal.value()
        
        total_meal_fee = (total_guests * adult_cost)
        net_profit = total_amt - total_meal_fee

        self.lbl_total_amount.setText(f"총 축의금: {total_amt:,} 원")
        self.lbl_guest_count.setText(f"총 하객: {total_guests} 명")
        self.lbl_net_profit.setText(f"순 정산금: {net_profit:,} 원")

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
                QMessageBox.information(self, "성공", "엑셀 저장 완료!")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"엑셀 저장 실패: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = ChuguiMasterUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
