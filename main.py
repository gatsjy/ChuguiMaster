"""ChuguiMaster 실행 진입점.

    python main.py

패키지를 설치하지 않고도 소스에서 바로 실행할 수 있도록 ``src`` 를 경로에 추가한다.
``pip install -e .`` 로 설치했다면 이 분기는 그냥 통과한다.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    try:
        import chugui  # noqa: F401
    except ImportError:
        src = Path(__file__).resolve().parent / "src"
        if src.is_dir():
            sys.path.insert(0, str(src))


def main() -> int:
    _ensure_src_on_path()
    from chugui.app import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
