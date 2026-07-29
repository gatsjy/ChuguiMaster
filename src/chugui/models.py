"""도메인 모델.

UI / 저장 / 파싱 계층이 공유하는 단 하나의 데이터 표현이다.
과거 버전은 하객을 raw ``dict``로 다뤄서 파싱 경로마다 키 스키마가 달랐고,
누락된 키 하나가 곧바로 렌더링 중 ``KeyError``로 이어졌다.
여기서는 dataclass + 관용적 역직렬화로 그 계열의 버그를 구조적으로 차단한다.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# 세션/설정 파일에 기록되는 스키마 버전. 하위 호환 로딩의 기준점.
SCHEMA_VERSION = 2


class Relation(str, Enum):
    """하객 관계 분류."""

    FAMILY = "친척/가족"
    WORK = "직장/기관"
    FAITH = "종교/모임"
    SCHOOL = "학교/동창"
    OTHER = "지인/기타"

    @classmethod
    def coerce(cls, value: Any) -> Relation:
        """어떤 입력이 와도 유효한 Relation을 돌려준다."""
        if isinstance(value, cls):
            return value
        text = str(value or "").strip()
        for member in cls:
            if text == member.value:
                return member
        # 구버전 세션 파일 및 사용자 오타 대응
        for member in cls:
            if text and (text in member.value or member.value in text):
                return member
        return cls.OTHER

    @classmethod
    def values(cls) -> list[str]:
        return [m.value for m in cls]


class Attendance(str, Enum):
    """참석 여부."""

    PRESENT = "참석"
    ABSENT = "불참(송금)"

    @classmethod
    def coerce(cls, value: Any) -> Attendance:
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            return cls.PRESENT if value else cls.ABSENT
        text = str(value or "").strip()
        if not text:
            return cls.PRESENT
        if "불참" in text or "미참" in text or "송금" in text:
            return cls.ABSENT
        return cls.PRESENT


class Payment(str, Enum):
    """수령 경로."""

    CASH = "현금"
    TRANSFER = "계좌이체"

    @classmethod
    def coerce(cls, value: Any) -> Payment:
        if isinstance(value, cls):
            return value
        text = str(value or "").strip()
        return cls.TRANSFER if ("계좌" in text or "이체" in text or "송금" in text) else cls.CASH


class Source(str, Enum):
    """데이터 출처. 현금 명단과 계좌이체 내역을 병합할 때 근거가 된다."""

    TEXT = "텍스트"
    EXCEL = "엑셀"
    BANK = "계좌내역"
    MANUAL = "직접입력"

    @classmethod
    def coerce(cls, value: Any) -> Source:
        if isinstance(value, cls):
            return value
        text = str(value or "").strip()
        for member in cls:
            if text == member.value:
                return member
        return cls.TEXT


# 사용자에게 "확인이 필요하다"고 알리는 경고 코드.
# 파서는 절대 조용히 추측하지 않는다 - 확신이 없으면 경고를 남긴다.
WARN_NO_AMOUNT = "금액을 찾지 못했습니다"
WARN_NO_NAME = "이름을 자동 인식하지 못했습니다"
WARN_AMBIGUOUS_AMOUNT = "금액 후보가 여러 개입니다"
WARN_DUPLICATE = "동일 이름이 이미 있습니다"


@dataclass
class Guest:
    """하객 한 명(또는 함께 낸 한 팀)의 축의 기록."""

    name: str = ""
    amount: int = 0
    relation: Relation = Relation.OTHER
    attendance: Attendance = Attendance.PRESENT
    payment: Payment = Payment.CASH
    adult_tickets: int = 0
    child_tickets: int = 0
    belong: str = ""
    note: str = ""
    aliases: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    sent_thanks: bool = False
    raw: str = ""
    source: Source = Source.TEXT
    warnings: list[str] = field(default_factory=list)
    guest_id: int = 0

    # ------------------------------------------------------------------ 파생값

    @property
    def is_present(self) -> bool:
        return self.attendance is Attendance.PRESENT

    @property
    def needs_review(self) -> bool:
        return bool(self.warnings)

    @property
    def head_count(self) -> int:
        """이 레코드가 대표하는 사람 수(부부 = 2)."""
        return max(1, len(self.names))

    @property
    def ticket_summary(self) -> str:
        if not self.adult_tickets and not self.child_tickets:
            return "-"
        parts = []
        if self.adult_tickets:
            parts.append(f"대{self.adult_tickets}")
        if self.child_tickets:
            parts.append(f"소{self.child_tickets}")
        return "·".join(parts)

    def add_warning(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def clear_warning(self, message: str) -> None:
        if message in self.warnings:
            self.warnings.remove(message)

    # -------------------------------------------------------------- 직렬화

    def to_dict(self) -> dict[str, Any]:
        return {
            "guest_id": self.guest_id,
            "name": self.name,
            "names": list(self.names),
            "aliases": list(self.aliases),
            "amount": self.amount,
            "relation": self.relation.value,
            "attendance": self.attendance.value,
            "payment": self.payment.value,
            "adult_tickets": self.adult_tickets,
            "child_tickets": self.child_tickets,
            "belong": self.belong,
            "note": self.note,
            "sent_thanks": self.sent_thanks,
            "raw": self.raw,
            "source": self.source.value,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Any) -> Guest:
        """어떤 형태의 dict가 와도 유효한 Guest를 만든다.

        구버전(v1) 세션 파일의 ``attended`` / ``sent_thanks`` 키와
        키가 통째로 빠진 부분 레코드까지 모두 흡수한다.
        """
        if not isinstance(data, dict):
            return cls(name="", warnings=[WARN_NO_NAME])

        def _int(key: str, default: int = 0) -> int:
            try:
                return int(data.get(key, default) or default)
            except (TypeError, ValueError):
                return default

        name = str(data.get("name") or "").strip()
        names = [str(n).strip() for n in (data.get("names") or []) if str(n).strip()]
        if not names and name:
            names = [n.strip() for n in name.replace("&", ",").split(",") if n.strip()]

        # v1 호환: attendance 대신 attended 키를 썼다.
        attendance_raw = data.get("attendance", data.get("attended", Attendance.PRESENT.value))

        guest = cls(
            guest_id=_int("guest_id", _int("id", 0)),
            name=name,
            names=names,
            aliases=[str(a) for a in (data.get("aliases") or [])],
            amount=_int("amount"),
            relation=Relation.coerce(data.get("relation")),
            attendance=Attendance.coerce(attendance_raw),
            payment=Payment.coerce(data.get("payment")),
            adult_tickets=_int("adult_tickets"),
            child_tickets=_int("child_tickets"),
            belong=str(data.get("belong") or ""),
            note=str(data.get("note") or ""),
            sent_thanks=bool(data.get("sent_thanks", False)),
            raw=str(data.get("raw") or ""),
            source=Source.coerce(data.get("source")),
            warnings=[str(w) for w in (data.get("warnings") or [])],
        )
        if not guest.name:
            guest.name = "이름 미상"
            guest.add_warning(WARN_NO_NAME)
        return guest


def renumber(guests: Iterable[Guest]) -> list[Guest]:
    """표시용 순번을 1부터 다시 매긴다."""
    result = list(guests)
    for index, guest in enumerate(result, start=1):
        guest.guest_id = index
    return result
