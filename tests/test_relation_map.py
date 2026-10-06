"""소속 → 관계 사용자 사전 테스트.

실제 225행 명단에서 나온 문제다. 관계 추정은 `보건소` `교회` 같은 일반명사만 안다.

    현대모비스   23건  회사명
    넥스트로     17건  회사명
    일구칠구     14건  부모님 모임 이름
    속셈말        3건  아버지 고향 마을 이름

앞의 둘은 사전을 늘리면 잡히는 척이라도 하지만, 뒤의 둘은 사용자만 아는 사실이라
어떤 키워드 목록으로도 영원히 못 맞힌다. 그래서 '한 번 가르치면 기억한다'로 간다.
"""

from __future__ import annotations

import json

import pytest

from chugui.models import Guest, Relation
from chugui.parsing.text_parser import parse_text
from chugui.services.relation_map import (
    RelationMap,
    guests_sharing_belong,
    normalize_belong,
)
from chugui.storage.repositories import RelationMapRepository


def guest(name: str, belong: str = "", relation: Relation = Relation.OTHER) -> Guest:
    return Guest(name=name, names=[name], amount=100_000, belong=belong, relation=relation)


class TestNormalizeBelong:
    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("넥스트로(주)", "(주)넥스트로"),
            ("넥스트로(주)", "주식회사 넥스트로"),
            ("현대모비스 충청부품사업소", "현대모비스충청부품사업소"),
            ("여명교회 사랑부", "여명교회사랑부"),
            ("일구칠구", " 일구칠구 "),
            ("아산시보건소", "아산시 보건소"),
        ],
    )
    def test_same_place_same_key(self, left, right):
        assert normalize_belong(left) == normalize_belong(right)

    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("현대모비스", "넥스트로"),
            ("일구칠구", "속셈말"),
            ("둔포보건지소", "인주보건소"),
        ],
    )
    def test_different_places_differ(self, left, right):
        assert normalize_belong(left) != normalize_belong(right)

    @pytest.mark.parametrize("value", ["", "   ", None, "()", "---"])
    def test_empty_becomes_empty_key(self, value):
        assert normalize_belong(value) == ""


class TestLearn:
    def test_learn_and_get(self):
        mapping = RelationMap()
        assert mapping.learn("현대모비스", Relation.WORK) is True
        assert mapping.get("현대모비스") is Relation.WORK

    def test_learn_matches_variant_spelling(self):
        mapping = RelationMap()
        mapping.learn("넥스트로(주)", Relation.WORK)
        assert mapping.get("(주)넥스트로") is Relation.WORK

    def test_relearning_same_value_is_noop(self):
        mapping = RelationMap()
        mapping.learn("일구칠구", Relation.OTHER)
        assert mapping.learn("일구칠구", Relation.OTHER) is False

    def test_relearning_changes_value(self):
        mapping = RelationMap()
        mapping.learn("청년회", Relation.OTHER)
        assert mapping.learn("청년회", Relation.FAITH) is True
        assert mapping.get("청년회") is Relation.FAITH

    @pytest.mark.parametrize("belong", ["", "   ", None])
    def test_empty_belong_is_not_learned(self, belong):
        """소속이 없으면 배울 것이 없다. 이름으로 배우면 다음 행사에서 쓸 데가 없다."""
        mapping = RelationMap()
        assert mapping.learn(belong, Relation.WORK) is False
        assert len(mapping) == 0

    def test_forget(self):
        mapping = RelationMap()
        mapping.learn("속셈말", Relation.FAMILY)
        mapping.forget("속셈말")
        assert mapping.get("속셈말") is None

    def test_unknown_belong_returns_none(self):
        assert RelationMap().get("한 번도 본 적 없는 곳") is None

    def test_contains(self):
        mapping = RelationMap()
        mapping.learn("현대모비스", Relation.WORK)
        assert "현대모비스 " in mapping
        assert "넥스트로" not in mapping


