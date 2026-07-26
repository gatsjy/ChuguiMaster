import sys
import os

# src 경로 추가
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from ui.main_view import main

if __name__ == '__main__':
    main()
