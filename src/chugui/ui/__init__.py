"""PySide6 프레젠테이션 계층."""

__all__ = ["MainWindow"]


def __getattr__(name: str):  # pragma: no cover - 지연 로딩
    if name == "MainWindow":
        from chugui.ui.main_window import MainWindow

        return MainWindow
    raise AttributeError(name)
