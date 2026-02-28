#1. 개요: App내에 여러 콘솔 출력 메세지를 표시하기 위한 커스텀 컴포넌트 위젯

#2. 디자인:
## 1) 검은 화면에 메세지 종류에 따라 색상을 다르게 표시한다. (INFO: 초록색, ERROR: 빨간색, WARNING: 노란색, 통신 TX: 파란색, 통신 RX: 보라색)

#3. 구현:
## 1) ui스레드가 아닌 다른 서비스 쓰레드에서 메세지를 추가할 수 있도록 스레드 안전하게 메세지를 추가하는 기능을 구현한다.
## 2) PySide6 + qFluentWidget을 사용한다.
### - 패키지 설치 : pip install pyside6 pyqt-fluent-widget
## 3) QListWidget 상속받아 구현한다.
## 4) 메세지 종류에 따라 색상을 다르게 표시한다.

#4. 기능(API + UI):
## 1) 메세지를 추가한다. (add_message)
## 2) 현재 창에 표시된 모든 메세지를 삭제한다. (clear_message)
## 3) 메세지를 필터링한다. (filter_message)
### - 이전까지 출력된 메세지에는 적용되지 않으며, 새로 추가되는 메세지에 대해 적용할 필터를 설정한다.
## 4) 전체 메세지 내용은 최근 20000줄로 제한된다. (메모리가 과 사용을 방지하기 위해 오래된 메세지는 삭제하여 메모리가 과 사용 되지 않도록 조정)

#테스트
import queue
from enum import Enum, auto
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QListWidget, QListWidgetItem)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont

# qFluentWidget에서 CheckBox 임포트
from qfluentwidgets import CheckBox  

class MsgType(Enum):
    INFO = auto()
    ERROR = auto()
    WARNING = auto()
    TX = auto()
    RX = auto()

class ConsoleWidget(QWidget):  # 기존 QListWidget 대신 QWidget 상속으로 변경
    MAX_LINES = 20000

    COLOR_MAP = {
        MsgType.INFO: "#00FF00",     
        MsgType.ERROR: "#FF3333",    
        MsgType.WARNING: "#FFFF00",  
        MsgType.TX: "#3399FF",       
        MsgType.RX: "#CC66FF",       
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._allowed_filters = set(MsgType)  # 초기에는 모든 필터 허용
        
        self._init_ui()
        
        # 스레드 안전한 큐 생성
        self.msg_queue = queue.Queue()
        
        # 타이머를 이용한 일괄(Batch) 업데이트 설정
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._process_message_queue)
        self.update_timer.start(100)

    def _init_ui(self):
        # 1. 메인 레이아웃 (수직)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 2. 상단 필터 레이아웃 (수평)
        self.filter_layout = QHBoxLayout()
        self.filter_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # 체크박스들을 딕셔너리에 저장하여 관리
        self.checkboxes = {}
        for msg_type in MsgType:
            cb = CheckBox(msg_type.name, self)
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_filters_from_ui)
            
            self.filter_layout.addWidget(cb)
            self.checkboxes[msg_type] = cb
            
        # 3. 하단 로그 리스트 위젯 (기존 로직 이동)
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: black;
                padding: 5px;
                border: 1px solid #333333; /* 위젯 구분을 위한 테두리 추가 */
            }
            QListWidget::item {
                padding: 2px;
            }
        """)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.list_widget.setFont(font)
        self.list_widget.setWordWrap(False) 

        # 레이아웃 조립
        self.main_layout.addLayout(self.filter_layout)
        self.main_layout.addWidget(self.list_widget)

    def _update_filters_from_ui(self):
        """UI의 체크박스 상태가 변경될 때 내부 필터 셋을 업데이트합니다."""
        new_filters = {msg_type for msg_type, cb in self.checkboxes.items() if cb.isChecked()}
        self._allowed_filters = new_filters

    # ------------------ API 기능 ------------------

    def add_message(self, msg_type: MsgType, message: str):
        self.msg_queue.put((msg_type, message))

    def clear_message(self):
        self.list_widget.clear()
        # 큐도 함께 비워줌 (Thread-safe clear)
        with self.msg_queue.mutex:
            self.msg_queue.queue.clear()

    # ------------------ 내부 큐 처리 ------------------

    def _process_message_queue(self):
        if self.msg_queue.empty():
            return

        scrollbar = self.list_widget.verticalScrollBar()
        is_scrolled_to_bottom = (self.list_widget.count() == 0) or (scrollbar.value() == scrollbar.maximum())

        # 렌더링 부하 억제
        self.list_widget.setUpdatesEnabled(False)
        
        added_count = 0
        while not self.msg_queue.empty() and added_count < 1000:
            try:
                msg_type, message = self.msg_queue.get_nowait()
            except queue.Empty:
                break
                
            # 요구사항: 큐에서 꺼낼 때 필터를 확인하므로 이전 메세지는 그대로 둠
            if msg_type not in self._allowed_filters:
                continue

            display_text = f"[{msg_type.name}] {message}"
            item = QListWidgetItem(display_text)
            color_hex = self.COLOR_MAP.get(msg_type, "#FFFFFF")
            item.setForeground(QColor(color_hex))
            
            self.list_widget.addItem(item)
            added_count += 1

        # 변수화된 max_lines(기본 20000)를 활용한 제한 처리
        excess = self.list_widget.count() - self.MAX_LINES
        if excess > 0:
            for _ in range(excess):
                taken_item = self.list_widget.takeItem(0)
                del taken_item

        self.list_widget.setUpdatesEnabled(True)

        if is_scrolled_to_bottom and added_count > 0:
            self.list_widget.scrollToBottom()