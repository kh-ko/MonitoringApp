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

from enum import Enum, auto
from PySide6.QtWidgets import QListWidget, QListWidgetItem
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QColor, QFont

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
        self._message_signal.connect(self._append_message_slot)

    def add_message(self, msg_type: MsgType, message: str):
        self._message_signal.emit(msg_type, message)

    def clear_message(self):
        self.clear()

    def filter_message(self, allowed_types: list[MsgType]):
        self._allowed_filters = set(allowed_types)

    @Slot(MsgType, str)
    def _append_message_slot(self, msg_type: MsgType, message: str):
        if msg_type not in self._allowed_filters:
            return

        # 1. 리스트의 개별 항목(Item) 생성
        display_text = f"[{msg_type.name}] {message}"
        item = QListWidgetItem(display_text)
        
        # 2. 색상 적용 (HTML을 쓰지 않고 아이템 자체의 글자색을 변경하여 성능 극대화)
        color_hex = self.COLOR_MAP.get(msg_type, "#FFFFFF")
        item.setForeground(QColor(color_hex))
        
        # 3. 리스트에 아이템 추가
        self.addItem(item)
        
        # 4. 최대 줄 수 제한 (예: 2만 줄)
        # 2만 줄이 넘어가면 가장 오래된 첫 번째 줄을 삭제하여 메모리 관리
        if self.count() > 20000:
            taken_item = self.takeItem(0)
            del taken_item
            
        # 5. 최하단으로 자동 스크롤
        self.scrollToBottom()