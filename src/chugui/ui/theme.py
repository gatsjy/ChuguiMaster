"""테마.

구버전은 ``apply_theme()`` 안에 40줄짜리 스타일시트 리터럴이 두 벌 있었고,
관계 배지 색상은 별도의 ``BADGE_STYLES`` 문자열 딕셔너리에 하드코딩되어 있었다.
그 배지 색이 다크 전용이라 라이트 모드에서 대비가 무너졌다.

여기서는 팔레트 하나에서 스타일시트를 생성한다. 색을 바꾸려면 팔레트만 고치면 된다.
"""

from __future__ import annotations

from dataclasses import dataclass

from chugui.models import Relation


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
    border: str
    text: str
    text_muted: str
    text_subtle: str
    accent: str
    accent_strong: str
    positive: str
    positive_surface: str
    positive_border: str
    warning: str
    warning_surface: str
    danger: str
    grid: str
    selection: str
    badges: dict[str, BadgeColors]


DARK = Palette(
    name="dark",
    window="#0f172a",
    surface="#1e293b",
    surface_alt="#172033",
    border="#334155",
    text="#f8fafc",
    text_muted="#cbd5e1",
    text_subtle="#94a3b8",
    accent="#818cf8",
    accent_strong="#4f46e5",
    positive="#34d399",
    positive_surface="#064e3b",
    positive_border="#047857",
    warning="#fbbf24",
    warning_surface="#422006",
    danger="#f87171",
    grid="#1e293b",
    selection="#312e81",
    badges={
        Relation.FAMILY.value: BadgeColors("#3b0764", "#d8b4fe", "#7e22ce"),
        Relation.WORK.value: BadgeColors("#1e1b4b", "#a5b4fc", "#4338ca"),
        Relation.FAITH.value: BadgeColors("#064e3b", "#6ee7b7", "#047857"),
        Relation.SCHOOL.value: BadgeColors("#451a03", "#fcd34d", "#b45309"),
        Relation.OTHER.value: BadgeColors("#334155", "#e2e8f0", "#64748b"),
    },
)

LIGHT = Palette(
    name="light",
    window="#f1f5f9",
    surface="#ffffff",
    surface_alt="#f8fafc",
    border="#e2e8f0",
    text="#0f172a",
    text_muted="#475569",
    text_subtle="#64748b",
    accent="#4f46e5",
    accent_strong="#4338ca",
    positive="#059669",
    positive_surface="#ecfdf5",
    positive_border="#a7f3d0",
    warning="#b45309",
    warning_surface="#fef3c7",
    danger="#dc2626",
    grid="#f1f5f9",
    selection="#e0e7ff",
    badges={
        Relation.FAMILY.value: BadgeColors("#f3e8ff", "#6b21a8", "#d8b4fe"),
        Relation.WORK.value: BadgeColors("#e0e7ff", "#3730a3", "#a5b4fc"),
        Relation.FAITH.value: BadgeColors("#d1fae5", "#065f46", "#6ee7b7"),
        Relation.SCHOOL.value: BadgeColors("#fef3c7", "#92400e", "#fcd34d"),
        Relation.OTHER.value: BadgeColors("#f1f5f9", "#334155", "#cbd5e1"),
    },
)

FONT_STACK = "'Pretendard', 'Malgun Gothic', '맑은 고딕', 'Segoe UI', sans-serif"


def palette_for(dark_mode: bool) -> Palette:
    return DARK if dark_mode else LIGHT


def badge_colors(palette: Palette, relation: Relation) -> BadgeColors:
    return palette.badges.get(relation.value, palette.badges[Relation.OTHER.value])


