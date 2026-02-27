import sys
from PySide6.QtWidgets import QApplication
from ui.windows.home.home_window import HomeWindow

def main():
    # 애플리케이션 객체 생성
    app = QApplication(sys.argv)
    
    # 첫 화면 생성 및 표시
    window = HomeWindow()
    window.show()
    
    # 이벤트 루프 실행 및 종료 안전 처리
    sys.exit(app.exec())

if __name__ == "__main__":
    main()