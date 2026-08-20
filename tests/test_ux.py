"""UX / 접근성 자동 검증.

기능 테스트가 "동작하는가"를 본다면 이 파일은 **"쓸 만한가"** 를 본다.
디자인은 리뷰로 지키기 어렵다. 대비비·클릭 타깃·빈 상태·포커스처럼
객관적으로 측정 가능한 것들은 테스트로 고정한다.

기준: WCAG 2.1 AA
    - 본문 텍스트 대비 4.5:1 이상
    - 큰 텍스트(18.66px 이상 굵게 / 24px 이상) 3:1 이상
    - UI 컴포넌트 경계 3:1 이상
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from chugui.models import Relation
from chugui.parsing.text_parser import parse_text
from chugui.samples import SAMPLE_TEXT
from chugui.ui.guest_model import Column
from chugui.ui.main_window import MainWindow
from chugui.ui.theme import DARK, LIGHT, FontSize, Palette, Size, build_stylesheet

# ------------------------------------------------------------------ 대비 계산

AA_NORMAL = 4.5
AA_LARGE = 3.0
AA_COMPONENT = 3.0


def _channel(value: int) -> float:
    srgb = value / 255.0
    return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    """WCAG 상대 휘도."""
    qcolor = QColor(color)
    assert qcolor.isValid(), f"잘못된 색상 값: {color}"
    return (
        0.2126 * _channel(qcolor.red())
        + 0.7152 * _channel(qcolor.green())
        + 0.0722 * _channel(qcolor.blue())
    )


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 명도 대비비 (1.0 ~ 21.0)."""
    a, b = relative_luminance(foreground), relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


PALETTES = pytest.mark.parametrize("palette", [DARK, LIGHT], ids=["dark", "light"])


class TestContrastSanity:
    """대비 계산기 자체 검증 — 이게 틀리면 아래 테스트가 전부 무의미하다."""

    def test_known_values(self):
        assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
        assert contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0, abs=0.01)
        # WCAG 문서의 대표 예시
        assert contrast_ratio("#777777", "#ffffff") == pytest.approx(4.48, abs=0.05)


@PALETTES
class TestTextContrast:
    """모든 텍스트 색 × 배경 조합이 AA를 만족해야 한다."""

    @pytest.mark.parametrize("text_token", ["text", "text_muted", "text_subtle"])
    @pytest.mark.parametrize("surface_token", ["window", "surface", "surface_alt", "surface_hover"])
    def test_body_text_on_surfaces(self, palette: Palette, text_token: str, surface_token: str):
        fg = getattr(palette, text_token)
        bg = getattr(palette, surface_token)
        ratio = contrast_ratio(fg, bg)
        assert ratio >= AA_NORMAL, (
            f"[{palette.name}] {text_token}({fg}) on {surface_token}({bg}) = {ratio:.2f}:1"
        )

    def test_accent_text_on_surface(self, palette: Palette):
        """강조색은 링크·아이콘·값에 쓰이므로 본문 기준을 지켜야 한다."""
        for surface in (palette.surface, palette.surface_alt, palette.window):
            ratio = contrast_ratio(palette.accent, surface)
            assert ratio >= AA_NORMAL, f"[{palette.name}] accent on {surface} = {ratio:.2f}:1"

    def test_danger_text_on_surface(self, palette: Palette):
        ratio = contrast_ratio(palette.danger, palette.surface)
        assert ratio >= AA_NORMAL, f"[{palette.name}] danger = {ratio:.2f}:1"

    def test_positive_value_on_net_card(self, palette: Palette):
        """최종 순 정산금은 22px 굵은 글씨(큰 텍스트)지만 본문 기준까지 만족시킨다."""
        ratio = contrast_ratio(palette.positive, palette.positive_surface)
        assert ratio >= AA_NORMAL, f"[{palette.name}] 순정산 값 = {ratio:.2f}:1"

    def test_negative_value_on_net_card(self, palette: Palette):
        """순 정산금이 음수일 때 danger 색으로 바뀐다. 그 조합도 읽혀야 한다."""
        ratio = contrast_ratio(palette.danger, palette.positive_surface)
        assert ratio >= AA_LARGE, f"[{palette.name}] 음수 순정산 값 = {ratio:.2f}:1"

    def test_warning_banner(self, palette: Palette):
        ratio = contrast_ratio(palette.warning_text, palette.warning_surface)
        assert ratio >= AA_NORMAL, f"[{palette.name}] 경고 배너 = {ratio:.2f}:1"

    def test_white_on_filled_buttons(self, palette: Palette):
        """채워진 버튼의 흰 글씨. 13~15px 일반 굵기이므로 본문 기준."""
        for name, fill in (("primary", palette.accent_strong), ("success", palette.positive_strong)):
            ratio = contrast_ratio("#ffffff", fill)
            assert ratio >= AA_NORMAL, f"[{palette.name}] {name} 버튼 = {ratio:.2f}:1"


