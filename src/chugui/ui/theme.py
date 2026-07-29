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


def palette_for(dark_mode: bool) -> Palette:
    return DARK if dark_mode else LIGHT


def badge_colors(palette: Palette, relation: Relation) -> BadgeColors:
    return palette.badges.get(relation.value, palette.badges[Relation.OTHER.value])


# ----------------------------------------------------------------- 스타일시트


def build_stylesheet(palette: Palette) -> str:
    """토큰으로부터 애플리케이션 전역 스타일시트를 생성한다."""
    p = palette
    return f"""
    QWidget {{
        font-family: {FONT_STACK};
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
    QLabel#emptyTitle {{ font-size: {FontSize.SUBTITLE}px; font-weight: 700; color: {p.text_muted}; }}
    QLabel#emptyBody {{ font-size: {FontSize.BODY}px; color: {p.text_subtle}; }}
    QLabel#emptyIcon {{ font-size: 40px; }}

    /* ------------------------------------------------------------ 카드 */
    QFrame#card {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: {Radius.MD}px;
    }}
    QFrame#netCard {{
        background-color: {p.positive_surface};
        border: 1px solid {p.positive_border};
        border-radius: {Radius.MD}px;
    }}
    QFrame#reviewBanner {{
        background-color: {p.warning_surface};
        border: 1px solid {p.warning_border};
        border-radius: {Radius.SM}px;
    }}
    QLabel#reviewBannerText {{ color: {p.warning_text}; font-size: {FontSize.BODY}px; font-weight: 700; }}
    QFrame#hintBox {{
        background-color: {p.surface_alt};
        border: 1px dashed {p.border_strong};
        border-radius: {Radius.SM}px;
    }}
    QFrame#separator {{ background-color: {p.border}; border: none; }}

    /* ------------------------------------------------------------ 입력 */
    QTextEdit, QPlainTextEdit {{
        background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: {Radius.SM}px;
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
        border-radius: {Radius.SM}px;
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
        border-radius: {Radius.SM}px;
        padding: {Space.XS}px;
        selection-background-color: {p.accent_strong};
        selection-color: #ffffff;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; }}

    /* ------------------------------------------------------------ 버튼 */
    QPushButton {{
        font-size: {FontSize.BODY}px;
        font-weight: 700;
        border-radius: {Radius.SM}px;
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
        border-radius: {Radius.MD}px;
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
        border-radius: {Radius.SM}px;
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
        border-top-left-radius: {Radius.SM}px;
        border-top-right-radius: {Radius.SM}px;
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
        border-radius: {Radius.SM}px;
        padding: {Space.SM}px;
        font-size: {FontSize.SMALL}px;
    }}
    QScrollArea {{ background: transparent; border: none; }}
    """
