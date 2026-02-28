# 1.개요 : USB 패킷을 캡처하는 서비스
# 2.특징 :  UI쓰레드에서만 API 호출 가능하도록 설계함. 싱글 톤이지만 Lock 구조를 사용하지 않음.
# 3.사용법 : 
## 1) UsbSniffService()로 인스턴스 생성 - 싱글톤 클래스이므로 어디서 호출하든 같은 인스턴스 반환
## 2) get_interfaces()로 인터페이스 목록 조회
## 3) start_capture(interface_name)으로 캡처 시작 - 쓰레드 시작
## 4) stop_capture()로 캡처 중지 - 캡쳐 중지및 쓰레드 중지

import threading
import subprocess
import re
from enum import Enum

# console_widget.py 파일에서 MsgType만 임포트합니다.
from ui.components.console_widget import MsgType

# 🚀 캡처 필터용 Enum 정의 (다중 선택 가능)
class UsbFilter(Enum):
    ALL = "ALL"
    SERIAL = "SERIAL"
    HID = "HID"
    STORAGE = "STORAGE"
    OTHER = "OTHER"

class UsbSniffService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, tshark_path=r'C:\Program Files\Wireshark\tshark.exe'):
        if getattr(self, '_initialized', False):
            return
            
        self.tshark_path = tshark_path
        self.is_capturing = False
        self.capture_thread = None
        self.capture_process = None
        
        self.console_widget = None 
        self._initialized = True

    def set_console_widget(self, widget):
        self.console_widget = widget

    def get_interfaces(self):
        interfaces = []
        try:
            result = subprocess.run([self.tshark_path, '-D'], capture_output=True, text=True, encoding='utf-8')
            for line in result.stdout.splitlines():
                if 'USBPcap' in line:
                    words = line.split()
                    for word in words:
                        if 'USBPcap' in word:
                            short_name = word.split('\\')[-1]
                            interfaces.append((line, short_name))
                            break
            return interfaces
        except FileNotFoundError:
            raise FileNotFoundError("tshark.exe를 찾을 수 없습니다. 경로를 확인해 주세요.")

    # 🚀 protocol_filters를 리스트(List) 형태로 받도록 변경
    def start_capture(self, interface_name, protocol_filters: list = None):
        if self.is_capturing:
            self._log(MsgType.WARNING, "이미 캡처가 진행 중입니다.")
            return

        # 필터가 명시되지 않으면 ALL로 간주
        if not protocol_filters:
            protocol_filters = [UsbFilter.ALL]

        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._sniff_worker, args=(interface_name, protocol_filters))
        self.capture_thread.daemon = True
        self.capture_thread.start()

    def _log(self, msg_type: MsgType, message: str):
        if self.console_widget and hasattr(self.console_widget, 'add_message'):
            self.console_widget.add_message(msg_type, message)
        else:
            print(f"[{msg_type.name}] {message}")

    def _log_file(self, msg_type: MsgType, message: str):
        # 화면 출력(UI 업데이트)은 _log에서 처리하므로 여기서는 파일만 기록
        log_filename = "usb_capture_log.txt"
        try:
            with open(log_filename, "a", encoding="utf-8") as f:
                f.write(f"[{msg_type.name}] {message}\n")
        except Exception as e:
            print(f"파일 쓰기 실패: {e}")

    # 🚀 다중 필터 로직을 반영한 _sniff_worker
    def _sniff_worker(self, interface_name, protocol_filters: list):
        # 💡 1. 블랙리스트: 데이터 해석을 방해하는 디섹터들을 몽땅 끕니다.
        disable_protocols = {
            'usbhid', 'usbms', 'scsi', 'ftdi-ft'
        }

        # 💡 2. 명령어 세팅: 디섹터를 껐으므로 -e 옵션이 엄청나게 심플해집니다!
        cmd = [
            self.tshark_path, '-l', '-i', interface_name,
            '-T', 'fields',
            '-e', 'frame.time',
            '-e', 'frame.len',
            '-e', '_ws.col.Protocol',               # 디섹터를 껐으므로 대부분 "USB" 또는 "URB"로 찍힙니다.
            '-e', '_ws.col.Info',                   # 상세 정보 대신 "URB_BULK in" 형태의 기본 정보가 찍힙니다.
            '-e', 'usb.endpoint_address.direction', # 🌟 완벽한 TX/RX 판별용 (0:OUT, 1:IN)
            '-e', 'usb.capdata',                    # 🌟 모든 데이터가 모이는 방
            '-e', 'data.data',                      # 혹시 모를 기타 데이터
            '-e', 'usb.data_fragment',              # 조각난 패킷 데이터
        ]

        # 💡 3. tshark 디스플레이 필터(-Y) 하드웨어 기반 세팅
        filter_conditions = []
        
        if UsbFilter.ALL not in protocol_filters:
            if UsbFilter.HID in protocol_filters:
                # 인터럽트 전송(0x01)이거나 인터페이스 클래스가 HID(3)인 경우
                filter_conditions.append("(usb.transfer_type == 0x01 || usb.bInterfaceClass == 3)")
                
            if UsbFilter.STORAGE in protocol_filters:
                # 대용량 저장장치 클래스(8)인 경우
                filter_conditions.append("(usb.bInterfaceClass == 8)")
                
            if UsbFilter.SERIAL in protocol_filters:
                # 시리얼 장치는 주로 벌크 전송(0x03)을 사용합니다.
                # (주의: 디섹터를 끄면 벤더별 시리얼을 완벽히 특정하기 어려워 벌크 전송 전체를 잡습니다)
                filter_conditions.append("(usb.transfer_type == 0x03)")

        # OR 연산자로 필터 묶기
        display_filter_str = " || ".join(filter_conditions)
        if display_filter_str:
            cmd.extend(['-Y', display_filter_str])

        # 블랙리스트 옵션을 명령어에 추가
        for proto in disable_protocols:
            cmd.extend(['--disable-protocol', proto])

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.capture_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', startupinfo=startupinfo
            )
            
            filter_names = ", ".join([f.name for f in protocol_filters])
            self._log(MsgType.INFO, f"--- [{interface_name}] 블랙리스트 방식 패킷 캡처 시작 (필터: {filter_names}) ---")

            for line in self.capture_process.stdout:
                if not self.is_capturing:
                    break
                
                line = line.strip()
                if not line or line.startswith("Capturing on"):
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    frame_time = parts[0]
                    time_match = re.search(r'(\d{2}:\d{2}:\d{2}\.\d{3})', frame_time)
                    if time_match:
                        frame_time = time_match.group(1)

                    length = parts[1]
                    protocol = parts[2].upper() if len(parts) > 2 else "UNKNOWN"
                    info = parts[3] if len(parts) > 3 else "No Info"
                    direction_flag = parts[4] if len(parts) > 4 else ""

                    # 💡 4. 데이터 추출: 인덱스 5, 6, 7 (-e usb.capdata 등)에서 첫 번째 데이터 가져오기
                    payload_candidates = [p for p in parts[5:] if p.strip()]
                    raw_hex_data = payload_candidates[0] if payload_candidates else ""
                    
                    if raw_hex_data and ',' in raw_hex_data:
                        raw_hex_data = raw_hex_data.split(',')[0]

                    ascii_data = ""
                    clean_hex = ""

                    if raw_hex_data:
                        clean_hex = raw_hex_data.replace(':', '')
                        
                        is_truncated = False
                        if len(clean_hex) > 2000:
                            clean_hex = clean_hex[:2000]
                            is_truncated = True
                            
                        if len(clean_hex) % 2 != 0:
                            clean_hex = clean_hex[:-1]
                            
                        try:
                            decoded_bytes = bytes.fromhex(clean_hex)
                            ascii_data = decoded_bytes.decode('ascii', errors='replace')
                            # 제어 문자 필터링
                            ascii_data = ''.join([c if 32 <= ord(c) < 127 else '.' for c in ascii_data])
                            
                            if is_truncated:
                                ascii_data += "..."
                        except Exception as e:
                            ascii_data = f"[Decode Error: {e}]"

                    # 💡 5. 완벽한 TX/RX 판별 및 출력
                    # 데이터가 있을 때만 Data 항목을 문자열에 추가합니다.
                    msg = f"Time: {frame_time} | Len: {length} | Proto: {protocol} | Info: {info}"
                    if ascii_data:
                        msg += f" | Data(ASCII): {ascii_data}"
                    
                    if direction_flag == "0" or (not direction_flag and 'out' in info.lower()):
                        self._log(MsgType.TX, msg)
                    elif direction_flag == "1" or (not direction_flag and 'in' in info.lower()):
                        self._log(MsgType.RX, msg)
                    else:
                        self._log(MsgType.RX, msg)

            if self.is_capturing and self.capture_process:
                err_msg = self.capture_process.stderr.read()
                if err_msg:
                    self._log(MsgType.ERROR, f"tshark 에러: {err_msg.strip()}")

        except Exception as e:
            self._log(MsgType.ERROR, f"파이썬 에러: {e}")
        finally:
            self._cleanup()

    def stop_capture(self):
        self.is_capturing = False
        if self.capture_process and self.capture_process.poll() is None:
            try:
                # Windows 환경: /F (강제 종료), /T (하위 프로세스 트리까지 모두 종료)
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.capture_process.pid)], capture_output=True)
            except Exception as e:
                self._log(MsgType.ERROR, f"프로세스 종료 오류: {e}")

    def _cleanup(self):
        if self.capture_process and self.capture_process.poll() is None:
            try:
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.capture_process.pid)], capture_output=True)
            except Exception:
                pass
        self._log(MsgType.INFO, "--- 캡처 중지됨 ---")