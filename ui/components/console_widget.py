#1. 개요: App내에 여러 콘솔 출력 메세지를 표시하기 위한 커스텀 컴포넌트 위젯

#2. 디자인:
## 1) 검은 화면에 메세지 종류에 따라 색상을 다르게 표시한다. (INFO: 초록색, ERROR: 빨간색, WARNING: 노란색, 통신 TX: 파란색, 통신 RX: 보라색)

#3. 구현:
## 1) ui스레드가 아닌 다른 서비스 쓰레드에서 메세지를 추가할 수 있도록 스레드 안전하게 메세지를 추가하는 기능을 구현한다.
## 2) PySide6 + qFluentWidget을 사용한다.
### - 패키지 설치 : pip install pyside6 pyqt-fluent-widget
## 3) QTextEdit를 상속받아 구현한다.
## 4) 메세지 종류에 따라 색상을 다르게 표시한다.

#4. 기능(API):
## 1) 메세지를 추가한다. (add_message)
## 2) 현재 창에 표시된 모든 메세지를 삭제한다. (clear_message)
## 3) 메세지를 필터링한다. (filter_message)
### - 이전까지 출력된 메세지에는 적용되지 않으며, 새로 추가되는 메세지에 대해 적용할 필터를 설정한다.
## 4) 전체 메세지 내용은 최근 3000줄로 제한된다. (메모리가 과 사용을 방지하기 위해 오래된 메세지는 삭제하여 메모리가 과 사용 되지 않도록 조정)

import queue
from enum import Enum, auto
from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Signal

class MsgType(Enum):
    INFO = auto()
    ERROR = auto()
    WARNING = auto()
    TX = auto()
    RX = auto()

class ConsoleWidget(QListWidget):  # QTextEdit 대신 QListWidget 상속
    _message_signal = Signal(MsgType, str)

    COLOR_MAP = {
        MsgType.INFO: "#00FF00",     
        MsgType.ERROR: "#FF3333",    
        MsgType.WARNING: "#FFFF00",  
        MsgType.TX: "#3399FF",       
        MsgType.RX: "#CC66FF",       
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 기본 UI 설정
        self.setStyleSheet("""
            QListWidget {
                background-color: black;
                padding: 5px;
            }
            QListWidget::item {
                padding: 2px; /* 줄 간격 살짝 띄우기 */
            }
        """)
        
        # 폰트 설정 (QListWidget 전체에 일괄 적용)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        # 단어 잘림 방지 및 가로 스크롤바 생성 허용
        self.setWordWrap(False) 

        self._allowed_filters = {MsgType.INFO, MsgType.ERROR, MsgType.WARNING, MsgType.TX, MsgType.RX}

        # 🚀 [성능 개선 1] 스레드 안전한 큐 생성
        self.msg_queue = queue.Queue()
        
        # 🚀 [성능 개선 2] 타이머를 이용한 일괄(Batch) 업데이트 설정
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._process_message_queue)
        # 100ms(0.1초) 주기로 큐를 확인하여 화면 갱신. (더 부드럽게 하려면 50ms 권장)
        self.update_timer.start(100)

    def add_message(self, msg_type: MsgType, message: str):
        self.msg_queue.put((msg_type, message))

    def clear_message(self):
        self.clear()
        # 큐도 함께 비워줌
        while not self.msg_queue.empty():
            try:
                self.msg_queue.get_nowait()
            except queue.Empty:
                break

    def filter_message(self, allowed_types: list[MsgType]):
        self._allowed_filters = set(allowed_types)

    def _process_message_queue(self):
        """100ms 마다 큐에 쌓인 메세지를 한 번에 UI에 반영합니다."""
        if self.msg_queue.empty():
            return

        # 1. 자동 스크롤 개선 (새 아이템 추가 전 스크롤이 맨 아래에 있었는지 확인)
        scrollbar = self.verticalScrollBar()
        is_scrolled_to_bottom = scrollbar.value() == scrollbar.maximum()

        # 🚀 [성능 개선 3] 대량 추가 시 화면 그리기 연산을 일시 중지하여 렌더링 부하 억제
        self.setUpdatesEnabled(False)
        
        added_count = 0
        # 1회 업데이트 당 최대 1000개씩만 처리하여 UI 스레드가 완전히 멈추는 것을 방지
        while not self.msg_queue.empty() and added_count < 1000:
            try:
                msg_type, message = self.msg_queue.get_nowait()
            except queue.Empty:
                break
                
            if msg_type not in self._allowed_filters:
                continue

            display_text = f"[{msg_type.name}] {message}"
            item = QListWidgetItem(display_text)
            color_hex = self.COLOR_MAP.get(msg_type, "#FFFFFF")
            item.setForeground(QColor(color_hex))
            
            self.addItem(item)
            added_count += 1

        # 🚀 [성능 개선 4] 2만 줄 제한 처리 (한 번에 초과분만큼 일괄 삭제)
        excess = self.count() - 20000
        if excess > 0:
            for _ in range(excess):
                taken_item = self.takeItem(0)
                del taken_item

        # 🚀 화면 그리기 재개
        self.setUpdatesEnabled(True)

        # 2. 이전 상태가 최하단이었을 경우에만 스크롤을 맨 밑으로 내림
        if is_scrolled_to_bottom and added_count > 0:
            self.scrollToBottom()