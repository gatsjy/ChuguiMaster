"""은행 거래내역 읽기. 나간 돈이 축의금으로 잡히거나 은행 용어가 이름이 되면 안 된다."""

from __future__ import annotations

import pytest

from chugui.models import WARN_NO_NAME, Attendance, Payment, Source
from chugui.parsing.excel_parser import parse_rows, read_spreadsheet
from chugui.parsing.statement import find_statement_header, parse_statement_rows
from chugui.services.settlement import settle

# 은행마다 열 구성이 다르다. 실제 양식을 흉내 낸 네 가지.
SEPARATE_COLUMNS = [
    ["조회기간", "2025.10.01~2025.10.05"],
    ["거래일시", "구분", "적요", "기재내용", "출금액", "입금액", "잔액"],
    ["2025-10-03 10:00", "입금", "타행이체", "홍길동", "0", "100000", "1100000"],
    ["2025-10-03 11:00", "출금", "카드", "예식장", "500000", "0", "600000"],
    ["2025-10-03 12:00", "입금", "", "김철수", "", "50000", "650000"],
    ["합계", "", "", "", "500000", "150000", ""],
]
UNITS_IN_HEADER = [
    ["거래일자", "거래시간", "보낸분/받는분", "입금액(원)", "출금액(원)", "내 통장 표시", "잔액(원)"],
    ["2025.10.03", "10:00", "홍길동", "100,000", "", "홍길동", "1,100,000"],
    ["2025.10.03", "10:01", "예식장", "", "500,000", "예식장", "600,000"],
]
SIGNED_AMOUNT = [
    ["거래 일시", "적요", "거래 유형", "거래 금액", "거래 후 잔액", "메모"],
    ["2025.10.03 10:00", "홍길동", "입금", "+100,000", "1,100,000", ""],
    ["2025.10.03 11:00", "예식장", "출금", "-500,000", "600,000", ""],
]
TELLER_WORDS = [
    ["거래일자", "적요", "맡기신금액", "찾으신금액", "거래후잔액", "내용"],
    ["2025.10.03", "전자금융", "100,000", "0", "1,100,000", "홍길동"],
    ["2025.10.03", "체크카드", "0", "500,000", "600,000", "예식장"],
]


@pytest.mark.parametrize(
    "rows",
    [SEPARATE_COLUMNS, UNITS_IN_HEADER, SIGNED_AMOUNT, TELLER_WORDS],
    ids=["separate", "units", "signed", "teller"],
)
class TestEveryFormat:
    def test_only_deposits_become_guests(self, rows):
        names = [g.name for g in parse_rows(rows)]
        assert "예식장" not in names
        assert "홍길동" in names

    def test_sender_is_the_person_not_the_bank_word(self, rows):
        assert parse_rows(rows)[0].name == "홍길동"

    def test_outflow_is_counted_for_the_user(self, rows):
        assert parse_statement_rows(rows).skipped_outflows == 1

    def test_outflow_never_adds_to_the_total(self, rows):
        total = settle(parse_rows(rows)).total_amount
        assert total in (100_000, 150_000)

    def test_rows_are_transfers_without_meal_tickets(self, rows):
        guest = parse_rows(rows)[0]
        assert guest.payment is Payment.TRANSFER
        assert guest.source is Source.BANK
        assert guest.attendance is Attendance.ABSENT
        assert (guest.adult_tickets, guest.child_tickets) == (0, 0)


class TestMoneyIsNeverDropped:
    def test_deposit_without_sender_stays_for_review(self):
        rows = [["거래일시", "입금액", "잔액", "기재내용"], ["2025-10-03", "70,000", "770,000", ""]]
        guest = parse_rows(rows)[0]
        assert guest.amount == 70_000
        assert guest.name == "이름 미상"
        assert WARN_NO_NAME in guest.warnings

    def test_bank_word_as_sender_is_flagged(self):
        rows = [["거래일시", "적요", "입금액", "잔액"], ["2025-10-03", "결산이자", "1,234", "1,001,234"]]
        guest = parse_rows(rows)[0]
        assert guest.amount == 1_234
        assert WARN_NO_NAME in guest.warnings

    def test_memo_saying_attended_keeps_tickets(self):
        rows = [["거래일시", "보낸분", "입금액", "잔액", "메모"], ["2025-10-03", "홍길동", "100000", "1", "참석"]]
        guest = parse_rows(rows)[0]
        assert guest.attendance is Attendance.PRESENT
        assert guest.adult_tickets == 1


class TestDetection:
    def test_handmade_list_is_not_a_statement(self):
        assert find_statement_header([["성명", "금액", "소속"], ["홍길동", "100000", "이모"]]) is None

    def test_list_with_a_deposit_column_is_not_a_statement(self):
        assert find_statement_header([["이름", "입금액", "참석"], ["홍길동", "100000", "참석"]]) is None

    def test_export_of_this_app_is_not_a_statement(self, tmp_path):
        from chugui.parsing.text_parser import parse_text
        from chugui.services.exporter import export_to_excel

        guests = parse_text("홍길동 10만원")
        path = tmp_path / "명단.xlsx"
        export_to_excel(path, guests, settle(guests))
        assert read_spreadsheet(path).is_export

    def test_detected_from_columns_not_file_name(self, tmp_path):
        """파일 이름에 '내역' 이 없으면 계좌이체가 현금으로 집계됐다."""
        path = tmp_path / "신한은행.csv"
        path.write_text("거래일시,보낸분,입금액,잔액\n2025-10-03,홍길동,100000,1100000\n", encoding="utf-8-sig")
        result = read_spreadsheet(path)
        assert result.guests[0].payment is Payment.TRANSFER


def test_window_reports_skipped_outflows(qt_app, tmp_path):
    from PySide6.QtTest import QTest

    from chugui.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    QTest.qWait(200)
    try:
        path = tmp_path / "신한은행.csv"
        path.write_text(
            "거래일시,보낸분,입금액,출금액,잔액\n2025-10-03,홍길동,100000,,1100000\n2025-10-03,예식장,,500000,600000\n",
            encoding="utf-8-sig",
        )
        window._load_file(str(path))
        assert [g.name for g in window._model.guests] == ["홍길동"]
        assert "출금 1건 제외" in window._toast._label.text()
    finally:
        window.close()
