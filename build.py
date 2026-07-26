import os
import subprocess
import sys

def build_exe():
    print("[ChuguiMaster] Building Single Executable (.exe)...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(current_dir, 'main.py')
    
    # 단일 .exe 파일 빌드 옵션 (--onefile)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name=ChuguiMaster-Single",
        "--hidden-import=openpyxl",
        "--hidden-import=pandas",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtGui",
        "--collect-all=openpyxl",
        f"--paths={os.path.join(current_dir, 'src')}",
        main_py
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\n[SUCCESS] Build completed successfully!")
        print(f"Single Executable Path: {os.path.join(current_dir, 'dist', 'ChuguiMaster-Single.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build failed: {e}")

if __name__ == '__main__':
    build_exe()