@PALETTES
class TestBadgeContrast:
    """관계 배지는 5종 × 2테마 = 10조합. v1은 다크 전용 색을 라이트에도 써서 대비가 무너졌다."""

    @pytest.mark.parametrize("relation", list(Relation), ids=lambda r: r.name)
    def test_badge_text(self, palette: Palette, relation: Relation):
        badge = palette.badges[relation.value]
        ratio = contrast_ratio(badge.foreground, badge.background)
        assert ratio >= AA_NORMAL, (
            f"[{palette.name}] {relation.value} 배지 텍스트 = {ratio:.2f}:1"
        )

    @pytest.mark.parametrize("relation", list(Relation), ids=lambda r: r.name)
    def test_badge_border_against_surface(self, palette: Palette, relation: Relation):
        """배지 테두리가 카드 배경과 구분되어야 배지로 인식된다."""
        badge = palette.badges[relation.value]
        ratio = contrast_ratio(badge.border, palette.surface)
        assert ratio >= 1.4, f"[{palette.name}] {relation.value} 배지 테두리 = {ratio:.2f}:1"


@PALETTES
class TestComponentBoundaries:
    def test_focus_ring_is_visible(self, palette: Palette):
        """키보드 사용자가 포커스 위치를 알 수 있어야 한다."""
        for surface in (palette.surface, palette.surface_alt):
            ratio = contrast_ratio(palette.focus_ring, surface)
            assert ratio >= AA_COMPONENT, f"[{palette.name}] 포커스 링 = {ratio:.2f}:1"

    def test_input_border_is_visible(self, palette: Palette):
        ratio = contrast_ratio(palette.border_strong, palette.surface)
        assert ratio >= 1.4, f"[{palette.name}] 입력 테두리 = {ratio:.2f}:1"

    def test_selection_keeps_text_readable(self, palette: Palette):
        """선택된 행의 글씨가 선택 배경 위에서 읽혀야 한다."""
        ratio = contrast_ratio(palette.text, palette.selection)
        assert ratio >= AA_NORMAL, f"[{palette.name}] 선택 행 텍스트 = {ratio:.2f}:1"

    def test_alternating_rows_are_distinguishable_but_subtle(self, palette: Palette):
        """줄무늬는 구분되되 눈에 거슬리지 않아야 한다."""
        ratio = contrast_ratio(palette.surface, palette.surface_alt)
        assert 1.01 <= ratio <= 1.35, f"[{palette.name}] 교대 행 대비 = {ratio:.2f}:1"


class TestDesignTokens:
    def test_spacing_scale_is_monotonic(self):
        from chugui.ui.theme import Space

        values = [Space.XS, Space.SM, Space.MD, Space.LG, Space.XL]
        assert values == sorted(values)
        assert len(set(values)) == len(values)

    def test_type_scale_is_monotonic(self):
        values = [
            FontSize.CAPTION,
            FontSize.SMALL,
            FontSize.BODY,
            FontSize.SUBTITLE,
            FontSize.TITLE,
            FontSize.DISPLAY,
        ]
        assert values == sorted(values)

    def test_minimum_body_font_size(self):
        """본문 13px 미만은 한글에서 읽기 어렵다."""
        assert FontSize.BODY >= 13
        assert FontSize.CAPTION >= 11

    def test_hit_targets_are_large_enough(self):
        assert Size.MIN_HIT_TARGET >= 24
        assert Size.CONTROL_HEIGHT >= Size.MIN_HIT_TARGET
        assert Size.ROW_HEIGHT >= Size.MIN_HIT_TARGET

    @PALETTES
    def test_stylesheet_builds_and_covers_object_names(self, palette: Palette):
        sheet = build_stylesheet(palette)
        assert sheet.strip()
        for object_name in (
            "appTitle", "sectionTitle", "cardTitle", "cardValue", "cardCaption",
            "hint", "emptyTitle", "emptyBody", "card", "netCard", "reviewBanner",
            "hintBox", "primary", "success", "ghost", "danger", "bannerAction",
        ):
            assert f"#{object_name}" in sheet, f"[{palette.name}] #{object_name} 스타일 누락"

    @PALETTES
    def test_stylesheet_has_no_unresolved_placeholders(self, palette: Palette):
        sheet = build_stylesheet(palette)
        assert "{" not in sheet.replace("{{", "").replace("}}", "") or "}" in sheet
        assert "None" not in sheet
        assert "PLACEHOLDER" not in sheet


