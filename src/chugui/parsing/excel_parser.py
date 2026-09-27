"""스프레드시트(.xlsx) / CSV → Guest 변환.

pandas를 쓰지 않는다. 이 프로그램이 pandas에서 쓰던 기능은 ``read_excel`` /
``to_excel`` 두 개뿐인데, 그 대가로 PyInstaller 산출물이 두 배가 되고
콜드 스타트가 몇 초씩 늘어난다. openpyxl + 표준 ``csv`` 로 충분하다.

구버전 대비 실질적인 개선 두 가지:

* **헤더 행 자동 탐색** - 은행/토스/카뱅 거래내역 엑셀은 상단에 계좌·기간
  안내가 5~10줄 붙어 나온다. 구버전은 그 첫 줄을 헤더로 잡아 통째로 실패했다.
* **CSV 실제 지원** - 구버전은 파일 다이얼로그와 드래그&드롭에서 ``*.csv`` 를
  받아놓고 ``pd.read_excel`` 만 호출해 ``ValueError`` 로 죽었다.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chugui.models import (
    WARN_NO_AMOUNT,
    WARN_NO_NAME,
    Attendance,
    Guest,
    Payment,
    Relation,
    Source,
    renumber,
)
from chugui.parsing.amount import parse_amount
from chugui.parsing.names import format_display_name, split_names, strip_person_names
from chugui.parsing.relations import guess_relation

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES: tuple[str, ...] = (".xlsx", ".xlsm", ".csv")

# 헤더 후보 키워드. 은행 거래내역 컬럼명까지 포함한다.
_NAME_KEYS = ("성명", "이름", "입금자", "보낸분", "보내는분", "거래자", "성함", "고객명", "적요")
_AMOUNT_KEYS = ("금액", "축의금", "입금액", "입금", "받은금액", "거래금액", "원화금액")
_BELONG_KEYS = ("소속", "관계", "그룹", "분류", "구분")
_NOTE_KEYS = ("비고", "특이사항", "메모", "내용", "기재내용", "적요")
_TICKET_ADULT_KEYS = ("식권", "대인", "성인")
_TICKET_CHILD_KEYS = ("소인", "어린이", "아동")

# 헤더 탐색 시 스캔할 최대 행 수.
_MAX_HEADER_SCAN = 20

#: 내보내기 명단 시트의 이름과 열 제목. 내보내기와 다시 불러오기가 함께 쓴다.
EXPORT_SHEET = "축의금 명단"
EXPORT_HEADERS: tuple[str, ...] = (
    "순번", "성명", "축의금액", "관계분류", "소속", "참석여부", "수령경로",
    "대인식권", "소인식권", "비고", "확인필요", "감사메시지", "발송완료",
)
#: 이 열들이 대부분 있으면 내보낸 명단으로 본다. 은행·지인 엑셀에는 없는 조합이다.
_EXPORT_SIGNATURE: tuple[str, ...] = ("축의금액", "관계분류", "참석여부", "수령경로", "발송완료")
_SENT_TRUE = frozenset({"완료", "발송", "발송완료", "o", "y", "yes", "true", "1", "✓", "v", "예"})


class ExcelParseError(RuntimeError):
    """스프레드시트를 해석할 수 없을 때."""


def _norm(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _match_column(headers: Sequence[str], keys: Sequence[str]) -> int | None:
    """키워드에 가장 잘 맞는 컬럼 인덱스. 긴 키워드가 우선."""
    best_index: int | None = None
    best_length = 0
    for index, header in enumerate(headers):
        for key in keys:
            if key in header and len(key) > best_length:
                best_index, best_length = index, len(key)
    return best_index


def _score_header_row(row: Sequence[str]) -> int:
    """이 행이 헤더일 가능성 점수."""
    filled = [cell for cell in row if cell]
    if len(filled) < 2:
        return 0
    score = 0
    if _match_column(row, _NAME_KEYS) is not None:
        score += 2
    if _match_column(row, _AMOUNT_KEYS) is not None:
        score += 2
    if _match_column(row, _BELONG_KEYS) is not None:
        score += 1
    if _match_column(row, _NOTE_KEYS) is not None:
        score += 1
    return score


def _find_header_row(rows: Sequence[Sequence[str]]) -> int:
    """상단 안내문을 건너뛰고 실제 헤더 행 인덱스를 찾는다."""
    best_index, best_score = 0, 0
    for index, row in enumerate(rows[:_MAX_HEADER_SCAN]):
        score = _score_header_row(row)
        if score > best_score:
            best_index, best_score = index, score
    if best_score < 2:
        logger.warning("헤더 행을 확신할 수 없어 첫 행을 헤더로 사용합니다.")
        return 0
    return best_index


# --------------------------------------------------------------------- 로더


def _read_csv_rows(path: Path) -> list[list[str]]:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                try:
                    dialect: Any = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                except csv.Error:
                    dialect = csv.excel
                return [[_norm(cell) for cell in row] for row in csv.reader(handle, dialect)]
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc
            continue
    raise ExcelParseError(f"CSV 인코딩을 판별하지 못했습니다: {last_error}")


def _read_xlsx_rows(path: Path) -> list[list[str]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - 배포본에는 항상 포함
        raise ExcelParseError("openpyxl이 설치되어 있지 않습니다.") from exc

    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise ExcelParseError(f"엑셀 파일을 열 수 없습니다: {exc}") from exc

    try:
        # 내보낸 파일을 '정산 요약' 시트가 선택된 채로 저장했어도 명단 시트를 읽는다.
        sheet = workbook[EXPORT_SHEET] if EXPORT_SHEET in workbook.sheetnames else workbook.active
        if sheet is None:
            raise ExcelParseError("시트를 찾을 수 없습니다.")
        return [[_norm(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _load_rows(path: Path) -> list[list[str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv_rows(path)
    if suffix in (".xlsx", ".xlsm"):
        return _read_xlsx_rows(path)
    if suffix == ".xls":
        raise ExcelParseError(
            "구형 .xls 형식은 지원하지 않습니다. 엑셀에서 .xlsx로 저장한 뒤 다시 시도해 주세요."
        )
    raise ExcelParseError(f"지원하지 않는 형식입니다: {suffix or '(확장자 없음)'}")


# -------------------------------------------------------------------- 파서


def _cell(row: Sequence[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index]


def _int_cell(row: Sequence[str], index: int | None) -> int:
    text = _cell(row, index)
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def parse_rows(rows: Sequence[Sequence[str]], source: Source = Source.EXCEL) -> list[Guest]:
    """이미 읽어들인 행 목록을 Guest로 변환한다(테스트 진입점)."""
    if not rows:
        return []

    header_index = _find_header_row(rows)
    headers = list(rows[header_index])
    body: Iterable[Sequence[str]] = rows[header_index + 1 :]

    name_col = _match_column(headers, _NAME_KEYS)
    amount_col = _match_column(headers, _AMOUNT_KEYS)
    belong_col = _match_column(headers, _BELONG_KEYS)
    note_col = _match_column(headers, _NOTE_KEYS)
    adult_col = _match_column(headers, _TICKET_ADULT_KEYS)
    child_col = _match_column(headers, _TICKET_CHILD_KEYS)

    if name_col is None:
        name_col = 0
    if name_col == note_col:  # '적요'가 이름과 비고 양쪽에 걸린 경우
        note_col = None

    guests: list[Guest] = []
    for offset, row in enumerate(body, start=1):
        if not any(cell for cell in row):
            continue

        raw_name = _cell(row, name_col)
        if not raw_name or raw_name in ("nan", "None"):
            continue
        # 은행 엑셀 하단의 합계/소계 행 제거
        if any(marker in raw_name for marker in ("합계", "총계", "소계", "TOTAL", "Total")):
            continue

        belong = _cell(row, belong_col)
        note = _cell(row, note_col)

        names = split_names(raw_name) or [raw_name]
        attendance = Attendance.ABSENT if ("불참" in note or "미참" in note) else Attendance.PRESENT
        amount = parse_amount(_cell(row, amount_col)) if amount_col is not None else 0

        adult_tickets = _int_cell(row, adult_col)
        child_tickets = _int_cell(row, child_col)
        if adult_col is None:
            adult_tickets = len(names) if attendance is Attendance.PRESENT else 0
        elif attendance is Attendance.ABSENT:
            adult_tickets = 0

        guest = Guest(
            name=format_display_name(names),
            names=names,
            amount=amount,
            relation=guess_relation(belong, note, strip_person_names(raw_name, names)),
            attendance=attendance,
            payment=Payment.coerce(note) if source is Source.EXCEL else Payment.TRANSFER,
            adult_tickets=adult_tickets,
            child_tickets=child_tickets,
            belong=belong,
            note=note,
            raw=" ".join(part for part in (raw_name, str(amount), belong, note) if part).strip(),
            source=source,
            guest_id=offset,
        )
        if amount <= 0:
            guest.add_warning(WARN_NO_AMOUNT)
        if not raw_name.strip():
            guest.add_warning(WARN_NO_NAME)
        guests.append(guest)

    return renumber(guests)


# ------------------------------------------------ 내보낸 파일 다시 불러오기


def _find_export_header(rows: Sequence[Sequence[str]]) -> int | None:
    """이 프로그램이 내보낸 명단이면 헤더 행 인덱스, 아니면 ``None``.

    사용자가 열 순서를 바꾸거나 몇 열을 지워도 알아보도록, 특징적인 열
    (축의금액 · 관계분류 · 참석여부 · 발송완료 등)이 대부분 남아 있으면 인정한다.
    """
    for index, row in enumerate(rows[:_MAX_HEADER_SCAN]):
        present = sum(1 for title in _EXPORT_SIGNATURE if title in row)
        if present >= len(_EXPORT_SIGNATURE) - 1 and "성명" in row:
            return index
    return None


def _count_cell(text: str) -> int:
    """식권 수 셀. 엑셀에서 고치면 ``2.0`` 처럼 올 수 있어 숫자로 해석한다."""
    try:
        return max(0, int(float(text.replace(",", ""))))
    except ValueError:
        return 0


def _sent_cell(text: str) -> bool:
    return text.strip().lower() in _SENT_TRUE


def parse_export_rows(rows: Sequence[Sequence[str]]) -> list[Guest] | None:
    """내보낸 명단을 **모든 열 그대로** 되살린다. 내보낸 형식이 아니면 ``None``.

    일반 파서로 읽으면 관계는 추정으로 바뀌고('관계분류' 열이 소속으로 들어갔다),
    참석여부 · 수령경로 · 발송완료가 사라졌다. 사용자가 엑셀에서 고친 값을
    그대로 믿는 것이 이 경로의 목적이므로 추정하지 않는다.
    """
    header_index = _find_export_header(rows)
    if header_index is None:
        return None
    headers = [cell.strip() for cell in rows[header_index]]
    column = {title: headers.index(title) for title in EXPORT_HEADERS if title in headers}

    def get(row: Sequence[str], title: str) -> str:
        return _cell(row, column.get(title))

    guests: list[Guest] = []
    for row in rows[header_index + 1 :]:
        raw_name = get(row, "성명").strip()
        if not raw_name:
            continue
        names = split_names(raw_name.replace("&", ",")) or [raw_name]
        amount = parse_amount(get(row, "축의금액"))
        guest = Guest(
            name=format_display_name(names),
            names=names,
            amount=amount,
            relation=Relation.coerce(get(row, "관계분류")),
            belong=get(row, "소속"),
            attendance=Attendance.coerce(get(row, "참석여부")),
            payment=Payment.coerce(get(row, "수령경로")),
            adult_tickets=_count_cell(get(row, "대인식권")),
            child_tickets=_count_cell(get(row, "소인식권")),
            note=get(row, "비고"),
            sent_thanks=_sent_cell(get(row, "발송완료")),
            raw=raw_name,
            source=Source.EXCEL,
            # 사용자가 '확인필요' 칸을 비웠으면 확인을 마친 것으로 본다.
            warnings=[w.strip() for w in get(row, "확인필요").split(" / ") if w.strip()],
        )
        if amount <= 0:
            guest.add_warning(WARN_NO_AMOUNT)
        guests.append(guest)
    return renumber(guests)


@dataclass(frozen=True)
class SpreadsheetResult:
    guests: list[Guest]
    #: 이 프로그램이 내보낸 명단인가. 그렇다면 병합이 아니라 교체해야 한다.
    is_export: bool


def read_spreadsheet(file_path: str | Path, source: Source = Source.EXCEL) -> SpreadsheetResult:
    """엑셀/CSV 파일을 읽는다. 내보낸 명단이면 모든 열을 그대로 되살린다."""
    path = Path(file_path)
    if not path.exists():
        raise ExcelParseError(f"파일을 찾을 수 없습니다: {path}")
    rows = _load_rows(path)
    exported = parse_export_rows(rows)
    if exported is not None:
        logger.info("내보낸 명단 다시 불러오기: %s (%d건)", path.name, len(exported))
        return SpreadsheetResult(exported, is_export=True)
    guests = parse_rows(rows, source=source)
    logger.info("스프레드시트 파싱 완료: %s (%d건)", path.name, len(guests))
    return SpreadsheetResult(guests, is_export=False)


def parse_spreadsheet(file_path: str | Path, source: Source = Source.EXCEL) -> list[Guest]:
    """엑셀/CSV 파일을 읽어 Guest 목록을 만든다."""
    return read_spreadsheet(file_path, source=source).guests
