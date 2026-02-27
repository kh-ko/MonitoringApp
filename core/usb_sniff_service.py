# 1.개요 : USB 패킷을 캡처하는 서비스
# 2.특징 :  UI쓰레드에서만 API 호출 가능하도록 설계함. 싱글 톤이지만 Lock 구조를 사용하지 않음.
# 3.사용법 : 
## 1) UsbSniffService()로 인스턴스 생성 - 싱글톤 클래스이므로 어디서 호출하든 같은 인스턴스 반환
## 2) get_interfaces()로 인터페이스 목록 조회
## 3) start_capture(interface_name)으로 캡처 시작 - 쓰레드 시작
## 4) stop_capture()로 캡처 중지 - 캡쳐 중지및 쓰레드 중지

import threading
import subprocess
import re # 정규표현식 모듈 추가

# console_widget.py 파일에서 MsgType만 임포트합니다.
from ui.components.console_widget import MsgType

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

    def start_capture(self, interface_name):
        if self.is_capturing:
            self._log(MsgType.WARNING, "이미 캡처가 진행 중입니다.")
            return

        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._sniff_worker, args=(interface_name,))
        self.capture_thread.daemon = True
        self.capture_thread.start()

    def _log(self, msg_type: MsgType, message: str):
        if self.console_widget and hasattr(self.console_widget, 'add_message'):
            self.console_widget.add_message(msg_type, message)
        else:
            print(f"[{msg_type.name}] {message}")

    def _sniff_worker(self, interface_name):
        cmd = [
            self.tshark_path, '-l', '-i', interface_name,
            '-T', 'fields',
            '-e', 'frame.time',
            '-e', 'frame.len',
            '-e', '_ws.col.Protocol',
            '-e', '_ws.col.Info',
            '-e', 'usb.capdata',
            '-e', 'usb.data'
        ]
        
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.capture_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', startupinfo=startupinfo
            )
            
            self._log(MsgType.INFO, f"--- [{interface_name}] 캡처 시작 ---")

            for line in self.capture_process.stdout:
                if not self.is_capturing:
                    break
                
                line = line.strip()
                if not line or line.startswith("Capturing on"):
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    frame_time = parts[0]
                    
                    # [추가된 부분] 정규식을 사용해 'HH:MM:SS.mmm' (시:분:초.밀리초) 형태만 추출
                    time_match = re.search(r'(\d{2}:\d{2}:\d{2}\.\d{3})', frame_time)
                    if time_match:
                        frame_time = time_match.group(1)

                    length = parts[1]
                    protocol = parts[2] if len(parts) > 2 else "Unknown"
                    info = parts[3] if len(parts) > 3 else "No Info"
                    
                    # 2. [추가됨] 실제 데이터 추출
                    capdata = parts[4] if len(parts) > 4 else ""
                    usb_data = parts[5] if len(parts) > 5 else ""
                    
                    # 프로토콜 해석 여부에 따라 둘 중 하나에 값이 들어감
                    actual_hex_data = capdata if capdata else usb_data
                    
                    ascii_data = ""
                    clean_hex = ""

                    if actual_hex_data:
                        # tshark 버전에 따라 콜론(:) 구분자가 들어갈 수 있으므로 제거
                        # clean_hex = actual_hex_data.replace(':', '')
                        clean_hex = actual_hex_data
                        
                        # [최적화] 디코딩 전에 미리 자르기 (1글자 = 1바이트 = Hex 2자리)
                        is_truncated = False
                        if len(clean_hex) > 2000:
                            clean_hex = clean_hex[:2000]
                            is_truncated = True
                            
                        if len(clean_hex) % 2 != 0:
                            clean_hex = clean_hex[:-1]
                            
                        try:
                            decoded_bytes = bytes.fromhex(clean_hex)
                            ascii_data = decoded_bytes.decode('ascii', errors='replace')
                            
                            if is_truncated:
                                ascii_data += "..."
                                
                        except Exception as e:
                            ascii_data = f"[Hex Decode Error: {e}]"

                    data_str = f" | Data(ASCII): {ascii_data}" if ascii_data else ""
                    
                    msg = f"Time: {frame_time} | Len: {length} | Proto: {protocol} | Info: {info}{data_str}"
                    self._log(MsgType.RX, msg)
                        
        except Exception as e:
            self._log(MsgType.ERROR, f"캡처 중 에러 발생: {e}")
        finally:
            self._cleanup()

    def stop_capture(self):
        self.is_capturing = False
        if self.capture_process and self.capture_process.poll() is None:
            self.capture_process.terminate()
            self.capture_process.wait()

    def _cleanup(self):
        if self.capture_process and self.capture_process.poll() is None:
            self.capture_process.terminate()
        self._log(MsgType.INFO, "--- 캡처 중지됨 ---")