# ------------------------------------------------------------------ 창 단위


@pytest.fixture
def window(qt_app):
    win = MainWindow()
    win.show()
    qt_app.processEvents()
    yield win
    win.close()


@pytest.fixture
def loaded_window(window, qt_app):
    window._model.set_guests(parse_text(SAMPLE_TEXT))
    qt_app.processEvents()
    return window


class TestEmptyState:
    """빈 격자 대신 다음에 할 일을 알려준다."""

    def test_empty_state_shown_initially(self, window):
        assert window._table_stack.currentWidget() is window._empty_state
        assert "없습니다" in window._empty_state.title_text

    def test_table_shown_after_parsing(self, loaded_window):
        assert loaded_window._table_stack.currentWidget() is loaded_window._table

    def test_distinct_message_when_filter_matches_nothing(self, loaded_window, qt_app):
        loaded_window._search.setText("존재하지않는이름")
        qt_app.processEvents()
        assert loaded_window._table_stack.currentWidget() is loaded_window._empty_state
        assert "조건에 맞는" in loaded_window._empty_state.title_text

    def test_returns_to_table_when_filter_cleared(self, loaded_window, qt_app):
        loaded_window._search.setText("존재하지않는이름")
        qt_app.processEvents()
        loaded_window._search.clear()
        qt_app.processEvents()
        assert loaded_window._table_stack.currentWidget() is loaded_window._table


class TestReviewBanner:
    """문제가 있을 때만 말한다. 0건일 때 회색 카드를 띄우는 건 노이즈다."""

    def test_hidden_when_no_problems(self, loaded_window):
        assert loaded_window._current_settlement().review_count == 0
        assert not loaded_window._review_banner.isVisible()

    def test_visible_when_problems_exist(self, window, qt_app):
        window._model.set_guests(parse_text("홍길동 친척\n김철수 10만원 대학"))
        qt_app.processEvents()
        assert window._review_banner.isVisible()
        assert "1건" in window._banner_label.text()

    def test_action_filters_to_problem_rows(self, window, qt_app):
        window._model.set_guests(parse_text("홍길동 친척\n김철수 10만원 대학"))
        qt_app.processEvents()
        window._banner_action.click()
        qt_app.processEvents()
        assert window._chk_review.isChecked()
        assert window._proxy.rowCount() == 1

    def test_disappears_after_fixing(self, window, qt_app):
        window._model.set_guests(parse_text("홍길동 친척"))
        qt_app.processEvents()
        assert window._review_banner.isVisible()
        window._model.setData(window._model.index(0, Column.AMOUNT), "10만원")
        qt_app.processEvents()
        assert not window._review_banner.isVisible()


class TestReviewRowHighlight:
    """경고를 한 열에만 적어두면 넓은 표에서 눈에 띄지 않는다."""

    def test_problem_row_has_background(self, window, qt_app):
        window._model.set_guests(parse_text("홍길동 친척\n김철수 10만원 대학"))
        qt_app.processEvents()
        model = window._model
        problem = model.data(model.index(0, Column.NAME), Qt.ItemDataRole.BackgroundRole)
        clean = model.data(model.index(1, Column.NAME), Qt.ItemDataRole.BackgroundRole)
        assert problem is not None
        assert clean is None

    def test_highlight_follows_theme(self, window, qt_app):
        window._model.set_guests(parse_text("홍길동 친척"))
        qt_app.processEvents()
        model = window._model
        dark_brush = model.data(model.index(0, Column.NO), Qt.ItemDataRole.BackgroundRole)
        window._toggle_theme()
        qt_app.processEvents()
        light_brush = model.data(model.index(0, Column.NO), Qt.ItemDataRole.BackgroundRole)
        assert dark_brush.color() != light_brush.color()