class TestApplyTo:
    def test_learned_belong_overrides_keyword_guess(self):
        """사용자가 직접 가르친 값이 추정보다 우선한다."""
        mapping = RelationMap({"일구칠구": Relation.FAMILY.value})
        guests = [guest("조문행", "일구칠구"), guest("이면구", "일구칠구")]
        assert mapping.apply_to(guests) == 2
        assert all(g.relation is Relation.FAMILY for g in guests)

    def test_unknown_belong_left_alone(self):
        mapping = RelationMap({"일구칠구": Relation.FAMILY.value})
        guests = [guest("이해명", "아산시보건소", Relation.WORK)]
        assert mapping.apply_to(guests) == 0
        assert guests[0].relation is Relation.WORK

    def test_already_correct_is_not_counted(self):
        mapping = RelationMap({"현대모비스": Relation.WORK.value})
        guests = [guest("남천석", "현대모비스", Relation.WORK)]
        assert mapping.apply_to(guests) == 0

    def test_empty_belong_untouched(self):
        mapping = RelationMap({"현대모비스": Relation.WORK.value})
        guests = [guest("강환민", "")]
        assert mapping.apply_to(guests) == 0
        assert guests[0].relation is Relation.OTHER

    def test_applies_to_parsed_list(self):
        """실제 명단 형태(탭 3열)에 그대로 걸린다."""
        guests = parse_text(
            "남천석\t100,000\t현대모비스\n조문행\t100,000\t일구칠구\n이해명\t100,000\t아산시보건소"
        )
        assert [g.relation for g in guests] == [Relation.OTHER, Relation.OTHER, Relation.WORK]

        mapping = RelationMap(
            {"현대모비스": Relation.WORK.value, "일구칠구": Relation.FAMILY.value}
        )
        assert mapping.apply_to(guests) == 2
        assert [g.relation for g in guests] == [Relation.WORK, Relation.FAMILY, Relation.WORK]


class TestSharingBelong:
    def test_finds_same_place_despite_spelling(self):
        guests = [
            guest("손해신", "넥스트로(주)"),
            guest("이윤기", "(주)넥스트로"),
            guest("정지만", "넥스트로"),
            guest("남천석", "현대모비스"),
        ]
        assert len(guests_sharing_belong(guests, "넥스트로")) == 3

    def test_empty_belong_matches_nothing(self):
        """소속 없는 39건이 서로 '같은 소속'으로 묶이면 안 된다."""
        guests = [guest("강환민", ""), guest("김혜림", ""), guest("박기태", "")]
        assert guests_sharing_belong(guests, "") == []


class TestRepository:
    def test_round_trip(self):
        repo = RelationMapRepository()
        mapping = repo.load()
        mapping.learn("현대모비스 충청부품사업소", Relation.WORK)
        mapping.learn("일구칠구", Relation.FAMILY)
        assert repo.save(mapping) is True

        reloaded = repo.load()
        assert len(reloaded) == 2
        assert reloaded.get("현대모비스충청부품사업소") is Relation.WORK
        assert reloaded.get("일구칠구") is Relation.FAMILY

    def test_missing_file_gives_empty_map(self):
        assert len(RelationMapRepository().load()) == 0

    @pytest.mark.parametrize(
        "payload", ["[]", "null", '"문자열"', "깨진 json", '{"일구칠구": 42}']
    )
    def test_garbage_never_raises(self, payload):
        repo = RelationMapRepository()
        repo.path.write_text(payload, encoding="utf-8")
        mapping = repo.load()
        assert isinstance(mapping, RelationMap)

    def test_unknown_relation_value_falls_back(self):
        repo = RelationMapRepository()
        repo.path.write_text(json.dumps({"어딘가": "없는관계"}), encoding="utf-8")
        assert repo.load().get("어딘가") is Relation.OTHER

    def test_clear(self):
        repo = RelationMapRepository()
        mapping = RelationMap()
        mapping.learn("속셈말", Relation.FAMILY)
        repo.save(mapping)
        repo.clear()
        assert len(repo.load()) == 0


