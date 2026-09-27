"""디자인 시스템.

색 · 간격 · 타이포그래피를 **토큰**으로 정의하고, 스타일시트는 거기서 생성한다.
값을 바꾸려면 토큰만 고치면 되고, 두 테마가 구조적으로 항상 대응한다.

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
    #: 퀘스트 강조 · 경험치 막대 색.
    quest: str = "#fbbf24"


DARK = Palette(
    name="dark",
    window="#0b1220",
    surface="#151f33",
    surface_alt="#1c2942",
    surface_hover="#233150",
    border="#2c3b57",
    border_strong="#3d5075",
    text="#f1f5f9",
    text_muted="#c3cfe0",
    text_subtle="#93a3bb",
    accent="#93a5fd",
    accent_strong="#4f46e5",
    accent_hover="#6366f1",
    accent_soft="#1e2547",
    positive="#4ade80",
    # 채워진 버튼 위의 흰 글씨가 WCAG AA(4.5:1)를 넘어야 한다.
    # #059669는 3.77:1로 미달이라 한 단계 어둡게 잡았다.
    positive_strong="#047857",
    positive_surface="#0a3a2c",
    positive_border="#0f7057",
    warning="#fbbf24",
    warning_text="#fcd34d",
    warning_surface="#3a2a08",
    warning_border="#a16207",
    danger="#fb7185",
    grid="#22304a",
    selection="#2b3a63",
    focus_ring="#93a5fd",
    badges={
        Relation.FAMILY.value: BadgeColors("#3b1163", "#e0bafd", "#7e34c9"),
        Relation.WORK.value: BadgeColors("#1b2260", "#b4befe", "#4f5bd5"),
        Relation.FAITH.value: BadgeColors("#0a3a2c", "#82efb9", "#0f7057"),
        Relation.SCHOOL.value: BadgeColors("#452408", "#fbd38d", "#b45309"),
        Relation.OTHER.value: BadgeColors("#2c3b57", "#dbe4f0", "#4a5c7e"),
    },
)

LIGHT = Palette(
    name="light",
    window="#eef2f7",
    surface="#ffffff",
    surface_alt="#f6f8fb",
    surface_hover="#eaeff6",
    border="#dde4ee",
    border_strong="#c2ccdb",
    text="#0f172a",
    text_muted="#475569",
    text_subtle="#5c6b81",
    accent="#4338ca",
    accent_strong="#4f46e5",
    accent_hover="#6366f1",
    accent_soft="#eef0ff",
    positive="#047857",
    positive_strong="#047857",
    positive_surface="#ecfdf5",
    positive_border="#a7f3d0",
    warning="#b45309",
    warning_text="#92400e",
    warning_surface="#fffbeb",
    warning_border="#fcd34d",
    danger="#dc2626",
    grid="#eef2f7",
    selection="#e0e7ff",
    focus_ring="#4f46e5",
    badges={
        Relation.FAMILY.value: BadgeColors("#f5e9ff", "#6b21a8", "#d8b4fe"),
        Relation.WORK.value: BadgeColors("#e8ebff", "#3730a3", "#a5b4fc"),
        Relation.FAITH.value: BadgeColors("#e3fcef", "#065f46", "#6ee7b7"),
        Relation.SCHOOL.value: BadgeColors("#fef6e0", "#8a4708", "#fcd34d"),
        Relation.OTHER.value: BadgeColors("#eef2f7", "#334155", "#c2ccdb"),
    },
)


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
    accent="#5ee9ff",
    accent_strong="#c2185b",
    accent_hover="#d81b60",
    accent_soft="#1f2150",
    positive="#7dff6b",
    positive_strong="#1b7a35",
    positive_surface="#0f2a1c",
    positive_border="#2fbf4f",
    warning="#ffb000",
    warning_text="#ffd166",
    warning_surface="#33230a",
    warning_border="#c98a00",
    danger="#ff6b88",
    grid="#26215a",
    selection="#3b2f7a",
    focus_ring="#ffd23f",
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
    quest="#ffd23f",
)

PALETTES: dict[str, Palette] = {"retro": RETRO, "dark": DARK, "light": LIGHT}

#: 테마 버튼에 표시할 '다음 테마' 이름.
THEME_LABELS: dict[str, str] = {"retro": "🕹  레트로", "dark": "🌙  다크", "light": "☀  라이트"}


def palette_for(dark_mode: bool) -> Palette:
    return DARK if dark_mode else LIGHT


def palette_named(name: str) -> Palette:
    return PALETTES.get(name, RETRO)


def badge_colors(palette: Palette, relation: Relation) -> BadgeColors:
    return palette.badges.get(relation.value, palette.badges[Relation.OTHER.value])


# ----------------------------------------------------------------- 스타일시트


def build_stylesheet(palette: Palette) -> str:
    """토큰으로부터 애플리케이션 전역 스타일시트를 생성한다."""
    p = palette
    r_sm = round(Radius.SM * p.radius_scale)
    r_md = round(Radius.MD * p.radius_scale)
    bw = 2 if p.retro else 1
    return _base_stylesheet(p, r_sm, r_md, bw) + _quest_stylesheet(p, r_sm, bw) + (
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
    QScrollArea {{ background: transparent; border: none; }}
    """


