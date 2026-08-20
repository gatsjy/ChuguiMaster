"""표 형태 붙여넣기 열 인식.

엑셀·구글시트·한글 표에서 복사하면 열이 **탭**으로 구분되어 붙는다.
카톡·메모장에서 정렬해 적은 명단은 **공백 여러 칸**으로 구분된다.

    유광호<TAB>200,000<TAB>토끼할머니

구버전 텍스트 파서는 줄 전체를 한 덩어리로만 봤다. 그래서 소속 열이
``belong`` 에 들어가지 못하고 ``raw`` 에만 남아, 엑셀로 내보내면
소속 열이 통째로 비었다. 이름도 줄 전체에서 골라서, 소속이 사람 이름보다
앞에 오는 형식에서는 엉뚱한 값을 집을 수 있었다.

여기서는 구분자가 뚜렷할 때만 열로 해석한다. 한 칸 공백으로 쓴
``홍길동 10만원 친척`` 은 자유 서식이므로 건드리지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from chugui.parsing.amount import extract_amount

_TAB_RE = re.compile(r"\t+")
#: 2칸 이상 공백(전각 공백 포함)만 열 구분자로 본다.
_WIDE_SPACE_RE = re.compile(r"[ 　]{2,}")

#: 열이 이 개수를 넘으면 표가 아니라 정렬된 산문으로 보고 포기한다.
_MAX_COLUMNS = 8


def split_columns(line: str) -> list[str] | None:
    """줄을 열로 나눈다. 뚜렷한 구분자가 없으면 ``None``."""
    text = str(line or "")
    if "\t" in text:
        fields = _TAB_RE.split(text)
    elif _WIDE_SPACE_RE.search(text):
        fields = _WIDE_SPACE_RE.split(text)
    else:
        return None

    fields = [field.strip() for field in fields]
    # 엑셀에서 복사하면 뒤쪽 빈 열이 딸려 오는 일이 흔하다.
    while fields and not fields[-1]:
        fields.pop()

    if not 2 <= len(fields) <= _MAX_COLUMNS:
        return None
    return fields


@dataclass(frozen=True)
class ColumnLayout:
    """한 줄의 열 배치."""

    fields: list[str]
    name_index: int
    amount_index: int | None
    belong: str

    @property
    def name_field(self) -> str:
        return self.fields[self.name_index] if 0 <= self.name_index < len(self.fields) else ""

    @property
    def amount_field(self) -> str:
        if self.amount_index is None:
            return ""
        return self.fields[self.amount_index]


def _digit_ratio(field: str) -> float:
    if not field:
        return 0.0
    return sum(character.isdigit() for character in field) / len(field)


def classify_columns(fields: list[str]) -> ColumnLayout:
    """어느 열이 이름이고 금액이고 소속인지 정한다.

    금액 열은 '숫자 비중이 가장 높으면서 실제로 금액으로 읽히는 열'이다.
    이름은 금액이 아닌 첫 열, 나머지는 전부 소속으로 합친다.
    """
    amount_index: int | None = None
    best_ratio = -1.0

    for index, field in enumerate(fields):
        if not any(character.isdigit() for character in field):
            continue
        amount, _ = extract_amount(field)
        if amount <= 0:
            continue
        ratio = _digit_ratio(field)
        if ratio > best_ratio:
            best_ratio, amount_index = ratio, index

    name_index = next(
        (index for index, field in enumerate(fields) if index != amount_index and field),
        0,
    )
    belong = " ".join(
        field
        for index, field in enumerate(fields)
        if field and index not in (name_index, amount_index)
    ).strip()

    return ColumnLayout(
        fields=fields, name_index=name_index, amount_index=amount_index, belong=belong
    )


def parse_columns(line: str) -> ColumnLayout | None:
    """열 구분자가 있으면 배치를 돌려준다."""
    fields = split_columns(line)
    return classify_columns(fields) if fields else None
