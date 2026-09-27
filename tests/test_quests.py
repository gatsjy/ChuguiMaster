"""단계 안내 판정과 화면 연동."""

from __future__ import annotations

import pytest

from chugui.samples import SAMPLE_TEXT
from chugui.services.quests import QUESTS, QuestSnapshot, QuestTracker


class TestTracker:
    def test_starts_at_first_step(self):
        progress = QuestTracker().progress()
        assert progress.current is QUESTS[0]
        assert (progress.cleared, progress.ratio) == (0, 0.0)

    def test_state_clears_paste_and_parse_together(self):
        tracker = QuestTracker()
        done = tracker.observe(QuestSnapshot(guest_count=3, review_count=1))
        assert [q.key for q in done] == ["paste", "parse"]
        assert tracker.progress().current.key == "review"

    def test_review_needs_data(self):
        """빈 명단에서 '확인 필요 고치기' 를 완료로 치지 않는다."""
        tracker = QuestTracker()
        tracker.observe(QuestSnapshot(has_input=True))
        assert not tracker.is_cleared("review")

    def test_finished_step_never_reopens(self):
        tracker = QuestTracker()
        tracker.observe(QuestSnapshot(guest_count=3, review_count=0))
        tracker.observe(QuestSnapshot(guest_count=5, review_count=2))
        assert tracker.is_cleared("review")

    def test_same_event_reports_once(self):
        tracker = QuestTracker()
        assert tracker.mark("copy")
        assert not tracker.mark("copy")

    def test_unknown_keys_are_ignored(self):
        tracker = QuestTracker(["paste", "hacked"])
        assert tracker.cleared_keys == ["paste"]
        assert not tracker.mark("hacked")

    def test_all_clear(self):
        progress = QuestTracker([quest.key for quest in QUESTS]).progress()
        assert progress.all_clear
        assert progress.ratio == 1.0

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


class TestGuideBar:
    def test_no_intro_screen(self, window):
        """첫 실행에도 창을 가리는 시작 화면 없이 바로 작업 화면이 보인다."""
        assert not hasattr(window, "_start_screen")
        assert window._input.isVisible()

    def test_first_step_outlines_input(self, window):
        assert window._quest_target is window._input
        assert window._input.property("questTarget") == "on"
        assert "1/" in window._quest_bar.title_text

    def test_parsing_advances_and_moves_outline(self, window, qt_app):
        window._input.setPlainText(SAMPLE_TEXT)
        window._handle_parse()
        qt_app.processEvents()
        assert window._tracker.is_cleared("parse")
        assert window._quest_target is not window._input
        assert window._input.property("questTarget") == "off"
        assert "완료" in window._quest_bar.title_text

    def test_outline_is_steady(self, window, qt_app):
        """깜박이지 않는다. 시간이 지나도 강조 상태가 그대로다."""
        before = window._input.property("questTarget")
        qt_app.processEvents()
        assert window._input.property("questTarget") == before == "on"

    def test_meal_change_finishes_meal_step(self, window):
        window._spin_adult.setValue(window._spin_adult.value() + 1_000)
        assert window._tracker.is_cleared("meal")

    def test_progress_persists(self, window, qt_app):
        window._input.setPlainText("홍길동 5만원")
        qt_app.processEvents()
        window._save_config()
        assert "paste" in window._config_repo.load().quests

    def test_progress_bar_fills(self, window, qt_app):
        before = window._quest_bar.bar.ratio
        window._input.setPlainText("홍길동 5만원")
        qt_app.processEvents()
        assert window._quest_bar.bar.ratio > before

    def test_copy_has_no_game_words(self, window):
        text = window._quest_bar.title_text
        for word in ("QUEST", "XP", "LEVEL", "CLEAR", "LV."):
            assert word not in text

    def test_done_message_points_to_the_real_next_step(self, window, qt_app):
        """완료 알림의 '다음:' 이 이미 끝난 단계를 가리키던 버그."""
        window._handle_sample()
        qt_app.processEvents()
        hint = window._quest_bar._hint.text()
        assert hint == f"다음: {window._tracker.progress().current.title}"
        assert "표로 변환" not in hint