def _quest_stylesheet(p: Palette, r_sm: int, bw: int) -> str:
    """퀘스트 바 · 시작 화면. 모든 테마에 쓰인다."""
    return f"""
    QFrame#questBar {{
        background-color: {p.surface};
        border: {bw}px solid {p.quest};
        border-radius: {r_sm}px;
    }}
    QLabel#questLevel {{
        font-size: {FontSize.SMALL}px;
        font-weight: 800;
        color: {p.window};
        background-color: {p.quest};
        border-radius: {r_sm}px;
        padding: 2px {Space.SM}px;
    }}
    QLabel#questTitle {{ font-size: {FontSize.SUBTITLE}px; font-weight: 800; color: {p.text}; }}
    QLabel#questHint {{ font-size: {FontSize.SMALL}px; color: {p.text_muted}; }}
    QLabel#questXp {{ font-size: {FontSize.CAPTION}px; font-weight: 700; color: {p.text_subtle}; }}

    /* 지금 퀘스트가 가리키는 요소. ID 규칙보다 우선하도록 ID까지 붙여 쓴다. */
    QTextEdit[questTarget="on"], QTableView[questTarget="on"],
    QFrame#card[questTarget="on"], QPushButton#primary[questTarget="on"],
    QPushButton#success[questTarget="on"] {{
        border: 3px solid {p.quest};
    }}

    QFrame#startScreen {{ background-color: {p.window}; }}
    QFrame#startPanel {{
        background-color: {p.surface};
        border: 3px solid {p.quest};
        border-radius: {r_sm}px;
    }}
    QLabel#startLogo {{
        font-size: 34px;
        font-weight: 900;
        color: {p.quest};
        letter-spacing: 2px;
    }}
    QLabel#startSubtitle {{ font-size: {FontSize.SUBTITLE}px; color: {p.text_muted}; }}
    QLabel#startStep {{ font-size: {FontSize.BODY}px; color: {p.text}; }}
    QLabel#startBlink {{ font-size: {FontSize.SUBTITLE}px; font-weight: 800; color: {p.accent}; }}
    QLabel#questRow {{ font-size: {FontSize.BODY}px; color: {p.text}; }}
    QLabel#questRowDone {{ font-size: {FontSize.BODY}px; color: {p.positive}; }}
    """


def _retro_stylesheet(p: Palette) -> str:
    """아케이드 느낌: 굵은 테두리 · 입체 버튼 · 각진 모서리.

    Qt 스타일시트는 그림자를 지원하지 않으므로, 아래쪽 테두리를 두껍고 어둡게
    칠해 눌리기 전의 입체감을 만들고, 누르면 그 두께를 위쪽 여백으로 옮겨
    버튼이 '내려가는' 느낌을 낸다.
    """
    return f"""
    QFrame#card, QFrame#netCard {{ border-width: 2px; }}
    QTableView {{ border-width: 2px; }}
    QLabel#appTitle {{ color: {p.quest}; letter-spacing: 1px; }}
    QLabel#sectionTitle {{ color: {p.accent}; }}
    QHeaderView::section {{ border-bottom: 2px solid {p.border_strong}; }}

    QPushButton {{
        border: 2px solid {p.border_strong};
        border-bottom: 5px solid {p.bevel};
    }}
    QPushButton:pressed {{
        border-bottom: 2px solid {p.bevel};
        margin-top: 3px;
    }}
    QPushButton#primary, QPushButton#success {{
        border: 2px solid {p.bevel};
        border-bottom: 5px solid {p.bevel};
    }}
    QPushButton#primary:pressed, QPushButton#success:pressed {{
        border-bottom: 2px solid {p.bevel};
        margin-top: 3px;
    }}
    QPushButton#ghost {{ border: 2px solid {p.border}; border-bottom: 4px solid {p.bevel}; }}
    QPushButton#danger {{ border: 2px solid {p.border}; border-bottom: 4px solid {p.bevel}; }}

    QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{ border-width: 2px; }}
    QCheckBox::indicator {{ border-radius: 0px; border-width: 2px; }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ border-radius: 0px; }}
    """
