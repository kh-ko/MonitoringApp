from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import FluentWidget, FluentIcon as FIF, TitleLabel, ComboBox, PushButton

# 기존에 작성하신 콘솔 위젯 임포트
from ui.components.console_widget import ConsoleWidget
# USB 캡처 서비스 임포트
from core.usb_sniff_service import UsbSniffService

class HomeWindow(FluentWidget):
    def __init__(self):
        super().__init__()
        
        # 기본 창 설정
        self.setWindowTitle("USB Packet Sniffer - Home")
        self.resize(1024, 768)

        # 메인 레이아웃 구성
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 48, 10, 10)

        # 상단 타이틀 레이블
        self.title_label = TitleLabel("USB Packet Monitor", self)
        self.main_layout.addWidget(self.title_label)

        # 컨트롤 패널 (인터페이스 선택, 시작, 중지 버튼) 구성
        self.control_layout = QHBoxLayout()
        
        self.interface_combo = ComboBox(self)
        self.interface_combo.setPlaceholderText("캡처할 USB 인터페이스를 선택하세요")
        self.interface_combo.setMinimumWidth(400)
        
        self.start_btn = PushButton(FIF.PLAY, "캡처 시작", self)
        self.stop_btn = PushButton(FIF.PAUSE, "캡처 중지", self)
        self.stop_btn.setEnabled(False) # 처음에는 중지 버튼 비활성화
        
        self.control_layout.addWidget(self.interface_combo)
        self.control_layout.addWidget(self.start_btn)
        self.control_layout.addWidget(self.stop_btn)
        self.control_layout.addStretch(1) # 우측 여백 확보
        
        self.main_layout.addLayout(self.control_layout)

        # 콘솔 위젯 추가
        self.console = ConsoleWidget(self)
        self.main_layout.addWidget(self.console)
        
        # 창 아이콘 설정
        self.setWindowIcon(FIF.HOME.icon())
        
        # 1. USB Sniff Service 초기화 및 콘솔 연결
        self.sniffer = UsbSniffService()
        self.sniffer.set_console_widget(self.console)
        
        # 2. 인터페이스 목록 불러오기
        self.load_interfaces()
        
        # 3. 버튼 이벤트 연결
        self.start_btn.clicked.connect(self.start_capture)
        self.stop_btn.clicked.connect(self.stop_capture)

    def load_interfaces(self):
        """tshark를 통해 사용 가능한 USBPcap 인터페이스 목록을 로드하여 콤보박스에 추가합니다."""
        try:
            interfaces = self.sniffer.get_interfaces()
            for full_name, short_name in interfaces:
                # 콤보박스에는 전체 이름을 보여주고, 내부 데이터로 short_name을 저장합니다.
                self.interface_combo.addItem(full_name, userData=short_name)
        except Exception as e:
            from ui.components.console_widget import MsgType
            self.console.add_message(MsgType.ERROR, f"인터페이스 로드 실패: {str(e)}")

    def start_capture(self):
        """선택된 인터페이스로 패킷 캡처를 시작합니다."""
        selected_interface = self.interface_combo.currentData()
        
        if not selected_interface:
            from ui.components.console_widget import MsgType
            self.console.add_message(MsgType.WARNING, "캡처할 인터페이스를 먼저 선택해주세요.")
            return
            
        self.sniffer.start_capture(selected_interface)
        
        # UI 상태 업데이트
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.interface_combo.setEnabled(False)

    def stop_capture(self):
        """패킷 캡처를 중지합니다."""
        self.sniffer.stop_capture()
        
        # UI 상태 복구
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.interface_combo.setEnabled(True)

    def closeEvent(self, event):
        """프로그램 종료 시 백그라운드에 tshark 프로세스가 남지 않도록 안전하게 종료합니다."""
        if self.sniffer.is_capturing:
            self.sniffer.stop_capture()
        super().closeEvent(event)