class TestWindowIntegration:
    @pytest.fixture
    def window(self, qt_app):
        from chugui.ui.main_window import MainWindow

        win = MainWindow()
        win.show()
        yield win
        win.close()

    @staticmethod
    def _set_relation(window, row: int, relation: Relation) -> None:
        from PySide6.QtCore import Qt

        from chugui.ui.guest_model import Column

        window._model.setData(
            window._model.index(row, Column.RELATION),
            relation.value,
            Qt.ItemDataRole.EditRole,
        )

    def test_editing_relation_learns_the_belong(self, window, qt_app):
        window._model.set_guests(parse_text("남천석\t100,000\t현대모비스"))
        self._set_relation(window, 0, Relation.WORK)
        qt_app.processEvents()
        assert window._relation_map.get("현대모비스") is Relation.WORK

    def test_learned_belong_persists_to_disk(self, window, qt_app):
        window._model.set_guests(parse_text("남천석\t100,000\t현대모비스"))
        self._set_relation(window, 0, Relation.WORK)
        qt_app.processEvents()
        assert RelationMapRepository().load().get("현대모비스") is Relation.WORK

    def test_no_belong_learns_nothing(self, window, qt_app):
        window._model.set_guests(parse_text("강환민\t100,000"))
        self._set_relation(window, 0, Relation.WORK)
        qt_app.processEvents()
        assert len(window._relation_map) == 0

    def test_bulk_offer_appears_for_shared_belong(self, window, qt_app):
        window._model.set_guests(
            parse_text(
                "남천석\t100,000\t현대모비스\n"
                "유정곤\t200,000\t현대모비스\n"
                "채창균\t50,000\t현대모비스"
            )
        )
        self._set_relation(window, 0, Relation.WORK)
        qt_app.processEvents()
        assert window._toast._action.isVisible()
        assert window._toast._action.text() == "2건 변경"

    def test_bulk_offer_hidden_when_alone(self, window, qt_app):
        window._model.set_guests(parse_text("남천석\t100,000\t현대모비스"))
        self._set_relation(window, 0, Relation.WORK)
        qt_app.processEvents()
        assert not window._toast._action.isVisible()

    def test_bulk_change_applies_to_all(self, window, qt_app):
        window._model.set_guests(
            parse_text(
                "조문행\t100,000\t일구칠구\n"
                "이면구\t100,000\t일구칠구\n"
                "김한기\t50,000\t일구칠구"
            )
        )
        self._set_relation(window, 0, Relation.FAMILY)
        qt_app.processEvents()
        window._toast._action.click()
        qt_app.processEvents()
        assert all(g.relation is Relation.FAMILY for g in window._model.guests)

    def test_bulk_change_undoes_in_one_step(self, window, qt_app):
        """줄마다 명령을 쌓으면 Ctrl+Z 를 수십 번 눌러야 한다. 매크로로 묶는다."""
        window._model.set_guests(
            parse_text(
                "조문행\t100,000\t일구칠구\n"
                "이면구\t100,000\t일구칠구\n"
                "김한기\t50,000\t일구칠구"
            )
        )
        self._set_relation(window, 0, Relation.FAMILY)
        qt_app.processEvents()
        window._toast._action.click()
        qt_app.processEvents()

        window._undo_stack.undo()  # 일괄 변경 되돌리기
        qt_app.processEvents()
        assert [g.relation for g in window._model.guests[1:]] == [
            Relation.OTHER,
            Relation.OTHER,
        ]
        assert window._model.guests[0].relation is Relation.FAMILY

    def test_bulk_change_does_not_re_offer(self, window, qt_app):
        """일괄 변경이 줄마다 relationEdited 를 다시 보낸다. 되묻지 않아야 한다."""
        window._model.set_guests(
            parse_text(
                "조문행\t100,000\t일구칠구\n"
                "이면구\t100,000\t일구칠구\n"
                "김한기\t50,000\t일구칠구"
            )
        )
        self._set_relation(window, 0, Relation.FAMILY)
        qt_app.processEvents()
        window._toast._action.click()
        qt_app.processEvents()
        assert not window._toast._action.isVisible()

    def test_learned_map_applies_to_next_parse(self, window, qt_app):
        """다음 명단부터는 가르치지 않아도 알아서 분류된다."""
        window._relation_map.learn("일구칠구", Relation.FAMILY)
        window._input.setPlainText("새하객\t100,000\t일구칠구")
        window._handle_parse()
        qt_app.processEvents()
        assert window._model.guests[0].relation is Relation.FAMILY

    # ------------------------------------------------- 되돌리기와 학습

    def test_undo_forgets_a_belong_that_was_unknown(self, window, qt_app):
        """오클릭 → Ctrl+Z 했는데 사전에 남으면, 다음 명단 23건이 조용히 틀린다."""
        window._model.set_guests(parse_text("남천석\t100,000\t현대모비스"))
        self._set_relation(window, 0, Relation.FAITH)  # 드롭다운 오클릭
        qt_app.processEvents()
        assert window._relation_map.get("현대모비스") is Relation.FAITH

        window._undo_stack.undo()
        qt_app.processEvents()
        assert window._model.guests[0].relation is Relation.OTHER
        assert window._relation_map.get("현대모비스") is None

    def test_undo_restores_the_previously_learned_value(self, window, qt_app):
        """이미 알던 소속이면 잊는 게 아니라 그 값으로 돌아가야 한다."""
        window._relation_map.learn("현대모비스", Relation.WORK)
        window._model.set_guests(parse_text("남천석\t100,000\t현대모비스"))
        self._set_relation(window, 0, Relation.FAITH)
        qt_app.processEvents()

        window._undo_stack.undo()
        qt_app.processEvents()
        assert window._relation_map.get("현대모비스") is Relation.WORK

    def test_undo_is_persisted(self, window, qt_app):
        """되돌린 사전이 디스크에도 반영돼야 재시작 후 다시 틀리지 않는다."""
        window._model.set_guests(parse_text("남천석\t100,000\t현대모비스"))
        self._set_relation(window, 0, Relation.FAITH)
        window._undo_stack.undo()
        qt_app.processEvents()
        assert RelationMapRepository().load().get("현대모비스") is None

    def test_redo_teaches_again(self, window, qt_app):
        window._model.set_guests(parse_text("남천석\t100,000\t현대모비스"))
        self._set_relation(window, 0, Relation.WORK)
        window._undo_stack.undo()
        window._undo_stack.redo()
        qt_app.processEvents()
        assert window._relation_map.get("현대모비스") is Relation.WORK

    def test_undoing_bulk_then_first_edit_unwinds_fully(self, window, qt_app):
        window._model.set_guests(
            parse_text(
                "조문행\t100,000\t일구칠구\n"
                "이면구\t100,000\t일구칠구\n"
                "김한기\t50,000\t일구칠구"
            )
        )
        self._set_relation(window, 0, Relation.FAMILY)
        qt_app.processEvents()
        window._toast._action.click()
        qt_app.processEvents()

        window._undo_stack.undo()  # 일괄 변경
        assert window._relation_map.get("일구칠구") is Relation.FAMILY  # 첫 편집은 아직 살아 있다
        window._undo_stack.undo()  # 첫 편집
        qt_app.processEvents()
        assert all(g.relation is Relation.OTHER for g in window._model.guests)
        assert window._relation_map.get("일구칠구") is None

    # ------------------------------------------- 알림이 떠 있는 사이 표가 바뀜

    def test_bulk_change_survives_row_deletion(self, window, qt_app):
        """알림이 떠 있는 몇 초 사이 줄을 지우면 행 번호가 다른 사람을 가리킨다."""
        window._model.set_guests(
            parse_text(
                "김가나\t100,000\t현대모비스\n"
                "김다라\t100,000\t현대모비스\n"
                "김마바\t100,000\t현대모비스\n"
                "김사아\t100,000\t다른곳"
            )
        )
        self._set_relation(window, 0, Relation.WORK)
        qt_app.processEvents()
        window._model.remove_rows([1])  # 김다라 삭제 → 아래 줄이 한 칸씩 올라온다
        qt_app.processEvents()
        window._toast._action.click()
        qt_app.processEvents()

        by_name = {g.name: g for g in window._model.guests}
        assert by_name["김마바"].relation is Relation.WORK
        assert by_name["김사아"].relation is Relation.OTHER  # 다른 소속은 그대로

    def test_bulk_change_skips_rows_already_fixed_by_hand(self, window, qt_app):
        """사용자가 그 사이 손으로 고친 줄은 다시 건드리지 않는다(빈 되돌리기 항목도 없음)."""
        window._model.set_guests(
            parse_text(
                "조문행\t100,000\t일구칠구\n"
                "이면구\t100,000\t일구칠구\n"
                "김한기\t50,000\t일구칠구"
            )
        )
        self._set_relation(window, 0, Relation.FAMILY)
        qt_app.processEvents()
        window._bulk_relation_in_progress = True  # 이 편집으로 새 알림이 뜨지 않게
        self._set_relation(window, 1, Relation.FAMILY)
        window._bulk_relation_in_progress = False
        before = window._undo_stack.count()

        window._toast._action.click()
        qt_app.processEvents()
        assert window._undo_stack.count() == before + 1  # 남은 1건만 담은 매크로 하나
        assert all(g.relation is Relation.FAMILY for g in window._model.guests)