def build_stylesheet(palette: Palette) -> str:
    """팔레트로부터 애플리케이션 전역 스타일시트를 만든다."""
    p = palette
    return f"""
    QWidget {{
        font-family: {FONT_STACK};
        color: {p.text};
    }}
    QMainWindow, QDialog {{ background-color: {p.window}; }}
    QLabel {{ background: transparent; border: none; color: {p.text}; }}
    QLabel#appTitle {{ font-size: 17px; font-weight: 800; color: {p.accent}; }}
    QLabel#sectionTitle {{ font-size: 14px; font-weight: 700; }}
    QLabel#cardTitle {{ font-size: 12px; font-weight: 600; color: {p.text_subtle}; }}
    QLabel#cardValue {{ font-size: 20px; font-weight: 800; }}
    QLabel#hint {{ font-size: 11px; color: {p.text_subtle}; }}

    QFrame#card {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: 10px;
    }}
    QFrame#netCard {{
        background-color: {p.positive_surface};
        border: 1px solid {p.positive_border};
        border-radius: 10px;
    }}
    QFrame#reviewCard {{
        background-color: {p.warning_surface};
        border: 1px solid {p.warning};
        border-radius: 10px;
    }}
    QFrame#hintBox {{
        background-color: {p.surface_alt};
        border: 1px dashed {p.border};
        border-radius: 6px;
    }}

    QTextEdit, QPlainTextEdit {{
        background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 10px;
        font-size: 13px;
        color: {p.text};
        selection-background-color: {p.accent_strong};
    }}
    QTextEdit#dropActive {{ border: 2px dashed {p.accent}; }}

    QLineEdit, QSpinBox, QComboBox {{
        background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 12px;
        font-weight: 600;
        color: {p.text};
        min-height: 26px;
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {p.accent}; }}
    QComboBox QAbstractItemView {{
        background-color: {p.surface};
        color: {p.text};
        border: 1px solid {p.border};
        selection-background-color: {p.accent_strong};
        selection-color: #ffffff;
    }}

    QPushButton {{
        font-size: 13px;
        font-weight: 700;
        border-radius: 6px;
        padding: 8px 14px;
        min-height: 34px;
        border: 1px solid {p.border};
        background-color: {p.surface_alt};
        color: {p.text};
    }}
    QPushButton:hover {{ border: 1px solid {p.accent}; }}
    QPushButton:disabled {{ color: {p.text_subtle}; border-color: {p.border}; }}
    QPushButton#primary {{
        background-color: {p.accent_strong};
        color: #ffffff;
        border: none;
    }}
    QPushButton#primary:hover {{ background-color: {p.accent}; }}
    QPushButton#success {{
        background-color: {p.positive};
        color: #ffffff;
        border: none;
    }}
    QPushButton#ghost {{
        min-height: 26px;
        font-size: 12px;
        color: {p.accent};
        background-color: transparent;
    }}
    QPushButton#danger {{ color: {p.danger}; background-color: transparent; }}

    QTableView {{
        background-color: {p.surface};
        alternate-background-color: {p.surface_alt};
        border: 1px solid {p.border};
        border-radius: 10px;
        gridline-color: {p.grid};
        font-size: 13px;
        color: {p.text};
        selection-background-color: {p.selection};
        selection-color: {p.text};
    }}
    QHeaderView::section {{
        background-color: {p.surface_alt};
        font-weight: 700;
        color: {p.text_muted};
        padding: 8px;
        border: none;
        border-bottom: 2px solid {p.border};
    }}
    QTableCornerButton::section {{ background-color: {p.surface_alt}; border: none; }}

    QTabWidget::pane {{ border: 1px solid {p.border}; border-radius: 8px; background: {p.surface}; }}
    QTabBar::tab {{
        background: {p.surface_alt};
        padding: 10px 18px;
        font-weight: 600;
        color: {p.text_subtle};
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    QTabBar::tab:selected {{ background: {p.surface}; color: {p.accent}; }}

    QCheckBox {{ color: {p.text_muted}; background: transparent; border: none; }}
    QSplitter::handle {{ background-color: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; width: 0px; }}
    QStatusBar {{ color: {p.text_subtle}; }}
    QToolTip {{
        background-color: {p.surface};
        color: {p.text};
        border: 1px solid {p.border};
        padding: 6px;
    }}
    """
