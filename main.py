import sys
import os
import traceback

# src 경로 추가
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

def global_excepthook(exctype, value, tb):
    """
    프로그램 실행 중 예외 발생 시 튕기지 않고 에러 내용을 팝업창으로 보여주는 글로벌 예외 핸들러
    """
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    print("CRITICAL ERROR:", err_msg)
    
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance():
            QMessageBox.critical(None, "오류 발생", f"프로그램 실행 중 오류가 발생했습니다:\n\n{value}\n\n상세:\n{err_msg[:500]}")
    except Exception:
        pass
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_excepthook

from ui.main_view import main

if __name__ == '__main__':
    main()
