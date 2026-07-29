"""PyInstaller 빌드 스크립트.

구버전 대비 변경점

* **기본을 ``--onedir`` 로** — ``--onefile`` 은 실행할 때마다 임시 폴더에
  전체를 압축 해제하므로 첫 화면까지 수 초가 걸린다. 단일 파일이 꼭 필요하면
  ``--onefile`` 플래그를 주면 된다.
* **pandas 제거** — v2는 openpyxl만 쓴다. 산출물 크기가 대략 절반이 된다.
* **불필요 모듈 제외** — matplotlib / tkinter / PySide6 미사용 모듈을 걷어낸다.
* **산출물 이름을 README와 일치** — v1은 ``ChuguiMaster-Single.exe`` 를 만들면서
  README에는 ``ChuguiMaster.exe`` 라고 적어두었다.

사용법::

    python build.py              # onedir (권장, 빠른 실행)
    python build.py --onefile    # 단일 exe (배포 편의)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "ChuguiMaster"
ROOT = Path(__file__).resolve().parent

# Qt는 대부분의 서브모듈을 쓰지 않는다. 빼면 용량과 기동 시간이 함께 줄어든다.
EXCLUDES = (
    "pandas", "numpy", "matplotlib", "scipy", "tkinter", "test", "unittest",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets", "PySide6.QtMultimedia", "PySide6.Qt3DCore",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtNetwork",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtBluetooth", "PySide6.QtPositioning",
)


def build(onefile: bool = False, clean: bool = True) -> int:
    icon = ROOT / "assets" / "icon.ico"

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--onefile" if onefile else "--onedir",
        f"--name={APP_NAME}",
        f"--paths={ROOT / 'src'}",
        "--collect-submodules=openpyxl",
        "--hidden-import=openpyxl.cell._writer",
    ]
    if clean:
        command.append("--clean")
    for module in EXCLUDES:
        command.append(f"--exclude-module={module}")
    if icon.is_file():
        command.append(f"--icon={icon}")
    command.append(str(ROOT / "main.py"))

    print(f"[{APP_NAME}] 빌드 시작 ({'onefile' if onefile else 'onedir'})")
    print("  " + " ".join(command))

    try:
        subprocess.run(command, check=True, cwd=ROOT)
    except FileNotFoundError:
        print("\n[오류] PyInstaller가 없습니다:  pip install -r requirements-dev.txt")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"\n[오류] 빌드 실패 (exit {exc.returncode})")
        return exc.returncode

    target = ROOT / "dist" / (f"{APP_NAME}.exe" if onefile else APP_NAME / f"{APP_NAME}.exe")
    print("\n[완료] 빌드 성공")
    print(f"  산출물: {target}")
    if target.exists():
        print(f"  크기:   {target.stat().st_size / 1_048_576:.1f} MB")
    if not onefile:
        folder = ROOT / "dist" / APP_NAME
        total = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
        print(f"  폴더 전체: {total / 1_048_576:.1f} MB (배포 시 폴더째 압축)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} 실행 파일 빌드")
    parser.add_argument("--onefile", action="store_true", help="단일 exe로 빌드 (기동이 느려짐)")
    parser.add_argument("--no-clean", action="store_true", help="이전 빌드 캐시 재사용")
    parser.add_argument("--purge", action="store_true", help="build/ dist/ 를 지우고 종료")
    args = parser.parse_args()

    if args.purge:
        for name in ("build", "dist"):
            shutil.rmtree(ROOT / name, ignore_errors=True)
        (ROOT / f"{APP_NAME}.spec").unlink(missing_ok=True)
        print("[완료] 빌드 산출물을 정리했습니다.")
        return 0

    return build(onefile=args.onefile, clean=not args.no_clean)


if __name__ == "__main__":
    raise SystemExit(main())
