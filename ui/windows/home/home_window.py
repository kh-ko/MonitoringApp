from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import FluentWidget, FluentIcon as FIF, TitleLabel
from ui.components.consol_widget import ConsoleWidget

class HomeWindow(FluentWidget):
    def __init__(self):
        super().__init__()
        
        # 기본 창 설정 (FluentWidget은 기본적으로 프레임리스 윈도우 기능 포함)
        self.setWindowTitle("USB Packet Sniffer - Home")
        self.resize(1024, 768)

        # 메인 레이아웃 구성
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 48, 10, 10) # 타이틀바 및 여백 확보

        # 상단 타이틀 레이블
        self.title_label = TitleLabel("USB Packet Monitor", self)
        self.main_layout.addWidget(self.title_label)

        # 콘솔 위젯 추가
        self.console = ConsoleWidget(self)
        self.main_layout.addWidget(self.console)
        
        # 창 아이콘 설정
        self.setWindowIcon(FIF.HOME.icon())