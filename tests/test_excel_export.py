"""스프레드시트 입출력 테스트."""

from __future__ import annotations

import pytest

from chugui.models import Attendance, Guest, Relation, Source
from chugui.parsing.excel_parser import ExcelParseError, parse_rows, parse_spreadsheet
from chugui.services.exporter import export_to_excel
from chugui.services.settlement import settle

openpyxl = pytest.importorskip("openpyxl")


def write_xlsx(path, rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(list(row))
    workbook.save(path)
    return path


class TestHeaderDetection:
    def test_plain_header(self):
        guests = parse_rows([["성명", "금액", "소속"], ["홍길동", "100,000", "친척"]])
        assert guests[0].name == "홍길동"
        assert guests[0].amount == 100_000
        assert guests[0].relation is Relation.FAMILY

    def test_bank_statement_preamble_is_skipped(self):
        """v1은 상단 안내문 첫 줄을 헤더로 잡아 은행 엑셀을 통째로 실패했다."""
        rows = [
            ["○○은행 거래내역조회"],
            ["계좌번호", "110-123-456789"],
            ["조회기간", "2025-03-01 ~ 2025-03-31"],
            [],
            ["거래일시", "보낸분", "입금액", "기재내용"],
            ["2025-03-14 11:20", "홍길동", "100,000", "축의금"],
            ["2025-03-14 12:05", "김철수", "50,000", ""],
        ]
        guests = parse_rows(rows, source=Source.BANK)
        assert [g.name for g in guests] == ["홍길동", "김철수"]
        assert [g.amount for g in guests] == [100_000, 50_000]

    def test_total_rows_are_dropped(self):
        rows = [["성명", "금액"], ["홍길동", "100000"], ["합계", "100000"]]
        assert [g.name for g in parse_rows(rows)] == ["홍길동"]

    def test_empty_rows_ignored(self):
        rows = [["성명", "금액"], [], ["", ""], ["홍길동", "100000"]]
        assert len(parse_rows(rows)) == 1

    def test_empty_input(self):
        assert parse_rows([]) == []


class TestExcelFields:
    def test_tickets_and_attendance(self):
        rows = [
            ["성명", "금액", "소속", "비고", "식권", "소인"],
            ["홍길동", "300000", "이모", "", "2", "1"],
            ["박지성", "100000", "친구", "불참 계좌이체", "", ""],
        ]
        guests = parse_rows(rows)
        assert (guests[0].adult_tickets, guests[0].child_tickets) == (2, 1)
        assert guests[1].attendance is Attendance.ABSENT
        assert guests[1].adult_tickets == 0

    def test_multiple_names_in_one_cell(self):
        guests = parse_rows([["성명", "금액"], ["김가족,김친지", "300000"]])
        assert guests[0].names == ["김가족", "김친지"]
        assert guests[0].adult_tickets == 2

    def test_missing_amount_is_flagged(self):
        guests = parse_rows([["성명", "금액"], ["홍길동", ""]])
        assert guests[0].needs_review is True


class TestFileLoading:
    def test_xlsx_round_trip(self, tmp_path):
        path = write_xlsx(tmp_path / "list.xlsx", [["성명", "금액", "소속"], ["홍길동", 100000, "친척"]])
        guests = parse_spreadsheet(path)
        assert guests[0].amount == 100_000

    def test_csv_is_actually_supported(self, tmp_path):
        """v1은 파일 다이얼로그와 드래그&드롭에서 .csv를 받아놓고
        ``pd.read_excel`` 만 호출해 ValueError로 죽었다."""
        path = tmp_path / "list.csv"
        path.write_text("성명,금액,소속\n홍길동,100000,친척\n김철수,50000,대학동기\n", encoding="utf-8-sig")
        guests = parse_spreadsheet(path)
        assert [g.name for g in guests] == ["홍길동", "김철수"]

    def test_cp949_csv(self, tmp_path):
        path = tmp_path / "cp949.csv"
        path.write_bytes("성명,금액\n홍길동,100000\n".encode("cp949"))
        assert parse_spreadsheet(path)[0].name == "홍길동"

    def test_missing_file(self, tmp_path):
        with pytest.raises(ExcelParseError):
            parse_spreadsheet(tmp_path / "없음.xlsx")

    def test_xls_gives_actionable_message(self, tmp_path):
        path = tmp_path / "old.xls"
        path.write_bytes(b"not really xls")
        with pytest.raises(ExcelParseError, match="xlsx"):
            parse_spreadsheet(path)


class TestExport:
    def test_export_creates_both_sheets(self, tmp_path):
        guests = [
            Guest(name="홍길동", names=["홍길동"], amount=100_000, relation=Relation.FAMILY, adult_tickets=1),
            Guest(name="김철수", names=["김철수"], amount=50_000, relation=Relation.SCHOOL, adult_tickets=1),
        ]
        path = export_to_excel(tmp_path / "out.xlsx", guests, settle(guests, 40_000, 20_000))
        workbook = openpyxl.load_workbook(path)
        assert workbook.sheetnames == ["축의금 명단", "정산 요약"]

        sheet = workbook["축의금 명단"]
        assert sheet.cell(row=1, column=1).value == "순번"
        assert sheet.cell(row=2, column=2).value == "홍길동"
        assert sheet.cell(row=2, column=3).value == 100_000
        assert "홍길동" in str(sheet.cell(row=2, column=12).value)  # 감사메시지
        assert sheet.freeze_panes == "A2"

    def test_export_empty_list(self, tmp_path):
        path = export_to_excel(tmp_path / "empty.xlsx", [], settle([]))
        assert path.exists()
