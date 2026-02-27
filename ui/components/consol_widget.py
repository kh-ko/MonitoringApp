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
from PySide6.QtWidgets import QTextEdit
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QColor, QTextCursor

# 1. 메세지 타입을 정의하는 Enum 클래스
class MsgType(Enum):
    INFO = auto()
    ERROR = auto()
    WARNING = auto()
    TX = auto()
    RX = auto()

class ConsoleWidget(QTextEdit):
    # 스레드 안전하게 메세지를 전달하기 위한 시그널 정의
    _message_signal = Signal(MsgType, str)

    # 메세지 타입별 색상 매핑 (검은 배경에 잘 보이도록 밝은 톤 적용)
    COLOR_MAP = {
        MsgType.INFO: "#00FF00",     # 초록색
        MsgType.ERROR: "#FF3333",    # 빨간색 (가독성을 위해 약간 밝게)
        MsgType.WARNING: "#FFFF00",  # 노란색
        MsgType.TX: "#3399FF",       # 파란색 (가독성을 위해 밝은 파랑)
        MsgType.RX: "#CC66FF",       # 보라색 (가독성을 위해 밝은 보라)
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 기본 UI 설정
        self.setReadOnly(True)  # 사용자 직접 입력 방지
        self.setStyleSheet("""
            QTextEdit {
                background-color: black;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                padding: 5px;
            }
        """)

        # 4. 기능 4: 전체 메세지 내용은 최근 3000줄로 제한 (메모리 과사용 방지)
        self.document().setMaximumBlockCount(3000)

        # 현재 허용된 메세지 타입 필터 (기본적으로 모두 허용)
        self._allowed_filters = {MsgType.INFO, MsgType.ERROR, MsgType.WARNING, MsgType.TX, MsgType.RX}

        # 시그널과 슬롯 연결 (스레드 간 통신을 위해 내부적으로 QueuedConnection 처리됨)
        self._message_signal.connect(self._append_message_slot)

    # 4. 기능 1: 메세지 추가 (외부 스레드에서 호출 가능한 API)
    def add_message(self, msg_type: MsgType, message: str):
        """
        메세지를 추가합니다. 어떤 스레드에서 호출하든 안전하게 UI에 반영됩니다.
        """
        # 직접 UI를 수정하지 않고 시그널을 발생시켜 UI 스레드로 전달
        self._message_signal.emit(msg_type, message)

    # 4. 기능 2: 모든 메세지 삭제 API
    def clear_message(self):
        """현재 창에 표시된 모든 메세지를 삭제합니다."""
        self.clear()

    # 4. 기능 3: 메세지 필터링 API
    def filter_message(self, allowed_types: list[MsgType]):
        """
        새로 추가되는 메세지에 대한 필터를 설정합니다.
        (예: [MsgType.ERROR, MsgType.WARNING] 만 전달하면 두 가지만 출력됨)
        """
        self._allowed_filters = set(allowed_types)

    # 실제 UI에 메세지를 그리는 내부 슬롯 함수 (항상 UI 스레드에서 실행됨)
    @Slot(MsgType, str)
    def _append_message_slot(self, msg_type: MsgType, message: str):
        # 1. 필터링 검사: 현재 허용된 타입이 아니면 무시
        if msg_type not in self._allowed_filters:
            return

        # 2. 색상 가져오기
        color_hex = self.COLOR_MAP.get(msg_type, "#FFFFFF") # 기본값 흰색

        # 3. HTML 형태로 포맷팅하여 추가
        # 개행 문자를 <br>로 변경하여 HTML 구조 안에서 줄바꿈이 정상 작동하도록 처리
        safe_message = message.replace('\n', '<br>')
        html_text = f'<span style="color: {color_hex};">[{msg_type.name}] {safe_message}</span>'
        
        self.append(html_text)
        
        # 스크롤을 항상 가장 아래로 이동
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)