"""소속 → 관계 사용자 사전.

관계 추정은 `회사` `보건소` `교회` 같은 **일반명사** 키워드로 한다.
고유명사는 그 방법으로 영원히 못 맞힌다.

    현대모비스   23건  회사명. 걸릴 일반명사가 없다 → 지인/기타
    넥스트로     17건  회사명
    일구칠구     14건  부모님 모임 이름
    속셈말        3건  아버지 고향 마을 이름

앞의 둘은 사전을 늘리면 잡히는 척이라도 하지만, 뒤의 둘은 **세상 어떤 사전에도 없다.**
사용자만 아는 사실이기 때문이다. 그러니 키워드를 늘리는 쪽은 애초에 답이 아니다.

여기서는 사용자가 한 번 고치면 그 소속을 기억한다. 다음 명단부터 자동 적용된다.
학습 대상은 **소속**이지 이름이 아니다. 사람은 바뀌어도 소속은 다음 행사에도 나온다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from chugui.models import Guest, Relation

#: 소속을 비교할 때 무시할 것들. `넥스트로(주)` 와 `(주)넥스트로` 는 같은 곳이다.
_NOISE_RE = re.compile(r"[\s()（）\[\]{}·・,，/∙.\-_~!?？]+")
_CORP_SUFFIX_RE = re.compile(r"(주식회사|㈜|주\)|\(주|유한회사|재단법인|사단법인)")


def normalize_belong(belong: str) -> str:
    """소속 비교용 키. 표기 흔들림을 흡수한다."""
    text = _CORP_SUFFIX_RE.sub("", str(belong or ""))
    return _NOISE_RE.sub("", text).lower()


class RelationMap:
    """소속 키 → 관계. 저장소가 읽고 쓰는 평범한 dict 위의 얇은 껍데기."""

    def __init__(self, mapping: Mapping[str, str] | None = None) -> None:
        self._map: dict[str, Relation] = {}
        for key, value in (mapping or {}).items():
            normalized = normalize_belong(key)
            if normalized:
                self._map[normalized] = Relation.coerce(value)

    def __len__(self) -> int:
        return len(self._map)

    def __contains__(self, belong: str) -> bool:
        return normalize_belong(belong) in self._map

    def get(self, belong: str) -> Relation | None:
        return self._map.get(normalize_belong(belong))

    def learn(self, belong: str, relation: Relation) -> bool:
        """소속 하나를 기억한다. 실제로 바뀌었으면 ``True``.

        소속이 비어 있으면 배울 것이 없다. 이름으로는 배우지 않는다 —
        `홍길동` 을 직장으로 기억해 봐야 다음 행사에서 쓸 데가 없다.
        """
        key = normalize_belong(belong)
        if not key:
            return False
        if self._map.get(key) is relation:
            return False
        self._map[key] = relation
        return True

    def forget(self, belong: str) -> None:
        self._map.pop(normalize_belong(belong), None)

    def to_dict(self) -> dict[str, str]:
        return {key: relation.value for key, relation in sorted(self._map.items())}

    def apply_to(self, guests: Iterable[Guest]) -> int:
        """기억해 둔 소속을 가진 하객의 관계를 덮어쓴다. 바뀐 건수를 돌려준다.

        사용자가 직접 가르친 값이므로 키워드 추정보다 우선한다.
        """
        changed = 0
        for guest in guests:
            learned = self.get(guest.belong)
            if learned is not None and guest.relation is not learned:
                guest.relation = learned
                changed += 1
        return changed


def guests_sharing_belong(guests: Iterable[Guest], belong: str) -> list[Guest]:
    """같은 소속의 하객 목록. 일괄 변경을 제안할지 판단하는 데 쓴다."""
    key = normalize_belong(belong)
    if not key:
        return []
    return [guest for guest in guests if normalize_belong(guest.belong) == key]
