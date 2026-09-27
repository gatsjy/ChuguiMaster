"""퀘스트 · 레벨 판정과 화면 연동."""

from __future__ import annotations

import pytest

from chugui.samples import SAMPLE_TEXT
from chugui.services.quests import LEVELS, MAX_XP, QUESTS, QuestSnapshot, QuestTracker


class TestTracker:
    def test_starts_at_first_quest(self):
        progress = QuestTracker().progress()
        assert progress.current is QUESTS[0]
        assert (progress.level, progress.xp, progress.cleared) == (1, 0, 0)

    def test_state_clears_paste_and_parse_together(self):
        tracker = QuestTracker()
        update = tracker.observe(QuestSnapshot(guest_count=3, review_count=1))
        assert [q.key for q in update.newly_cleared] == ["paste", "parse"]
        assert tracker.progress().current.key == "review"

    def test_review_needs_data(self):
        """빈 명단에서 '확인 필요 0건' 을 공짜로 주지 않는다."""
        tracker = QuestTracker()
        tracker.observe(QuestSnapshot(has_input=True))
        assert not tracker.is_cleared("review")

    def test_cleared_quest_never_relocks(self):
        tracker = QuestTracker()
        tracker.observe(QuestSnapshot(guest_count=3, review_count=0))
        tracker.observe(QuestSnapshot(guest_count=5, review_count=2))
        assert tracker.is_cleared("review")

    def test_same_event_rewards_once(self):
        tracker = QuestTracker()
        assert tracker.mark("copy").newly_cleared
        assert not tracker.mark("copy").newly_cleared

    def test_unknown_keys_are_ignored(self):
        tracker = QuestTracker(["paste", "hacked"])
        assert tracker.cleared_keys == ["paste"]
        assert not tracker.mark("hacked").newly_cleared

    def test_level_up_is_reported(self):
        tracker = QuestTracker()
        update = tracker.observe(QuestSnapshot(guest_count=1, review_count=0))  # 50+100+150 XP
        assert update.level_up
        assert tracker.progress().level > 1

    def test_all_clear_reaches_max_level(self):
        tracker = QuestTracker([quest.key for quest in QUESTS])
        progress = tracker.progress()
        assert progress.all_clear
        assert progress.xp == MAX_XP
        assert progress.title == LEVELS[-1][1]
        assert progress.level_ratio == 1.0

    def test_levels_are_reachable_and_ordered(self):
        needs = [need for need, _ in LEVELS]
        assert needs == sorted(needs)
        assert needs[-1] == sum(quest.xp for quest in QUESTS)

    def test_reset(self):
        tracker = QuestTracker([quest.key for quest in QUESTS])
        tracker.reset()
        assert tracker.progress().current is QUESTS[0]


# ------------------------------------------------------------------ 화면 연동


@pytest.fixture
def window(qt_app):
    from chugui.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    qt_app.processEvents()
    yield win
    win.close()


class TestStartScreen:
    def test_shown_on_first_run(self, window):
        assert window._start_screen.isVisible()

    def test_start_dismisses_and_is_remembered(self, window, qt_app):
        window._start_screen.startRequested.emit()
        qt_app.processEvents()
        assert not window._start_screen.isVisible()
        window._save_config()
        assert window._config_repo.load().onboarded is True

    def test_practice_loads_sample(self, window, qt_app):
        window._start_screen.practiceRequested.emit()
        qt_app.processEvents()
        assert window._model.guests
        assert not window._start_screen.isVisible()

    def test_not_shown_after_onboarding(self, window, qt_app):
        from chugui.ui.main_window import MainWindow

        window._finish_onboarding()
        window._save_config()
        again = MainWindow()
        again.show()
        qt_app.processEvents()
        try:
            assert not again._start_screen.isVisible()
        finally:
            again.close()


class TestQuestFlow:
    def test_first_quest_highlights_input(self, window):
        assert window._quest_target is window._input
        assert "QUEST 1/" in window._quest_bar.title_text

    def test_parsing_advances_quests_and_moves_highlight(self, window, qt_app):
        window._input.setPlainText(SAMPLE_TEXT)
        window._handle_parse()
        qt_app.processEvents()
        assert window._tracker.is_cleared("paste")
        assert window._tracker.is_cleared("parse")
        assert window._quest_target is not window._input
        assert "CLEAR" in window._quest_bar.title_text or "LEVEL UP" in window._quest_bar.title_text

    def test_meal_change_clears_meal_quest(self, window):
        window._spin_adult.setValue(window._spin_adult.value() + 1_000)
        assert window._tracker.is_cleared("meal")

    def test_progress_persists(self, window, qt_app):
        window._input.setPlainText("홍길동 5만원")
        qt_app.processEvents()
        window._save_config()
        assert "paste" in window._config_repo.load().quests

    def test_highlight_toggles_property(self, window):
        window._blink_quest_target()
        first = window._input.property("questTarget")
        window._blink_quest_target()
        assert window._input.property("questTarget") != first

    def test_xp_bar_fills(self, window, qt_app):
        before = window._quest_bar.bar.ratio
        window._input.setPlainText("홍길동 5만원")
        qt_app.processEvents()
        assert window._quest_bar.bar.ratio > before