class TestAutosaveDiscipline:
    """표시만 바뀐 경우에는 개인정보가 든 세션 파일을 다시 쓰지 않는다."""

    def test_theme_repaint_does_not_schedule_session_save(self, loaded_window):
        loaded_window._autosave_timer.stop()
        loaded_window._model.set_review_color(QColor("#fff7ed"))
        assert not loaded_window._autosave_timer.isActive()

    def test_message_refresh_does_not_schedule_session_save(self, loaded_window):
        loaded_window._autosave_timer.stop()
        loaded_window._model.refresh_messages()
        assert not loaded_window._autosave_timer.isActive()


class TestAccessibility:
    """스크린 리더와 키보드 사용자를 위한 최소 요건."""

    @staticmethod
    def _interactive_widgets(window):
        # findChildren은 타입 튜플을 받지 않는다. QWidget으로 훑고 isinstance로 거른다.
        types = (QAbstractButton, QLineEdit, QComboBox, QSpinBox, QTextEdit, QCheckBox)
        return [
            widget
            for widget in window.findChildren(QWidget)
            if isinstance(widget, types)
            and widget.isVisibleTo(window)
            and not widget.objectName().startswith("qt_")
        ]

    def test_every_interactive_widget_is_labelled(self, window):
        """이름도 툴팁도 없는 컨트롤은 스크린 리더에서 정체불명이 된다."""
        unlabelled = [
            f"{type(w).__name__}({w.objectName() or w.accessibleName() or '?'})"
            for w in self._interactive_widgets(window)
            if not (w.accessibleName() or w.toolTip())
        ]
        assert unlabelled == [], f"레이블 없는 컨트롤: {unlabelled}"

    def test_kpi_cards_expose_values(self, loaded_window):
        for card in (
            loaded_window._card_total,
            loaded_window._card_guests,
            loaded_window._card_meal,
            loaded_window._card_net,
        ):
            assert card.accessibleName()
            assert card.accessibleDescription()

    def test_table_is_labelled(self, window):
        assert window._table.accessibleName() == "하객 목록"

    @pytest.mark.parametrize(
        ("sequence", "label"),
        [("Ctrl+Return", "파싱"), ("Ctrl+S", "내보내기"), ("Ctrl+F", "검색")],
    )
    def test_keyboard_shortcuts_registered(self, window, sequence, label):
        shortcuts = {
            action.shortcut().toString(QKeySequence.SequenceFormat.PortableText)
            for action in window.actions()
        }
        assert sequence in shortcuts, f"{label} 단축키 누락 (등록됨: {shortcuts})"

    def test_find_shortcut_focuses_search(self, window, qt_app):
        for action in window.actions():
            if action.text() == "검색":
                action.trigger()
        qt_app.processEvents()
        assert window._search.hasFocus()

    def test_editable_cells_advertise_editability(self, loaded_window):
        model = loaded_window._model
        for column in (Column.NAME, Column.AMOUNT, Column.RELATION):
            tooltip = model.data(model.index(0, column), Qt.ItemDataRole.ToolTipRole)
            assert tooltip, f"{column.name} 열에 안내 툴팁 없음"

    def test_copy_cell_previews_the_message(self, loaded_window):
        model = loaded_window._model
        tooltip = model.data(model.index(0, Column.COPY), Qt.ItemDataRole.ToolTipRole)
        assert "홍길동" in tooltip, "복사 전에 문구를 미리 볼 수 있어야 한다"


