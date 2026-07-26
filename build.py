import os
import subprocess
import sys

def build_exe():
    print("[ChuguiMaster] Executable (.exe) Build Starting...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    main_py = os.path.join(current_dir, 'main.py')
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",          # 빠른 실행 및 호환성을 위한 디렉터리 배포
        "--windowed",        # GUI 전용
        "--name=ChuguiMaster",
        f"--paths={os.path.join(current_dir, 'src')}",
        main_py
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\n[SUCCESS] Build completed successfully!")
        print(f"Path: {os.path.join(current_dir, 'dist', 'ChuguiMaster', 'ChuguiMaster.exe')}")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build failed: {e}")

if __name__ == '__main__':
    build_exe()
