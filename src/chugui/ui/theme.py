"""디자인 시스템.

색 · 간격 · 타이포그래피를 **토큰**으로 정의하고, 스타일시트는 거기서 생성한다.
값을 바꾸려면 토큰만 고치면 된다. 화면은 레트로 테마 하나만 쓴다.

접근성 원칙: 본문 텍스트는 배경 대비 **4.5:1 이상**(WCAG AA),
큰 텍스트(18.66px 이상 굵게)는 **3:1 이상**을 만족한다.
`tests/test_ux.py` 가 모든 조합을 자동 검증한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from chugui.models import Relation

# --------------------------------------------------------------------- 토큰

FONT_STACK = "'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Segoe UI', sans-serif"
#: 레트로 테마용 픽셀 폰트. ``assets/fonts`` 에 넣어 두면 자동으로 등록된다.
#: 없으면 시스템 폰트로 내려가며, 그래도 색·테두리·기호로 레트로 느낌은 유지된다.
PIXEL_FONT_STACK = (
    "'Galmuri11', 'Galmuri9', 'DungGeunMo', 'NeoDunggeunmo', "
    "'Malgun Gothic', '맑은 고딕', monospace"
)


class Space:
    """8pt 그리드 기반 간격 스케일. 임의의 숫자를 쓰지 않는다."""

    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24


class Radius:
    SM = 6
    MD = 10
    LG = 14
    PILL = 999


class FontSize:
    """타이포그래피 스케일(px)."""

    CAPTION = 11
    SMALL = 12
    BODY = 13
    SUBTITLE = 15
    TITLE = 18
    DISPLAY = 22


class Size:
    """상호작용 요소 최소 크기. 클릭 타깃은 최소 28px을 보장한다."""

    CONTROL_HEIGHT = 34
    COMPACT_HEIGHT = 30
    MIN_HIT_TARGET = 28
    ROW_HEIGHT = 40
    CARD_HEIGHT = 84
    # 레이아웃이 실제로 요구하는 최소 폭은 약 1,067px(측정값)이다.
    # 1280x800 노트북에서도 여유 있게 열리도록 그보다 조금 크게 잡는다.
    WINDOW_MIN_WIDTH = 1160
    WINDOW_MIN_HEIGHT = 720


# --------------------------------------------------------------------- 팔레트


@dataclass(frozen=True)
class BadgeColors:
    background: str
    foreground: str
    border: str


@dataclass(frozen=True)
class Palette:
    """테마 하나를 구성하는 모든 색."""

    name: str
    window: str
    surface: str
    surface_alt: str
    surface_hover: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_subtle: str
    accent: str
    accent_strong: str
    accent_hover: str
    accent_soft: str
    positive: str
    positive_strong: str
    positive_surface: str
    positive_border: str
    warning: str
    warning_text: str
    warning_surface: str
    warning_border: str
    danger: str
    grid: str
    selection: str
    focus_ring: str
    badges: dict[str, BadgeColors]
    font_stack: str = FONT_STACK
    #: 0이면 모든 모서리가 각진다(픽셀 느낌).
    radius_scale: float = 1.0
    #: 레트로 전용 장식(입체 버튼 · 굵은 테두리)을 켠다.
    retro: bool = False
    #: 입체 버튼 아래쪽 그림자 색.
    bevel: str = "#000000"


RETRO = Palette(
    name="retro",
    window="#0d0b1e",
    surface="#17143a",
    surface_alt="#1d1947",
    surface_hover="#29245e",
    border="#3a3480",
    border_strong="#6a5fd0",
    text="#f4f1ff",
    text_muted="#d4ccff",
    text_subtle="#a9a0e0",
    accent="#a9b8ff",
    accent_strong="#4c3fb5",
    accent_hover="#5a4cc8",
    accent_soft="#1f2150",
    positive="#7ddca0",
    positive_strong="#1b7a45",
    positive_surface="#0f2a1c",
    positive_border="#2f8f5a",
    warning="#ffb000",
    warning_text="#ffd166",
    warning_surface="#33230a",
    warning_border="#c98a00",
    danger="#ff8aa0",
    grid="#26215a",
    selection="#3b2f7a",
    focus_ring="#a9b8ff",
    badges={
        Relation.FAMILY.value: BadgeColors("#3a0f4f", "#ffa8f5", "#c04bd8"),
        Relation.WORK.value: BadgeColors("#0e2350", "#8fd3ff", "#3b82f6"),
        Relation.FAITH.value: BadgeColors("#0f3326", "#8cffc1", "#22b573"),
        Relation.SCHOOL.value: BadgeColors("#3d2608", "#ffd166", "#d08c00"),
        Relation.OTHER.value: BadgeColors("#26215a", "#e4e0ff", "#6a5fd0"),
    },
    font_stack=PIXEL_FONT_STACK,
    radius_scale=0.0,
    retro=True,
    bevel="#05040f",
)

#: 앱이 쓰는 유일한 팔레트.
PALETTE = RETRO


def badge_colors(palette: Palette, relation: Relation) -> BadgeColors:
    return palette.badges.get(relation.value, palette.badges[Relation.OTHER.value])


# ----------------------------------------------------------------- 스타일시트


def build_stylesheet(palette: Palette) -> str:
    """토큰으로부터 애플리케이션 전역 스타일시트를 생성한다."""
    p = palette
    r_sm = round(Radius.SM * p.radius_scale)
    r_md = round(Radius.MD * p.radius_scale)
    bw = 2 if p.retro else 1
    return _base_stylesheet(p, r_sm, r_md, bw) + (
        _retro_stylesheet(p) if p.retro else ""
    )


def _base_stylesheet(p: Palette, r_sm: int, r_md: int, bw: int) -> str:
    return f"""
    QWidget {{
        font-family: {p.font_stack};
        font-size: {FontSize.BODY}px;
        color: {p.text};
    }}
    QMainWindow, QDialog {{ background-color: {p.window}; }}

    /* ---------------------------------------------------------- 텍스트 */
    QLabel {{ background: transparent; border: none; color: {p.text}; }}
    QLabel#appTitle {{
        font-size: {FontSize.TITLE}px;
        font-weight: 800;
        color: {p.text};
        letter-spacing: -0.3px;
    }}
    QLabel#appVersion {{ font-size: {FontSize.CAPTION}px; color: {p.text_subtle}; font-weight: 600; }}
    QLabel#sectionTitle {{ font-size: {FontSize.SUBTITLE}px; font-weight: 700; letter-spacing: -0.2px; }}
    QLabel#cardTitle {{ font-size: {FontSize.SMALL}px; font-weight: 600; color: {p.text_subtle}; }}
    QLabel#cardValue {{
        font-size: {FontSize.DISPLAY}px;
        font-weight: 800;
        letter-spacing: -0.6px;
    }}
    QLabel#cardCaption {{ font-size: {FontSize.CAPTION}px; color: {p.text_subtle}; }}
    QLabel#hint {{ font-size: {FontSize.CAPTION}px; color: {p.text_subtle}; }}
    QLabel#preview {{
        font-size: {FontSize.SMALL}px;
        font-weight: 700;
        color: {p.accent};
        background-color: {p.accent_soft};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        padding: {Space.SM}px {Space.MD}px;
    }}
    QLabel#emptyTitle {{ font-size: {FontSize.SUBTITLE}px; font-weight: 700; color: {p.text_muted}; }}
    QLabel#emptyBody {{ font-size: {FontSize.BODY}px; color: {p.text_subtle}; }}
    QLabel#emptyIcon {{ font-size: 40px; }}

    /* ------------------------------------------------------------ 카드 */
    QFrame#card {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: {r_md}px;
    }}
    QFrame#netCard {{
        background-color: {p.positive_surface};
        border: 1px solid {p.positive_border};
        border-radius: {r_md}px;
    }}
    QFrame#reviewBanner {{
        background-color: {p.warning_surface};
        border: 1px solid {p.warning_border};
        border-radius: {r_sm}px;
    }}
    QLabel#reviewBannerText {{ color: {p.warning_text}; font-size: {FontSize.BODY}px; font-weight: 700; }}
    QFrame#hintBox {{
        background-color: {p.surface_alt};
        border: 1px dashed {p.border_strong};
        border-radius: {r_sm}px;
    }}
    QFrame#separator {{ background-color: {p.border}; border: none; }}

    /* ------------------------------------------------------------ 입력 */
    QTextEdit, QPlainTextEdit {{
        background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        padding: {Space.MD}px;
        font-size: {FontSize.BODY}px;
        color: {p.text};
        selection-background-color: {p.accent_strong};
        selection-color: #ffffff;
    }}
    QTextEdit:focus {{ border: 1px solid {p.focus_ring}; }}
    QTextEdit#dropActive {{
        border: 2px dashed {p.accent};
        background-color: {p.accent_soft};
    }}

    QLineEdit, QSpinBox, QComboBox {{
        background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        padding: {Space.XS}px {Space.SM}px;
        font-size: {FontSize.SMALL}px;
        font-weight: 600;
        color: {p.text};
        min-height: {Size.COMPACT_HEIGHT - 10}px;
    }}
    QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{ border: 1px solid {p.border_strong}; }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {p.focus_ring}; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background-color: {p.surface};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        padding: {Space.XS}px;
        selection-background-color: {p.accent_strong};
        selection-color: #ffffff;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; }}

    /* ------------------------------------------------------------ 버튼 */
    QPushButton {{
        font-size: {FontSize.BODY}px;
        font-weight: 700;
        border-radius: {r_sm}px;
        padding: {Space.SM}px {Space.LG}px;
        min-height: {Size.CONTROL_HEIGHT - 12}px;
        border: 1px solid {p.border_strong};
        background-color: {p.surface_alt};
        color: {p.text};
    }}
    QPushButton:hover {{ background-color: {p.surface_hover}; border-color: {p.accent}; }}
    QPushButton:pressed {{ background-color: {p.surface_hover}; padding-top: {Space.SM + 1}px; }}
    QPushButton:focus {{ border: 2px solid {p.focus_ring}; }}
    QPushButton:disabled {{ color: {p.text_subtle}; border-color: {p.border}; background: transparent; }}

    QPushButton#primary {{
        background-color: {p.accent_strong};
        color: #ffffff;
        border: 1px solid {p.accent_strong};
        min-height: {Size.CONTROL_HEIGHT - 8}px;
        font-size: {FontSize.SUBTITLE}px;
    }}
    QPushButton#primary:hover {{ background-color: {p.accent_hover}; border-color: {p.accent_hover}; }}

    QPushButton#success {{
        background-color: {p.positive_strong};
        color: #ffffff;
        border: 1px solid {p.positive_strong};
        min-height: {Size.CONTROL_HEIGHT - 8}px;
        font-size: {FontSize.SUBTITLE}px;
    }}
    QPushButton#success:hover {{ background-color: {p.positive}; border-color: {p.positive}; }}

    QPushButton#successOutline {{
        color: {p.positive};
        background-color: transparent;
        border: 1px solid {p.positive_border};
        min-height: {Size.CONTROL_HEIGHT - 8}px;
        font-size: {FontSize.SUBTITLE}px;
    }}
    QPushButton#successOutline:hover {{ background-color: {p.positive_surface}; }}

    QPushButton#ghost {{
        min-height: {Size.COMPACT_HEIGHT - 8}px;
        font-size: {FontSize.SMALL}px;
        color: {p.text_muted};
        background-color: transparent;
        border: 1px solid {p.border};
        padding: {Space.XS}px {Space.MD}px;
    }}
    QPushButton#ghost:hover {{
        color: {p.accent};
        border-color: {p.accent};
        background-color: {p.surface_hover};
    }}

    QPushButton#danger {{
        color: {p.danger};
        background-color: transparent;
        border: 1px solid {p.border};
    }}
    QPushButton#danger:hover {{ border-color: {p.danger}; background-color: {p.surface_hover}; }}

    QPushButton#bannerAction {{
        color: {p.warning_text};
        background-color: transparent;
        border: 1px solid {p.warning_border};
        min-height: {Size.MIN_HIT_TARGET - 6}px;
        font-size: {FontSize.SMALL}px;
        padding: {Space.XS}px {Space.MD}px;
    }}

    /* ------------------------------------------------------------ 목록 */
    QListView {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        color: {p.text};
        outline: none;
        padding: {Space.XS}px;
    }}
    QListView::item {{ padding: {Space.SM}px; border-bottom: 1px solid {p.grid}; }}
    QListView::item:hover {{ background-color: {p.surface_hover}; }}
    QListView::item:selected {{ background-color: {p.selection}; color: {p.text}; }}

    /* -------------------------------------------------------------- 표 */
    QTableView {{
        background-color: {p.surface};
        alternate-background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: {r_md}px;
        gridline-color: {p.grid};
        font-size: {FontSize.BODY}px;
        color: {p.text};
        selection-background-color: {p.selection};
        selection-color: {p.text};
        outline: none;
    }}
    QTableView::item {{ padding: {Space.XS}px {Space.SM}px; border: none; }}
    QTableView::item:hover {{ background-color: {p.surface_hover}; }}
    QTableView::item:focus {{ border: 1px solid {p.focus_ring}; }}
    QHeaderView::section {{
        background-color: {p.surface_alt};
        font-size: {FontSize.SMALL}px;
        font-weight: 700;
        color: {p.text_muted};
        padding: {Space.SM}px {Space.SM}px;
        border: none;
        border-bottom: 2px solid {p.border};
    }}
    QHeaderView::section:hover {{ color: {p.accent}; }}
    QTableCornerButton::section {{ background-color: {p.surface_alt}; border: none; }}

    /* ------------------------------------------------------------ 기타 */
    QTabWidget::pane {{
        border: 1px solid {p.border};
        border-radius: {r_sm}px;
        background: {p.surface};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        padding: {Space.SM}px {Space.LG}px;
        font-size: {FontSize.SMALL}px;
        font-weight: 600;
        color: {p.text_subtle};
        border: 1px solid transparent;
        border-top-left-radius: {r_sm}px;
        border-top-right-radius: {r_sm}px;
    }}
    QTabBar::tab:selected {{
        background: {p.surface};
        color: {p.accent};
        border-color: {p.border};
        border-bottom-color: {p.surface};
    }}
    QTabBar::tab:hover:!selected {{ color: {p.text_muted}; }}

    QCheckBox {{
        color: {p.text_muted};
        background: transparent;
        border: none;
        font-size: {FontSize.SMALL}px;
        spacing: {Space.XS + 2}px;
        padding: {Space.XS}px;
    }}
    QCheckBox:hover {{ color: {p.text}; }}
    QCheckBox::indicator {{
        width: 15px; height: 15px;
        border: 1px solid {p.border_strong};
        border-radius: 4px;
        background-color: {p.surface_alt};
    }}
    QCheckBox::indicator:checked {{
        background-color: {p.accent_strong};
        border-color: {p.accent_strong};
    }}
    QCheckBox::indicator:hover {{ border-color: {p.accent}; }}

    QSplitter::handle {{ background-color: transparent; }}
    QSplitter::handle:horizontal {{ width: {Space.MD}px; }}
    QSplitter::handle:hover {{ background-color: {p.border}; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{
        background: {p.border_strong};
        border-radius: 5px;
        min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p.accent}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{
        background: {p.border_strong};
        border-radius: 5px;
        min-width: 32px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; width: 0px; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    QStatusBar {{ color: {p.text_subtle}; font-size: {FontSize.SMALL}px; }}
    QStatusBar::item {{ border: none; }}
    QToolTip {{
        background-color: {p.surface};
        color: {p.text};
        border: 1px solid {p.border_strong};
        border-radius: {r_sm}px;
        padding: {Space.SM}px;
        font-size: {FontSize.SMALL}px;
    }}
    /* 우클릭 메뉴. Windows 는 메뉴를 기본 테마(흰 바탕)로 그리므로 여기서 칠하지 않으면
       밝은 글자가 흰 바탕에 묻혀 빈 상자처럼 보인다(표 우클릭 · 입력창 우클릭). */
    QMenu {{
        background-color: {p.surface};
        color: {p.text};
        border: 1px solid {p.border_strong};
        padding: {Space.XS}px;
        font-size: {FontSize.BODY}px;
    }}
    QMenu::item {{
        padding: {Space.SM}px {Space.XL}px {Space.SM}px {Space.MD}px;
        background: transparent;
        color: {p.text};
    }}
    QMenu::item:selected {{ background-color: {p.selection}; color: {p.text}; }}
    QMenu::item:disabled {{ color: {p.text_subtle}; }}
    QMenu::separator {{ height: 1px; background: {p.border}; margin: {Space.XS}px {Space.SM}px; }}
    QScrollArea {{ background: transparent; border: none; }}
    """


def _retro_stylesheet(p: Palette) -> str:
    """레트로 느낌은 픽셀 폰트와 각진 모서리로만 낸다. 장식은 최소한으로.

    Qt 스타일시트는 그림자를 지원하지 않으므로 아래쪽 테두리를 조금 두껍게 칠해
    얕은 입체감을 만들고, 누르면 그 두께를 위쪽 여백으로 옮긴다.
    """
    return f"""
    QHeaderView::section {{ border-bottom: 2px solid {p.border_strong}; }}

    QPushButton {{
        border: 1px solid {p.border_strong};
        border-bottom: 3px solid {p.bevel};
    }}
    QPushButton:pressed {{
        border-bottom: 1px solid {p.bevel};
        margin-top: 2px;
    }}
    QPushButton#primary, QPushButton#success {{
        border: 1px solid {p.bevel};
        border-bottom: 3px solid {p.bevel};
    }}
    QPushButton#successOutline {{
        border: 1px solid {p.positive_border};
        border-bottom: 3px solid {p.bevel};
    }}
    QPushButton#primary:pressed, QPushButton#success:pressed, QPushButton#successOutline:pressed {{
        border-bottom: 1px solid {p.bevel};
        margin-top: 2px;
    }}
    /* 머리줄 버튼은 거의 검은 창 바탕 위에 놓인다. 그림자색(bevel)을 쓰면 아래 테두리가
       바탕에 묻혀 버튼이 아래가 잘린 탭처럼 보였다. 테두리 색으로 입체감을 낸다. */
    QPushButton#ghost, QPushButton#danger {{
        border: 1px solid {p.border_strong};
        border-bottom: 3px solid {p.border};
    }}
    QPushButton#ghost:pressed, QPushButton#danger:pressed {{
        border-bottom: 1px solid {p.border};
        margin-top: 2px;
    }}

    QCheckBox::indicator {{ border-radius: 0px; }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ border-radius: 0px; }}
    """


def apply_application_theme(palette: Palette) -> None:
    """앱 전체에 팔레트와 스타일시트를 적용한다.

    스타일시트는 이름을 붙인 위젯만 칠한다. 칠하지 않은 위젯(목록 · 스크롤 영역 ·
    메시지 상자 등)은 Windows 기본값인 **흰 바탕**을 쓰면서 글자색만 밝은 색을
    물려받아, 글자가 보이지 않았다('이전 시점 복구' 목록, '입력 가이드').
    기본 팔레트 자체를 테마 색으로 맞추면 새 화면을 추가해도 같은 사고가 나지 않는다.
    창에만 걸지 않고 앱에 거는 이유: 부모 없이 뜨는 대화상자에도 적용되어야 한다.
    """
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    p = palette
    qp = QPalette()
    role = QPalette.ColorRole
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        for color_role, value in (
            (role.Window, p.window),
            (role.WindowText, p.text),
            (role.Base, p.surface),
            (role.AlternateBase, p.surface_alt),
            (role.Text, p.text),
            (role.PlaceholderText, p.text_subtle),
            (role.Button, p.surface_alt),
            (role.ButtonText, p.text),
            (role.BrightText, "#ffffff"),
            (role.Highlight, p.selection),
            (role.HighlightedText, p.text),
            (role.ToolTipBase, p.surface),
            (role.ToolTipText, p.text),
            (role.Link, p.accent),
            (role.Mid, p.border),
            (role.Dark, p.bevel),
        ):
            qp.setColor(group, color_role, QColor(value))
    for color_role in (role.WindowText, role.Text, role.ButtonText):
        qp.setColor(QPalette.ColorGroup.Disabled, color_role, QColor(p.text_subtle))
    qp.setColor(QPalette.ColorGroup.Disabled, role.Base, QColor(p.window))
    qp.setColor(QPalette.ColorGroup.Disabled, role.Window, QColor(p.window))
    # 같은 값을 다시 걸어도 Qt 는 살아 있는 모든 위젯을 다시 칠한다. 바뀔 때만 건다.
    if app.palette() != qp:
        app.setPalette(qp)
    sheet = build_stylesheet(p)
    if app.styleSheet() != sheet:
        app.setStyleSheet(sheet)