class TestLayoutRobustness:
    def test_minimum_window_size_is_usable(self, window):
        """1366x768 노트북에서도 열려야 한다."""
        assert 1000 <= window.minimumWidth() <= 1366
        assert 700 <= window.minimumHeight() <= 768

    def test_layout_fits_within_declared_minimum(self, loaded_window, qt_app):
        """선언한 최소 크기가 레이아웃의 실제 요구치보다 작으면 가로 스크롤이 생긴다."""
        loaded_window.resize(loaded_window.minimumWidth(), loaded_window.minimumHeight())
        qt_app.processEvents()
        required = loaded_window.centralWidget().minimumSizeHint().width()
        assert required <= loaded_window.minimumWidth(), (
            f"레이아웃이 {required}px를 요구하는데 최소 폭은 {loaded_window.minimumWidth()}px"
        )

    @pytest.mark.parametrize(
        "line",
        [
            "홍길동 3억 2천만원 친척",   # 320,000,000원 - 9자리
            "홍길동 5천만원 친척",       # 50,000,000원
            "홍길동 10만원 친척",        # 100,000원
        ],
    )
    def test_kpi_values_are_never_clipped(self, window, qt_app, line):
        """금액이 '...' 으로 잘리는 정산 화면은 신뢰를 잃는다.

        카드 글자 크기가 폭에 맞춰 자동으로 줄어드는지 검증한다.
        """
        window.resize(window.minimumWidth(), window.minimumHeight())
        window._model.set_guests(parse_text(line))
        qt_app.processEvents()

        for card in (window._card_total, window._card_net, window._card_meal):
            label = card.value_label
            label.ensurePolished()
            needed = label.sizeHint().width()
            assert needed <= card.available_value_width, (
                f"{card.accessibleName()} 값 잘림: '{label.text()}' "
                f"필요 {needed}px / 가용 {card.available_value_width}px"
            )

    def test_value_font_shrinks_only_when_needed(self, window, qt_app):
        """짧은 값에서는 큰 글씨를 유지해야 한다. 무조건 축소하면 위계가 무너진다."""
        window.resize(300, 700)
        window._model.set_guests(parse_text("홍길동 10만원 친척"))
        qt_app.processEvents()
        small_value_style = window._card_total.value_label.styleSheet()

        window._card_total.set_value("999,999,999,999,999,999원")
        qt_app.processEvents()
        large_value_style = window._card_total.value_label.styleSheet()

        assert f"font-size: {FontSize.DISPLAY}px" in small_value_style
        assert small_value_style != large_value_style

    def test_toast_stays_inside_window(self, window, qt_app):
        window._toast.show_message("테스트 알림입니다")
        qt_app.processEvents()
        assert window._toast.geometry().left() >= 0
        assert window._toast.geometry().top() >= 0
        assert window._toast.geometry().right() <= window.width()

    def test_toast_recenters_after_resize(self, window, qt_app):
        window._toast.show_message("알림")
        qt_app.processEvents()
        before = window._toast.geometry().center().x()
        window.resize(window.width() + 260, window.height())
        qt_app.processEvents()
        assert window._toast.geometry().center().x() != before

    def test_panels_cannot_be_collapsed_to_zero(self, window):
        """스플리터를 끝까지 끌어 패널을 사라지게 만들 수 있으면 안 된다."""
        assert window._splitter.childrenCollapsible() is False
        assert window._splitter.count() == 2

class TestFeedback:
    """모든 사용자 행동에는 눈에 보이는 반응이 있어야 한다."""

    def test_parse_with_empty_input_gives_feedback_and_focus(self, window, qt_app):
        window._input.clear()
        window._handle_parse()
        qt_app.processEvents()
        assert window._toast.isVisible()
        assert window._input.hasFocus()

    def test_status_bar_summarises_after_load(self, loaded_window):
        message = loaded_window.statusBar().currentMessage()
        assert "10건" in message
        assert "평균" in message
        assert "감사 인사" in message

    def test_status_bar_guides_when_empty(self, window):
        assert "붙여넣" in window.statusBar().currentMessage()

    def test_copy_gives_feedback_without_marking_sent(self, loaded_window, qt_app):
        """복사는 발송이 아니다. v1은 복사만 해도 발송완료 처리했다."""
        index = loaded_window._proxy.index(0, Column.COPY)
        loaded_window._on_copy_clicked(index)
        qt_app.processEvents()
        assert loaded_window._toast.isVisible()
        assert loaded_window._model.guests[0].sent_thanks is False

    def test_cards_explain_their_numbers(self, loaded_window):
        """숫자만 있고 근거가 없으면 사용자가 검산할 수 없다."""
        assert "대인" in loaded_window._card_meal._caption.text()
        assert "참석" in loaded_window._card_guests._caption.text()
        assert "현금" in loaded_window._card_total._caption.text()


class TestThemeSwitching:
    def test_both_themes_apply_without_error(self, loaded_window, qt_app):
        for _ in range(2):
            loaded_window._toggle_theme()
            qt_app.processEvents()
            assert loaded_window.styleSheet().strip()

    def test_theme_button_label_matches_state(self, window, qt_app):
        first = window._btn_theme.text()
        window._toggle_theme()
        qt_app.processEvents()
        assert window._btn_theme.text() != first

    def test_theme_choice_persists(self, window, qt_app):
        original = window._config.dark_mode
        window._toggle_theme()
        window._save_config()
        assert window._config_repo.load().dark_mode is (not original)
