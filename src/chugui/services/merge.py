"""현금 명단 + 계좌이체 내역 병합.

README가 내세우는 핵심 기능 2번("현금 + 계좌이체 원클릭 통합")은
구버전에 **구현되어 있지 않았다**. 텍스트 파싱과 엑셀 로딩 모두

    self.guest_data = SmartParser.parse_...(...)

로 기존 목록을 통째로 덮어썼다. 텍스트를 취합한 뒤 엑셀을 드롭하면
현금 내역이 전부 사라졌다. 이 모듈이 그 기능을 실제로 구현한다.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from chugui.models import WARN_DUPLICATE, Guest, Source, renumber

_NORMALIZE_RE = re.compile(r"[\s()（）\[\]·&＆,/]+")


def normalize_name(name: str) -> str:
    """비교용 이름 정규화. 공백/구분자/괄호를 제거한다."""
    return _NORMALIZE_RE.sub("", str(name or "")).lower()


def _identity_keys(guest: Guest) -> set[str]:
    """이 하객을 식별할 수 있는 모든 키(본명 + 구성원 + 별칭)."""
    keys = {normalize_name(guest.name)}
    keys.update(normalize_name(n) for n in guest.names)
    keys.update(normalize_name(a) for a in guest.aliases)
    return {key for key in keys if key}


@dataclass
class MergeResult:
    """병합 결과와 그 근거."""

    guests: list[Guest] = field(default_factory=list)
    added: int = 0
    duplicates: list[tuple[Guest, Guest]] = field(default_factory=list)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)

    @property
    def summary(self) -> str:
        if self.duplicate_count:
            return f"{self.added}건 추가 · 중복 의심 {self.duplicate_count}건"
        return f"{self.added}건 추가"


def merge_guests(
    existing: list[Guest],
    incoming: list[Guest],
    *,
    skip_exact_duplicates: bool = False,
) -> MergeResult:
    """``incoming`` 을 ``existing`` 뒤에 이어 붙인다.

    같은 사람이 양쪽에 있으면 **지우지 않고 경고를 남긴다**. 축의금은 돈이므로
    자동 병합으로 한 건을 삼키는 것보다 사용자에게 확인시키는 편이 안전하다.

    Args:
        skip_exact_duplicates: 이름과 금액이 모두 같으면 완전 중복으로 보고
            추가하지 않는다(같은 파일을 두 번 드롭한 경우).
    """
    merged = list(existing)
    index: dict[str, Guest] = {}
    for guest in merged:
        for key in _identity_keys(guest):
            index.setdefault(key, guest)

    result = MergeResult(guests=merged)

    for guest in incoming:
        keys = _identity_keys(guest)
        match = next((index[key] for key in keys if key in index), None)

        if match is not None:
            if skip_exact_duplicates and match.amount == guest.amount:
                continue
            guest.add_warning(WARN_DUPLICATE)
            match.add_warning(WARN_DUPLICATE)
            result.duplicates.append((match, guest))

        merged.append(guest)
        result.added += 1
        for key in keys:
            index.setdefault(key, guest)

    result.guests = renumber(merged)
    return result


@dataclass
class TextSyncResult:
    """입력창 내용을 표에 반영한 결과."""

    guests: list[Guest]
    added: int = 0
    removed: list[Guest] = field(default_factory=list)
    #: 표가 실제로 바뀌었는가. 아니면 화면을 건드리지 않는다.
    changed: bool = False


def sync_with_text(
    existing: list[Guest],
    parsed: list[Guest],
    previous_lines: list[str],
) -> TextSyncResult:
    """입력창을 고칠 때마다 표를 갱신한다. **표에서 한 일은 지키면서.**

    통째로 다시 파싱해 교체하면 표에서 고친 금액 · 발송 체크, 은행 파일에서 합친 줄,
    '기존 목록에 추가' 로 앞서 붙인 줄이 모두 사라진다. 그래서 줄 단위로 맞춘다.

    * 입력창에 그대로 있는 줄 → 기존 행을 그대로 쓴다(표에서 한 수정 유지).
    * 새로 쓰거나 고친 줄 → 새로 읽는다.
    * 직전 입력창에 있었는데 지금은 없는 줄 → 사용자가 지웠으므로 표에서도 뺀다.
    * 직전 입력창에도 없던 텍스트 줄(앞서 추가한 묶음) · 파일에서 온 줄 → 건드리지 않는다.

    순서는 [앞서 추가한 묶음] + [입력창 순서] + [파일에서 온 줄].
    """
    previous = Counter(line.strip() for line in previous_lines if line.strip())

    pool: dict[str, list[Guest]] = {}
    for guest in existing:
        if guest.source is Source.TEXT:
            pool.setdefault(guest.raw, []).append(guest)

    managed: list[Guest] = []
    added = 0
    for guest in parsed:
        bucket = pool.get(guest.raw)
        if bucket:
            managed.append(bucket.pop(0))
        else:
            managed.append(guest)
            added += 1

    leftover = {id(guest) for bucket in pool.values() for guest in bucket}
    removed: list[Guest] = []
    unmanaged: list[Guest] = []
    for guest in existing:
        if guest.source is not Source.TEXT or id(guest) not in leftover:
            continue
        if previous[guest.raw] > 0:
            previous[guest.raw] -= 1
            removed.append(guest)
        else:
            unmanaged.append(guest)

    others = [guest for guest in existing if guest.source is not Source.TEXT]
    ordered = unmanaged + managed + others
    changed = [id(guest) for guest in ordered] != [id(guest) for guest in existing]
    return TextSyncResult(renumber(ordered), added=added, removed=removed, changed=changed)
