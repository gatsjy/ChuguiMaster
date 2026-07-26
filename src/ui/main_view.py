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

# 상위 디렉토리 모듈 임포트 가능하도록 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smart_parser import SmartParser
from message_generator import MessageGenerator

class ChuguiMasterUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("💍 ChuguiMaster - 스마트 축의금 자동 취합 & 감사 메시지 생성기")
        self.resize(1280, 800)
        self.guest_data = []
        
        # 메인 스타일시트 설정 (모던 테마)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f4f6f9;
            }
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
                color: #2c3e50;
            }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton#btnCopy {
                background-color: #10b981;
                padding: 4px 8px;
            }
            QPushButton#btnCopy:hover {
                background-color: #059669;
            }
            QPushButton#btnExcel {
                background-color: #059669;
            }
            QPushButton#btnExcel:hover {
                background-color: #047857;
            }
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e5e7eb;
                border: 1px solid #d1d5db;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                font-weight: bold;
                color: #374151;
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
        summary_group = QGroupBox("📊 1초 실시간 축의금 결산 카운터")
        summary_layout = QHBoxLayout(summary_group)

        self.lbl_total_amount = QLabel("총 축의금: 0 원")
        self.lbl_total_amount.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e3a8a;")
        
        self.lbl_guest_count = QLabel("총 하객: 0 명")
        self.lbl_guest_count.setStyleSheet("font-size: 15px; font-weight: bold; color: #374151;")

        # 식대 입력
        meal_layout = QHBoxLayout()
        meal_lbl = QLabel("1인당 식대:")
        self.spin_meal_cost = QSpinBox()
        self.spin_meal_cost.setRange(0, 500000)
        self.spin_meal_cost.setSingleStep(5000)
        self.spin_meal_cost.setValue(55000)
        self.spin_meal_cost.setSuffix(" 원")
        self.spin_meal_cost.valueChanged.connect(self.update_summary)
        meal_layout.addWidget(meal_lbl)
        meal_layout.addWidget(self.spin_meal_cost)

        self.lbl_net_profit = QLabel("순 정산금: 0 원")
        self.lbl_net_profit.setStyleSheet("font-size: 16px; font-weight: bold; color: #059669;")

        summary_layout.addWidget(self.lbl_total_amount)
        summary_layout.addWidget(self.lbl_guest_count)
        summary_layout.addLayout(meal_layout)
        summary_layout.addWidget(self.lbl_net_profit)
        
        main_layout.addWidget(summary_group)

        # 2. 메인 스플리터 (좌: 붙여넣기 창 / 우: 취합 표)
        splitter = QSplitter(Qt.Horizontal)

        # 좌측 입력 박스
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        input_group = QGroupBox("📋 자유 텍스트 복사-붙여넣기 창")
        input_inner_layout = QVBoxLayout(input_group)
        
        guide_label = QLabel("카톡/메모장 글을 복붙하세요 (예: 홍길동 10만원 직장 식권2)")
        guide_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        
        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("여기에 축의금 리스트를 자유롭게 붙여넣으세요...\n\n예시:\n홍길동 10만원 직장 식권2\n김철수 50,000 대학\n이영희 10만 친척 불참")
        
        btn_parse = QPushButton("⚡ 1초 자동 취합 및 파싱")
        btn_parse.clicked.connect(self.handle_parse_text)
        
        btn_excel_import = QPushButton("📂 엑셀/CSV 파일 불러오기")
        btn_excel_import.setStyleSheet("background-color: #6b7280;")
        btn_excel_import.clicked.connect(self.handle_excel_import)

        input_inner_layout.addWidget(guide_label)
        input_inner_layout.addWidget(self.txt_input)
        input_inner_layout.addWidget(btn_parse)
        input_inner_layout.addWidget(btn_excel_import)

        left_layout.addWidget(input_group)
        splitter.addWidget(left_widget)

        # 우측 결과 테이블 및 감사 메시지
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        table_group = QGroupBox("📜 스마트 취합 목록 & 1초 감사 인사 복사")
        table_inner_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "NO", "이름", "금액", "관계", "참석/식권", "1초 감사 메시지 복사", "발송상태", "원문"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)

        table_inner_layout.addWidget(self.table)
        
        # 하단 엑셀 내보내기 버튼
        btn_export = QPushButton("📥 취합 결과 엑셀로 저장 (xlsx)")
        btn_export.setObjectName("btnExcel")
        btn_export.clicked.connect(self.handle_export_excel)
        table_inner_layout.addWidget(btn_export)

        right_layout.addWidget(table_group)
        splitter.addWidget(right_widget)

        # 비율 설정 (4:6)
        splitter.setSizes([450, 750])
        main_layout.addWidget(splitter)

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
                QMessageBox.information(self, "성공", f"{len(self.guest_data)}건의 데이터를 가져왔습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"엑셀 읽기 실패: {str(e)}")

    def render_table(self):
        self.table.setRowCount(0)
        for idx, guest in enumerate(self.guest_data):
            row = self.table.rowCount()
            self.table.insertRow(row)

            # NO
            self.table.setItem(row, 0, QTableWidgetItem(str(guest['id'])))
            # 이름
            self.table.setItem(row, 1, QTableWidgetItem(guest['name']))
            # 금액
            amt_str = f"{guest['amount']:,} 원"
            self.table.setItem(row, 2, QTableWidgetItem(amt_str))
            # 관계
            self.table.setItem(row, 3, QTableWidgetItem(guest['relation']))
            # 참석/식권
            att_info = f"{guest['attended']} ({guest['tickets']}장)"
            self.table.setItem(row, 4, QTableWidgetItem(att_info))

            # 감사 메시지 생성 및 1초 복사 버튼
            msg = MessageGenerator.generate(guest)
            btn_copy = QPushButton("📋 인사말 복사")
            btn_copy.setObjectName("btnCopy")
            btn_copy.clicked.connect(lambda _, m=msg, g=guest: self.copy_to_clipboard(m, g))
            self.table.setCellWidget(row, 5, btn_copy)

            # 발송 상태 체크박스
            chk_sent = QCheckBox("완료")
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
        QMessageBox.information(self, "복사 완료", f"[{guest['name']}] 하객 감사 메시지가 클립보드에 복사되었습니다!\n\n카톡/문자 창에 바로 Ctrl+V 하세요.")

    def toggle_sent(self, state, guest):
        guest['sent_thanks'] = (state == 2) # 2: Checked

    def update_summary(self):
        total_amt = sum(g['amount'] for g in self.guest_data)
        total_guests = len(self.guest_data)
        total_tickets = sum(g['tickets'] for g in self.guest_data)
        
        meal_cost = self.spin_meal_cost.value()
        total_meal_fee = total_tickets * meal_cost
        net_profit = total_amt - total_meal_fee

        self.lbl_total_amount.setText(f"총 축의금: {total_amt:,} 원")
        self.lbl_guest_count.setText(f"총 하객: {total_guests} 명 (식권: {total_tickets}장)")
        self.lbl_net_profit.setText(f"순 정산금: {net_profit:,} 원")

    def handle_export_excel(self):
        if not self.guest_data:
            QMessageBox.warning(self, "경고", "내보낼 데이터가 없습니다.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "엑셀로 저장", "축의금_취합리스트.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            try:
                export_list = []
                for g in self.guest_data:
                    export_list.append({
                        '번호': g['id'],
                        '성함': g['name'],
                        '축의금액': g['amount'],
                        '관계': g['relation'],
                        '참석여부': g['attended'],
                        '식권수량': g['tickets'],
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
