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

    def _log_file(self, msg_type: MsgType, message: str):
        # 1. 화면 출력(UI 업데이트) 비활성화 - 기존 코드 주석 처리
        # if self.console_widget and hasattr(self.console_widget, 'add_message'):
        #     self.console_widget.add_message(msg_type, message)
        # else:
        #     print(f"[{msg_type.name}] {message}")

        # 2. 파일에 로그 쓰기 (임시 파일명: usb_capture_log.txt)
        log_filename = "usb_capture_log.txt"
        try:
            # 'a' 모드로 열어 기존 내용 끝에 계속 추가되도록 합니다.
            # 한글이나 특수문자 깨짐 방지를 위해 encoding='utf-8'을 지정합니다.
            with open(log_filename, "a", encoding="utf-8") as f:
                f.write(f"[{msg_type.name}] {message}\n")
        except Exception as e:
            print(f"파일 쓰기 실패: {e}")

    def _sniff_worker(self, interface_name):
        cmd = [
            self.tshark_path, '-l', '-i', interface_name,
            '-T', 'fields',
            '-e', 'frame.time',
            '-e', 'frame.len',
            '-e', '_ws.col.Protocol',
            '-e', '_ws.col.Info',
            
            '-e', 'usb.capdata',   # 기본 미확인 USB 데이터
            '-e', 'data.data',     # 기타 미확인 일반 데이터
            '-e', 'tcp.payload',   # TCP 변환 시 페이로드
            '-e', 'udp.payload',   # UDP 변환 시 페이로드
            
            # 기존 프로토콜 해석 중지 옵션들
            '--disable-protocol', 'usbms',
            '--disable-protocol', 'scsi',
            
            # 🚀 핵심 추가: HID(Human Interface Device) 해석 강제 중지
            # 가상 HID 방식을 사용하는 장비의 64바이트 인터럽트 데이터를 원본 그대로 추출합니다.
            '--disable-protocol', 'usbhid'
        ]
        
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.capture_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', startupinfo=startupinfo
            )
            
            self._log(MsgType.INFO, f"--- [{interface_name}] 스마트 패킷 캡처 시작 ---")

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
                    protocol = parts[2] if len(parts) > 2 else "Unknown"
                    info = parts[3] if len(parts) > 3 else "No Info"
                    
                    # 🚀 [핵심 파싱 로직] 4번 인덱스 이후의 모든 필드를 검사해서 빈칸이 아닌 첫 번째 데이터를 채택
                    payload_candidates = [p for p in parts[4:] if p.strip()]
                    raw_hex_data = payload_candidates[0] if payload_candidates else ""
                    
                    if raw_hex_data and ',' in raw_hex_data:
                        raw_hex_data = raw_hex_data.replace(',', '')

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
                            
                            # 제어 문자 필터링이 필요하다면 아래 주석을 해제하세요
                            # ascii_data = ''.join([c if 32 <= ord(c) < 127 else '.' for c in ascii_data])
                            
                            if is_truncated:
                                ascii_data += "..."
                                
                        except Exception as e:
                            ascii_data = f"[Decode Error: {e}]"

                    # 💡 내용이 있는 경우에만 Data를 출력 (Len: 27 패킷은 Data 부분 없이 출력됨)
                    data_str = f" | Data(ASCII): {ascii_data}" if ascii_data else ""
                    
                    msg = f"Time: {frame_time} | Len: {length} | Proto: {protocol} | Info: {info}{data_str}"
                    
                    # Info 항목에 'out'이 포함되어 있으면 송신(TX), 그 외(주로 'in')는 수신(RX)으로 판별
                    if 'out' in info.lower():
                        self._log(MsgType.TX, msg)
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