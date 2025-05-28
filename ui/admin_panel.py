from datetime import datetime
import os
import re
import socket
import subprocess
import sys
import threading
import time
import traceback

import psutil
import wx
import wx.grid
import wx.html2

from ip_middleware import get_local_ips
from ui.config_util import get_config_file, save_json_config
from ui.config_util import load_json_config
from ui.loading_splash import LoadingSplash
from ui.process_util import (
    get_process_using_port,
    is_port_in_use,
    is_process_running,
    kill_process,
    write_pid_to_file,
)
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


MAX_LOG_LINES = 3000

class AdminPanel(wx.Panel):
    def __init__(self, parent, api_client, main_frame_ref, monitoring_daemon=None):
        super().__init__(parent)
        self.api_client = api_client
        self.main_frame_ref = main_frame_ref # Store reference to MainFrame
        self.server_process = None
        self.log_thread = None
        self.stop_event = threading.Event()
        self.log_lines = []
        self.server_pid_file = "server_pid.txt"
        self.server_pid_temp_for_status = None 
        self.server_pid = None  # 현재 서버 PID 저장
        self.current_port = 8123  # 기본 포트 초기화
        self.monitoring_daemon = monitoring_daemon
    
        
        # 프로세스 종료 후 서버 자동 시작 관련 변수
        self._start_server_after_kill = False
        self._port_to_use = None
        
        # For auto-start server readiness detection
        self.server_ready_callback_for_auto_start = None
        self.initial_server_ready_signal_sent = False

        # 로딩 스플래시 관련
        self.loading_splash = None  # 서버 시작 시 표시될 스플래시 창

        vbox = wx.BoxSizer(wx.VERTICAL)

        # 서버 제어 섹션
        server_control_static_box = wx.StaticBox(self, label="서버 제어 및 포트 관리")
        server_control_sizer = wx.StaticBoxSizer(server_control_static_box, wx.VERTICAL)
        
        # 서버 시작/종료 버튼
        server_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start_server = wx.Button(self, label='서버 시작')
        self.btn_stop_server = wx.Button(self, label='서버 종료')
        self.btn_stop_server.Disable() 

        server_buttons_sizer.Add(self.btn_start_server, 1, wx.RIGHT, 5)
        server_buttons_sizer.Add(self.btn_stop_server, 1, wx.LEFT, 5)
        server_control_sizer.Add(server_buttons_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # 구분선 추가
        separator = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        server_control_sizer.Add(separator, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        
        # 포트 충돌 관리 섹션 추가 (레이블 추가)
        port_title = wx.StaticText(self, label="포트 충돌 확인 및 해결")
        port_title.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        server_control_sizer.Add(port_title, 0, wx.ALL, 5)
        
        port_conflict_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.port_input = wx.TextCtrl(self, value="8123", size=(60, -1))
        self.btn_check_port = wx.Button(self, label='포트 확인')
        self.btn_kill_process = wx.Button(self, label='프로세스 종료')
        self.btn_kill_process.Disable()  # 처음에는 비활성화
        
        port_conflict_sizer.Add(wx.StaticText(self, label="포트:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        port_conflict_sizer.Add(self.port_input, 0, wx.RIGHT, 5)
        port_conflict_sizer.Add(self.btn_check_port, 1, wx.RIGHT, 5)
        port_conflict_sizer.Add(self.btn_kill_process, 1)
        server_control_sizer.Add(port_conflict_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # 구분선 추가
        separator2 = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        server_control_sizer.Add(separator2, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        
        self.txt_server_status = wx.StaticText(self, label="서버 상태: 알 수 없음")
        server_control_sizer.Add(self.txt_server_status, 0, wx.EXPAND | wx.ALL, 5)
        
        vbox.Add(server_control_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # 시스템 모니터링 섹션
        monitoring_static_box = wx.StaticBox(self, label="시스템 모니터링")
        monitoring_sizer = wx.StaticBoxSizer(monitoring_static_box, wx.VERTICAL)
        
        # 모니터링 컨트롤
        monitoring_controls = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start_monitoring = wx.Button(self, label='모니터링 시작')
        self.btn_stop_monitoring = wx.Button(self, label='모니터링 중지')
        self.btn_stop_monitoring.Disable()
        
        self.monitoring_thread = None
        self.monitoring_interval = 10  # 초기 모니터링 간격 (초)
        monitoring_interval_label = wx.StaticText(self, label="모니터링 간격(초):")
        self.monitoring_interval_input = wx.TextCtrl(self, value=str(self.monitoring_interval), style=wx.TE_PROCESS_ENTER)
        
        monitoring_controls.Add(self.btn_start_monitoring, 0, wx.RIGHT, 5)
        monitoring_controls.Add(self.btn_stop_monitoring, 0, wx.RIGHT, 5)
        monitoring_controls.Add(monitoring_interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        monitoring_controls.Add(self.monitoring_interval_input, 0, wx.RIGHT, 5)
        
        monitoring_sizer.Add(monitoring_controls, 0, wx.ALL | wx.EXPAND, 5)
        
        # 실행 결과 표시
        result_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 실행 결과 제목
        # result_title = wx.StaticText(self, label="# 실행 결과")
        # result_title.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        # result_sizer.Add(result_title, 0, wx.ALL, 5)
        
        # 시작 ~ 종료 시간
        self.txt_time_period = wx.StaticText(self, label="- 시작 - 종료 시간: 아직 시작되지 않음")
        result_sizer.Add(self.txt_time_period, 0, wx.ALL, 5)
        
        # 걸린 시간
        self.txt_duration = wx.StaticText(self, label="- 걸린 시간: 0시간 0분 0초")
        result_sizer.Add(self.txt_duration, 0, wx.ALL, 5)
        
        # 파일 목록 헤더
        file_list_header = wx.StaticText(self, label="- 파일 변경 감지 결과:")
        result_sizer.Add(file_list_header, 0, wx.ALL, 5)
        
        # 추가/수정/삭제된 파일 목록을 표시할 텍스트 컨트롤
        self.txt_file_changes = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL, size=(-1, 100))
        result_sizer.Add(self.txt_file_changes, 1, wx.ALL | wx.EXPAND, 5)
        
        monitoring_sizer.Add(result_sizer, 1, wx.ALL | wx.EXPAND, 5)
        
        vbox.Add(monitoring_sizer, 0, wx.ALL | wx.EXPAND, 10)

        log_static_box = wx.StaticBox(self, label="Server Logs")
        log_box_sizer = wx.StaticBoxSizer(log_static_box, wx.VERTICAL)

        self.log_text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        log_box_sizer.Add(self.log_text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        
        vbox.Add(log_box_sizer, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(vbox)

        self.btn_start_server.Bind(wx.EVT_BUTTON, self.on_start_server)
        self.btn_stop_server.Bind(wx.EVT_BUTTON, self.on_stop_server)
        self.btn_check_port.Bind(wx.EVT_BUTTON, self.on_check_port)
        self.btn_kill_process.Bind(wx.EVT_BUTTON, self.on_kill_process)
        self.btn_start_monitoring.Bind(wx.EVT_BUTTON, self.on_start_monitoring)
        self.btn_stop_monitoring.Bind(wx.EVT_BUTTON, self.on_stop_monitoring)
        self.monitoring_interval_input.Bind(wx.EVT_TEXT_ENTER, self.on_monitoring_interval_changed)
        
        # 모니터링 타이머
        self.monitoring_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_monitoring_timer, self.monitoring_timer)
            
    def _show_port_change_dialog(self):
        """포트 충돌 시 프로세스 종료 또는 다른 포트 선택 옵션을 제공하는 대화상자를 표시합니다."""
        # 기본 포트 정보
        default_port = 8123
        default_next_port = 8124
        
        # 현재 포트를 사용 중인 프로세스 정보 가져오기
        process_info = get_process_using_port(default_port)
        
        # 커스텀 대화상자 생성
        dlg = wx.Dialog(self, title="포트 충돌", size=(450, 320))
        
        # 대화상자 레이아웃
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 아이콘 및 메시지 패널
        info_panel = wx.Panel(dlg)
        info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # 경고 아이콘 추가
        info_icon = wx.StaticBitmap(info_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_WARNING, wx.ART_MESSAGE_BOX))
        info_sizer.Add(info_icon, 0, wx.ALL | wx.CENTER, 10)
        
        # 메시지 텍스트
        message_text = f"기존 포트({default_port})가 이미 사용 중이거나, 사용 중인 프로세스를 확인할 수 없습니다.\n다른 포트를 선택해주세요."
        
        # 프로세스 정보가 있으면 추가
        if process_info:
            message_text += f"\n\n포트 {default_port}를 사용 중인 프로세스:\n"
            message_text += f"PID: {process_info['pid']}\n"
            message_text += f"프로세스 이름: {process_info['name']}\n"
            message_text += f"생성 시간: {process_info['create_time']}\n"
            process_info_text = f"PID: {process_info['pid']}\n"
            process_info_text += f"프로세스 이름: {process_info['name']}\n"
            process_info_text += f"생성 시간: {process_info['create_time']}\n"
            process_info_text += f"명령어: {process_info['cmd']}"
            message_text += process_info_text
        
        message = wx.StaticText(info_panel, label=message_text)
        info_sizer.Add(message, 1, wx.ALL | wx.EXPAND, 10)
        
        info_panel.SetSizer(info_sizer)
        main_sizer.Add(info_panel, 0, wx.ALL | wx.EXPAND, 5)
        
        # 구분선 추가
        main_sizer.Add(wx.StaticLine(dlg), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # 포트 입력 패널
        port_panel = wx.Panel(dlg)
        port_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        port_label = wx.StaticText(port_panel, label="다른 포트 번호:")
        port_sizer.Add(port_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        self.new_port_input = wx.TextCtrl(port_panel, value=str(default_next_port), size=(80, -1))
        port_sizer.Add(self.new_port_input, 0, wx.RIGHT, 5)
        
        port_panel.SetSizer(port_sizer)
        main_sizer.Add(port_panel, 0, wx.ALL | wx.CENTER, 10)
        
        # 버튼 패널
        btn_panel = wx.Panel(dlg)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # 프로세스 종료 후 계속 버튼 (프로세스 정보가 있을 때만 표시)
        if process_info:
            btn_kill = wx.Button(btn_panel, wx.ID_ANY, "프로세스 종료 후 계속")
            btn_sizer.Add(btn_kill, 0, wx.ALL, 5)
            btn_kill.Bind(wx.EVT_BUTTON, lambda evt: self._on_kill_process_from_dialog(dlg, process_info, default_port))
        
        # 다른 포트 사용 버튼
        btn_use_other = wx.Button(btn_panel, wx.ID_OK, "다른 포트 사용")
        btn_sizer.Add(btn_use_other, 0, wx.ALL, 5)
        
        # 취소 버튼
        btn_cancel = wx.Button(btn_panel, wx.ID_CANCEL, "취소")
        btn_sizer.Add(btn_cancel, 0, wx.ALL, 5)
        
        btn_panel.SetSizer(btn_sizer)
        main_sizer.Add(btn_panel, 0, wx.ALL | wx.CENTER, 10)
        
        dlg.SetSizer(main_sizer)
        dlg.Fit()
        dlg.CenterOnParent()
        
        # 대화상자 표시
        result = dlg.ShowModal()
        
        # 결과 처리
        if result == wx.ID_OK:
            # 다른 포트 사용 선택
            new_port = self.new_port_input.GetValue()
            dlg.Destroy()
            
            try:
                port = int(new_port)
                if port <= 0 or port > 65535:
                    wx.MessageBox("유효한 포트 번호는 1에서 65535 사이입니다.", "오류", wx.OK | wx.ICON_ERROR)
                    return self._show_port_change_dialog()  # 재귀적으로 다시 대화상자 표시
                if is_port_in_use(port):
                    wx.MessageBox(f"포트 {port}도 이미 사용 중입니다. 다른 포트를 선택해주세요.", "오류", wx.OK | wx.ICON_ERROR)
                    return self._show_port_change_dialog()  # 재귀적으로 다시 대화상자 표시
                return port
            except ValueError:
                wx.MessageBox("유효한 숫자를 입력해주세요.", "오류", wx.OK | wx.ICON_ERROR)
                return self._show_port_change_dialog()  # 재귀적으로 다시 대화상자 표시
        else:
            # 취소 또는 닫기
            dlg.Destroy()
            return None  # 사용자가 취소함
            
    def _try_kill_unknown_process(self, dlg, port):
        """포트를 사용 중인 프로세스를 찾을 수 없을 때 종료 시도"""
        self._start_server_after_kill = False  # 초기화
        self._port_to_use = port  # 해당 포트를 저장
        try:
            success = False
            pid_to_kill = None
            process_name = "unknown"
            
            # 방법 1: 넷스킷으로 SYN_SENT, LISTENING 등 모든 상태의 포트 사용 프로세스 찾기
            try:
                print(f"[AdminPanel] Checking all states of port {port} with netstat")
                netstat_result = subprocess.run(
                    ['netstat', '-ano'], 
                    capture_output=True, 
                    text=True, 
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                # 모든 상태의 포트 사용 프로세스 찾기
                for line in netstat_result.stdout.splitlines():
                    if f":{port}" in line:
                        print(f"[AdminPanel] Found in netstat: {line}")
                        parts = line.split()
                        if len(parts) >= 5:
                            pid_to_kill = parts[-1].strip()
                            try:
                                pid_to_kill = int(pid_to_kill)
                                # 프로세스 정보 확인
                                try:
                                    process = psutil.Process(pid_to_kill)
                                    process_name = process.name()
                                    print(f"[AdminPanel] Found process: {pid_to_kill} ({process_name})")
                                    break
                                except:
                                    pass
                            except ValueError:
                                pass
                            
                # 프로세스 발견 시 직접 taskkill로 종료
                if pid_to_kill:
                    print(f"[AdminPanel] Attempting to kill process {pid_to_kill} ({process_name}) using direct taskkill")
                    subprocess.run(
                        ['taskkill', '/F', '/PID', str(pid_to_kill)], 
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    success = True
            except Exception as e:
                print(f"[AdminPanel] Method 1 failed: {e}")
            
            # 방법 2: findstr를 사용해 넷스킷 결과 필터링 후 taskkill 실행
            if not success:
                try:
                    print(f"[AdminPanel] Attempting to kill process using port {port} with netstat+findstr and taskkill")
                    # 모든 상태 포함
                    cmd = f"for /f \"tokens=5\" %i in ('netstat -ano ^| findstr :{port}') do taskkill /F /PID %i"
                    subprocess.run(cmd, shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    success = True
                    
                    # 추가로 메모리에 있는 커맨드도 실행
                    cmd2 = f"for /f \"tokens=5\" %i in ('netstat -ano ^| findstr :{port} ^| findstr LISTENING') do taskkill /F /PID %i"
                    subprocess.run(cmd2, shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    
                    # SYN_SENT 까지 찾아서 종료
                    cmd3 = f"for /f \"tokens=5\" %i in ('netstat -ano ^| findstr :{port} ^| findstr SYN_SENT') do taskkill /F /PID %i"
                    subprocess.run(cmd3, shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception as e:
                    print(f"[AdminPanel] Method 2 failed: {e}")
            
            # 방법 3: TCPView 와 비슷한 방식으로 커넥션 해제
            if not success:
                try:
                    # 소켓 연결 시도
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1)
                    s.connect(('127.0.0.1', port))
                    s.close()
                    print(f"[AdminPanel] Successfully connected to port {port}, attempting RST")
                    
                        # FIN_WAIT 상태의 포트 해제 시도
                    cmd = f"for /f \"tokens=5\" %i in ('netstat -ano ^| findstr :{port} ^| findstr FIN_WAIT') do taskkill /F /PID %i"
                    subprocess.run(cmd, shell=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception as e:
                    print(f"[AdminPanel] Method 3 failed: {e}")
            
            # 포트 해제 확인을 위해 충분히 대기
            time.sleep(2)
            
            # 포트 사용 여부 다시 확인
            port_available = not is_port_in_use(port)
            if port_available:
                print(f"[AdminPanel] Port {port} is now available after kill attempts.")
                wx.MessageBox(f"포트 {port}를 사용하던 프로세스가 종료되었습니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 포트 {port}를 사용 중인 프로세스 종료 성공 ---")
                
                # 프로세스 종료 후 서버 자동 시작 설정
                self._start_server_after_kill = True
                self._port_to_use = port
                dlg.EndModal(wx.ID_YES)  # 성공 시 특별 결과 코드로 대화상자 종료
                return True
            else:
                wx.MessageBox(f"포트 {port}를 사용하는 프로세스 종료에 실패했거나 포트가 여전히 사용 중입니다.", "오류", wx.OK | wx.ICON_ERROR)
                self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 포트 {port}를 사용 중인 프로세스 종료 시도 실패 ---")
                return False
        except Exception as e:
            print(f"[AdminPanel] Error trying to kill unknown process: {e}")
            wx.MessageBox(f"프로세스 종료 시도 중 오류가 발생했습니다: {e}", "오류", wx.OK | wx.ICON_ERROR)
            return False
            
    def _on_kill_process_from_dialog(self, dlg, process_info, port):
        """포트 변경 대화상자에서 프로세스 종료 후 계속 옵션 처리"""
        # 프로세스 종료
        if kill_process(process_info['pid']):
            wx.MessageBox(f"프로세스(PID: {process_info['pid']})가 성공적으로 종료되었습니다.", "정보", wx.OK | wx.ICON_INFORMATION)
            
            # 포트가 실제로 해제될 때까지 약간 대기
            time.sleep(1)
            
            # 포트 상태 다시 확인
            port_available = not is_port_in_use(port)
            if port_available:
                wx.MessageBox(f"프로세스는 종료되었지만, 포트 {port}가 여전히 사용 중입니다.", "정보", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox(f"포트 {port}가 성공적으로 해제되었습니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                
            # 종료 버튼 비활성화
            self.btn_kill_process.Disable()
        else:
            wx.MessageBox(f"프로세스(PID: {process_info['pid']}) 종료에 실패했습니다.", "오류", wx.OK | wx.ICON_ERROR)
        
        # 대화상자가 전달된 경우 닫기
        if dlg and dlg.IsShown():
            dlg.EndModal(wx.ID_OK)
            
    def _update_api_client_url(self, port):
        """바뀐 포트를 반영하여 API 클라이언트의 기본 URL을 업데이트합니다."""
        try:
            if self.main_frame_ref:
                current_config = self.main_frame_ref.config
                # get_local_ips에서 첫 번째 IP 사용
                ips = list(get_local_ips())
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                print(ips)
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                ip = ips[0] if ips else '127.0.0.1'
                new_api_url = f'http://{ip}:{port}'
                current_config['api_base_url'] = new_api_url
                save_json_config(get_config_file(), current_config)
                print(f"[AdminPanel] Updated API base URL to {new_api_url}")
                self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API URL이 {new_api_url}로 업데이트되었습니다. ---")
                self.current_port = port
                if hasattr(self.main_frame_ref, 'api_client'):
                    print(f"[AdminPanel] Updating main frame API client to {new_api_url}")
                    self.main_frame_ref.api_client.base_url = new_api_url
                if hasattr(self.main_frame_ref, 'document_panel') and self.main_frame_ref.document_panel:
                    print(f"[AdminPanel] Updating document panel API client to {new_api_url}")
                    self.main_frame_ref.document_panel.api_client.base_url = new_api_url
                wx.CallAfter(self.main_frame_ref.SetStatusText, f"서버가 포트 {port}에서 실행 중입니다. API URL이 업데이트되었습니다.")
                return True
        except Exception as e:
            print(f"[AdminPanel] Error updating API base URL: {e}")
            wx.LogError(f"API URL 업데이트 오류: {e}")
            return False
            
    def _read_server_log(self):
        """Read and process server log output."""
        print("[AdminPanel] _read_server_log thread started.")
        try:
            if self.server_process and self.server_process.stdout:
                print(f"[AdminPanel] Server process stdout available. Starting to read logs...")
                server_started = False  # 서버 시작 상태 플래그 추가
                
                while not self.stop_event.is_set():
                    try:
                        raw_line = self.server_process.stdout.readline()
                    except Exception as e:
                        continue

                    # universal_newlines=False(바이너리 모드)로 실행된 경우 bytes로 들어옴
                    if isinstance(raw_line, bytes):
                        try:
                            line = raw_line.decode("utf-8")
                        except UnicodeDecodeError as e_utf8:
                            try:
                                line = raw_line.decode("cp949")
                                print(f"[AdminPanel] cp949로 디코딩 성공: {e_utf8}")
                            except Exception as e_cp949:
                                print(f"[AdminPanel] 로그 디코딩 실패: utf-8={e_utf8}, cp949={e_cp949}")
                                line = raw_line.decode("utf-8", errors="replace")
                    else:
                        line = raw_line

                    if len(line) > 0:
                        print(f"[AdminPanel] Read log line: {line[:50]}..." if len(line) > 500 else f"[AdminPanel] Read log line: {line}")
                    
                    # 서버 시작 여부 감지 (Uvicorn 실행 메시지 또는 Application startup complete 메시지 확인)
                    if not server_started and ("Uvicorn running on" in line or "Application startup complete" in line):
                        server_started = True
                        print("[AdminPanel] Server startup detected from logs!")
                        # UI 업데이트 (메인 스레드에서 실행되도록 CallAfter 사용)
                        wx.CallAfter(self._update_ui_for_server_running)
                    
                    if line.strip():  # 빈 줄 무시
                        print(f"[AdminPanel] Appending log line to UI: {line[:30]}..." if len(line) > 300 else f"[AdminPanel] Appending log line to UI: {line}")
                        wx.CallAfter(self._append_log_message, line.strip())   
            print("[AdminPanel] Exited log reading loop")
        except Exception as e:
            traceback.print_exc()
            print(f"[AdminPanel] Exception in _read_server_log: {e}")
            wx.LogError(f"Log reading error: {e}")
            if hasattr(self, 'log_text_ctrl') and self.log_text_ctrl:
                wx.CallAfter(self._append_log_message, f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Log reading error: {e} ---")
        finally:
            print("[AdminPanel] _read_server_log thread finishing.")
            if hasattr(self, 'log_text_ctrl') and self.log_text_ctrl:
                wx.CallAfter(self._append_log_message, f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Log reading finished ---")
            
            # 서버 프로세스 종료 로그 기록
            if self.server_process:
                wx.CallAfter(self._append_log_message, f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 서버 로그 읽기가 종료되었습니다. ---")
                print("[AdminPanel] Server log reading complete message sent.")

    def _force_document_refresh(self):
        """문서 패널의 문서 목록을 강제로 새로고침합니다."""
        try:
            print("[AdminPanel] Forcing document list refresh")
            if hasattr(self.main_frame_ref, 'doc_panel') and self.main_frame_ref.doc_panel:
                # API URL 갱신 후 직접 문서 목록 업데이트 호출
                try:
                    # 새로고침 버튼 클릭을 시ミュ레이션
                    print("[AdminPanel] Forcing document panel to update document list")
                    self.main_frame_ref.doc_panel.on_refresh_documents(None)
                    
                    # 문서 저장소 상태 정보도 업데이트
                    self.main_frame_ref.doc_panel.update_status_info()
                    
                    print("[AdminPanel] Document list refresh request completed")
                    self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 문서 목록 강제 새로고침 완료 ---")
                except Exception as e:
                    print(f"[AdminPanel] Error in document refresh simulation: {e}")
                    # 대체 방법 시도 - 직접 패널의 메소드 호출
                    try:
                        self.main_frame_ref.doc_panel.update_document_list()
                        print("[AdminPanel] Alternative document list update completed")
                    except Exception as alt_err:
                        print(f"[AdminPanel] Alternative update also failed: {alt_err}")
            else:
                print("[AdminPanel] Cannot refresh document list: document_panel not found")
        except Exception as e:
            print(f"[AdminPanel] Error in _force_document_refresh: {e}")
    
    def _update_ui_for_server_running(self):
        """서버가 시작되었을 때 UI 상태를 업데이트합니다."""
        try:
            print("[AdminPanel] Updating UI for server running state")
            # 서버 실행 중 상태로 UI 업데이트
            self.server_running = True
            self.server_starting = False
            
            # 버튼 상태 업데이트
            self.btn_start_server.Disable()
            self.btn_stop_server.Enable()
            self.btn_check_port.Disable()
            # port_spinner 대신 port_input 사용
            self.port_input.Disable()
            
            # 포트 상태 업데이트
            # port_spinner 대신 port_input 사용
            current_port = int(self.port_input.GetValue())
            status = self._update_api_client_url(current_port)
            if status:
                self._force_document_refresh()
            
            # 서버 상태 텍스트 업데이트
            self.txt_server_status.SetLabel(f"서버 상태: 실행 중 (포트: {current_port})")
            
            # 메인 프레임과 상태바 업데이트
            if hasattr(self, 'main_frame_ref') and self.main_frame_ref:
                # 상태바 업데이트
                self.main_frame_ref.SetStatusText(f"서버가 포트 {current_port}에서 실행 중입니다.")
                
                # 다른 패널들에게 서버 상태 변경 알림
                if hasattr(self.main_frame_ref, 'document_panel') and self.main_frame_ref.document_panel:
                    # 문서 저장소 상태 정보 업데이트
                    wx.CallAfter(self.main_frame_ref.document_panel.update_status_info)
                    
                    # 서버 시작 후 단순하게 문서 목록 새로고침
                    def refresh_documents_delayed():
                        # 서버가 완전히 준비될 시간 확보
                        print("[AdminPanel] 서버 로딩 완료, 잠시 후 문서 목록 갱신 시도...")
                        time.sleep(3.0)  # 3초 대기
                        
                        try:
                            # config 업데이트 - 언제나 최신 URL 사용
                            new_api_url = f'http://localhost:{self.current_port}'
                            self.main_frame_ref.config['api_base_url'] = new_api_url
                            print(f"[AdminPanel] API URL 업데이트: {new_api_url}")
                            
                            # 단순하게 문서 목록 새로고침 실행
                            print("[AdminPanel] 문서 목록 새로고침 시도")
                            wx.CallAfter(self.main_frame_ref.document_panel.on_refresh_documents, None)
                            print("[AdminPanel] 문서 목록 새로고침 요청 완료")
                            
                        except Exception as e:
                            print(f"[AdminPanel] 문서 목록 새로고침 중 오류: {e}")
                    
                    # 별도 스레드에서 지연 실행 (UI 차단 방지)
                    refresh_thread = threading.Thread(target=refresh_documents_delayed)
                    refresh_thread.daemon = True
                    refresh_thread.start()
                    
                    # 로그에 메시지 추가
                    print("[AdminPanel] 서버 시작 후 문서 목록 새로고침 예약됨")
                    self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 문서 목록 새로고침 예약됨 ---")
            
            # 로그에 메시지 추가
            self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 서버가 성공적으로 시작되었습니다. (포트: {current_port}) ---")
            
            print(f"[AdminPanel] UI updated for server running on port {current_port}")

            # 스플래시 닫기 (서버가 준비됨)
            self._hide_loading_splash()

            # 10초 뒤 모니터링 데몬 자동 시작
            wx.CallLater(10000, self._auto_start_monitoring)
        except Exception as e:
            print(f"[AdminPanel] Error updating UI for server running: {e}")
            wx.LogError(f"서버 실행 UI 업데이트 오류: {e}")
            self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] UI 업데이트 중 오류: {e} ---")

    def auto_start_server(self, ready_callback=None):
        """프로그램 시작 시 서버 자동 시작
        
        Args:
            ready_callback: 서버가 완전히 준비된 후 호출될 콜백 함수
        """

        import json

        print("[AdminPanel] auto_start_server called.")
        self.initial_server_ready_signal_sent = False  # Reset flag for this attempt
        self.server_ready_callback_for_auto_start = ready_callback

        config = load_json_config(get_config_file())
        default_port = config.get("port")
        if default_port is None:
            print("[AdminPanel] Auto-start: Port not configured or is None.")
            if self.main_frame_ref: wx.CallAfter(self.main_frame_ref.SetStatusText, "자동 시작 실패: 포트가 설정되지 않았습니다.")
            return

        try:
            port_to_check_auto = int(default_port)
        except (ValueError, TypeError) as e_conv:
            print(f"[AdminPanel] Auto-start: Invalid port from config '{default_port}': {e_conv}")
            if self.main_frame_ref: wx.CallAfter(self.main_frame_ref.SetStatusText, f"자동 시작 실패: 잘못된 포트 번호 ({default_port})")
            return

        print(f"[AdminPanel] auto_start_server: About to call is_port_in_use with port {port_to_check_auto} (type: {type(port_to_check_auto)})")
        if is_port_in_use(port_to_check_auto):
            print(f"[AdminPanel] Auto-start: Default port {port_to_check_auto} is already in use.")
            
        # Check if our managed server process is already running
        if self.server_process and self.server_process.poll() is None:
            print("[AdminPanel] Auto-start: Server process already managed by this UI instance and running.")
            return

        print("[AdminPanel] Auto-start: Attempting to start server process.")
        self.on_start_server_internal(auto_start_mode=True)

    def on_server_fully_ready_for_docs(self, success, message=""):
        """서버가 완전히 준비된 후 호출되는 콜백"""
        if success:
            if hasattr(self, 'main_frame_ref') and self.main_frame_ref:
                self.main_frame_ref.SetStatusText("문서 저장소가 준비되었습니다.")
        else:
            if hasattr(self, 'main_frame_ref') and self.main_frame_ref:
                self.main_frame_ref.SetStatusText(f"문서 저장소 시작 실패: {message}")

    def on_start_server(self, event): # Bound to the GUI button
        print("[AdminPanel] Manual 'Start Server' button clicked.")
        self.on_start_server_internal(auto_start_mode=False)
    
    def on_start_server_internal(self, auto_start_mode=False):
        """서버 시작 로직을 처리하는 내부 메서드"""
        import json
        
        # 프로세스 종료 후 서버 시작이 요청된 경우를 위한 변수 초기화
        if not hasattr(self, '_start_server_after_kill'):
            self._start_server_after_kill = False
            self._port_to_use = None
            
        # 이미 서버 프로세스가 실행 중인지 확인
        if self.server_process and self.server_process.poll() is None:
            if not auto_start_mode:
                wx.MessageBox("서버가 이미 실행 중입니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            else:
                print("[AdminPanel] on_start_server_internal (auto_start): Server already managed and running.")
            return

        script_path = os.path.join(os.getcwd(), "run.bat")
        if not os.path.exists(script_path):
            error_msg = f"Error: run.bat not found at {script_path}"
            wx.LogError(error_msg)
            self.txt_server_status.SetLabel("Server Status: run.bat not found")
            if self.main_frame_ref: wx.CallAfter(self.main_frame_ref.SetStatusText, "Server start failed: run.bat missing.")
            return

        try:
            self.stop_event.clear()
            
            config = load_json_config(get_config_file())

            default_port = config.get("port")
            if default_port is None:
                print("[AdminPanel] on_start_server_internal: Port not configured or is None.")
                if self.main_frame_ref: wx.CallAfter(self.main_frame_ref.SetStatusText, "서버 시작 실패: 포트가 설정되지 않았습니다.")
                return

            try:
                port_to_check_internal = int(default_port)
            except (ValueError, TypeError) as e_conv:
                print(f"[AdminPanel] on_start_server_internal: Invalid port from config '{default_port}': {e_conv}")
                if self.main_frame_ref: wx.CallAfter(self.main_frame_ref.SetStatusText, f"서버 시작 실패: 잘못된 포트 번호 ({default_port})")
                return

            print(f"[AdminPanel] on_start_server_internal: About to call is_port_in_use with port {port_to_check_internal} (type: {type(port_to_check_internal)})")
            port_in_use = is_port_in_use(port_to_check_internal)
            
            if port_in_use:
                print(f"[AdminPanel] Port {port_to_check_internal} is already in use. Attempting to handle...")
                self._run_server_when_port_in_use(script_path, port_to_check_internal)
            else:
                print(f"[AdminPanel] Port {port_to_check_internal} is available for use.")
                
            print(f"[AdminPanel] Starting server process with script: {script_path}")
            # 서버 시작 전 스플래시 표시
            self._show_loading_splash()
            
            # subprocess.PIPE 대신 버퍼링이 없는 방식으로 실행
            # 출력 버퍼링이 문제가 될 수 있으니 bufsize=0으로 설정
            # universal_newlines=True는 텍스트 모드로 출력을 처리하도록 합니다.
            self.server_process = subprocess.Popen(
                [script_path], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True, 
                bufsize=0,  # 버퍼링 없음
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            print(f"[AdminPanel] Server process created with PID: {self.server_process.pid}")
            
            self.server_pid = self.server_process.pid
            write_pid_to_file(self.server_pid, self.server_pid_file)
            self.server_pid_temp_for_status = self.server_pid
            
            self.log_thread = threading.Thread(target=self._read_server_log, daemon=True)
            self.log_thread.start()
            
            # 서버 로그 스레드 시작 후 모니터링 데몬 자동 시작
            try:
                self.on_start_monitoring(None)
            except Exception as e_monitor:
                print(f"[AdminPanel] Error during on_start_monitoring: {e_monitor}")
                wx.LogError(f"모니터링 시작 중 오류 발생: {e_monitor}")
                traceback.print_exc()

            self.btn_start_server.Disable()
            self.btn_stop_server.Enable()
            self.btn_check_port.Disable()
            self.port_input.Disable()
            
            status_msg = f"Server Status: Starting via run.bat (PID: {self.server_pid})..."
            detailed_status_msg = f"문서 저장소 시작 중입니다. 잠시만 기다려 주세요... (서버 PID: {self.server_pid})"
            self.txt_server_status.SetLabel(status_msg)
            if self.main_frame_ref:
                wx.CallAfter(self.main_frame_ref.SetStatusText, detailed_status_msg)
            print(f"[AdminPanel] Server process started (PID: {self.server_pid}). Log monitoring initiated.")

        except Exception as e:
            error_message = str(e) if e else "Unknown error"
            wx.LogError(f"Failed to start server: {error_message}")
            self.txt_server_status.SetLabel("Server Status: Error starting")
            if self.main_frame_ref: wx.CallAfter(self.main_frame_ref.SetStatusText, "서버 시작 중 오류가 발생했습니다.")
            self.server_process = None
            self.server_pid = None

    def _run_server_when_port_in_use(self, script_path, default_port_int):
        """포트가 사용 중일 때 서버 실행을 위한 포트 선택 및 프로세스 종료/변경 처리 로직을 별도 함수로 분리"""
        # default_port_int는 이미 정수형으로 전달받음
        print(f"[AdminPanel] *** Port {default_port_int} is already in use! Showing port change dialog. ***")
        
        # 포트 선택 처리 중단 여부를 위한 플래그
        break_out_of_port_selection = False
        
        # 재시도를 통한 포트를 사용하는 프로세스 정보 가져오기
        # 처음 시도에서 실패한 경우가 있을 수 있으므로 재시도
        retry_count = 0
        max_retries = 3
        process_info = None
        
        # 최대 3회까지 프로세스 정보 가져오기 시도
        while retry_count < max_retries:
            process_info = get_process_using_port(default_port_int)
            if process_info:
                print(f"[AdminPanel] Successfully found process using port {default_port_int} on attempt {retry_count+1}")
                break
            print(f"[AdminPanel] Retry {retry_count+1}/{max_retries} to find process using port {default_port_int}")
            retry_count += 1
            time.sleep(0.5)  # 재시도 전 잠시 대기
        
        # 프로세스 정보가 있을 경우 사용자에게 선택지 제공
        if process_info:
            # 프로세스 정보 문자열 생성
            process_info_text = f"기본 포트({default_port_int})를 사용 중인 프로세스:\n\n"
            process_info_text += f"PID: {process_info['pid']}\n"
            process_info_text += f"프로세스 이름: {process_info['name']}\n"
            process_info_text += f"생성 시간: {process_info['create_time']}\n"
            process_info_text += f"명령어: {process_info['cmd']}"
            
            # 사용자 선택 대화상자 표시
            if threading.current_thread() is threading.main_thread():
                # UI 스레드에서 직접 대화상자 표시
                # 메시지 강조 (MessageBox를 대신 사용하여 사용자 주의 유도)
                print(f"[AdminPanel] Showing process information dialog in UI thread")
                dlg = wx.MessageDialog(
                    self, 
                    process_info_text + "\n\n해당 프로세스를 종료하고 서버를 기본 포트로 시작할까요?",
                    "포트 충돌: 프로세스 처리 방법 선택",
                    wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION
                )
                dlg.SetYesNoLabels("프로세스 종료 후 계속", "다른 포트 사용")
                result = dlg.ShowModal()
                dlg.Destroy()
                
                if result == wx.ID_YES:  # 프로세스 종료 선택
                    print(f"[AdminPanel] User chose to kill the process {process_info['pid']}")
                    if kill_process(process_info['pid']):
                        print(f"[AdminPanel] Successfully killed process {process_info['pid']}")
                        wx.MessageBox(f"프로세스(PID: {process_info['pid']})가 종료되었습니다. 기본 포트로 재시작합니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                        # 포트가 실제로 해제될 때까지 약간 대기
                        time.sleep(1)  # 1초 대기
                        
                        # 포트가 이제 사용 가능한지 다시 확인
                        port_available = not is_port_in_use(default_port_int)
                        retry_count = 0
                        max_retries = 5  # 최대 5회 시도
                        
                        while not port_available and retry_count < max_retries:
                            print(f"[AdminPanel] Waiting for port {default_port_int} to be released... (Attempt {retry_count+1}/{max_retries})")
                            time.sleep(1)  # 1초 더 대기
                            port_available = not is_port_in_use(default_port_int)
                            retry_count += 1
                            
                        if port_available:
                            print(f"[AdminPanel] Port {default_port_int} is now available. Using default port.")
                            # 기본 포트 사용 계속
                            new_port = None
                            break_out_of_port_selection = True
                        else:
                            print(f"[AdminPanel] Port {default_port_int} is still in use after killing process. Asking for different port.")
                            wx.MessageBox(f"프로세스는 종료되었지만 포트 {default_port_int}가 여전히 사용 중입니다. 다른 포트를 선택해주세요.", "정보", wx.OK | wx.ICON_INFORMATION)
                            new_port = self._show_port_change_dialog()
                    else:
                        print(f"[AdminPanel] Failed to kill process {process_info['pid']}")
                        wx.MessageBox(f"프로세스(PID: {process_info['pid']}) 종료에 실패했습니다.", "오류", wx.OK | wx.ICON_ERROR)
                        new_port = self._show_port_change_dialog()
                elif result == wx.ID_NO:  # 다른 포트 사용 선택
                    print(f"[AdminPanel] User chose to use a different port")
                    new_port = self._show_port_change_dialog()
                else:  # 취소 선택
                    print(f"[AdminPanel] User canceled the operation")
                    new_port = None

            elif result == wx.ID_NO:  # 다른 포트 사용 선택
                port_result = [None]
                port_dialog_completed = threading.Event()
                
                def show_port_dialog():
                    try:
                        port_result[0] = self._show_port_change_dialog()
                    finally:
                        port_dialog_completed.set()
                        
                wx.CallAfter(show_port_dialog)
                port_dialog_completed.wait(30)  # 최대 30초 대기
                new_port = port_result[0]
            else:
                # 취소 또는 닫기
                dlg.Destroy()
                new_port = None
        
        # 사용자 응답에 따른 처리
        if (('new_port' not in locals() or new_port is None) and not break_out_of_port_selection):  # new_port가 정의되지 않았거나 None이면
            print(f"[AdminPanel] User canceled port change dialog. Aborting server start.")
            wx.CallAfter(self._append_log_message, f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 서버 시작이 취소되었습니다. ---")
            self.txt_server_status.SetLabel("Server Status: Startup canceled by user")
            if self.main_frame_ref:
                wx.CallAfter(self.main_frame_ref.SetStatusText, "서버 시작이 취소되었습니다.")
            return
        
        # 포트 충돌 해결 후 서버가 자동 시작된 경우 나머지 실행하지 않음
        if break_out_of_port_selection:
            return
        
        # 사용자가 선택한 포트로 run.bat 실행 명령 수정
        modified_script_path = os.path.join(os.path.dirname(script_path), "temp_run.bat")
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()

        config = load_json_config(get_config_file())

        content = content.replace(f"--port {config['port']}", f"--port {new_port}")
        
        with open(modified_script_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[AdminPanel] Created temporary run script with port {new_port}")
        script_path = modified_script_path
        
        # API 클라이언트 URL 업데이트
        status = self._update_api_client_url(new_port)
        if status:
            self._force_document_refresh()

    def on_stop_server(self, event):
        """서버 프로세스를 안전하게 종료합니다. 비동기로 처리하여 UI 블로킹을 방지합니다."""
        # 서버 실행 중인지 기본 확인
        if not self.server_process or self.server_process.poll() is not None:
            if not self.server_pid:  # 저장된 PID도 확인
                wx.MessageBox("Server is not running.", "Info", wx.OK | wx.ICON_INFORMATION)
                self.txt_server_status.SetLabel("Server Status: Not Running")
                if self.main_frame_ref: 
                    self.main_frame_ref.SetStatusText("서버가 실행 중이 아닙니다.")
                self._update_ui_for_server_stopped()
                return
        
        # 현재 실행 중인 서버 프로세스 ID 수집
        pids_to_kill = []
        if self.server_process and self.server_process.poll() is None:
            pids_to_kill.append(self.server_process.pid)
        
        if self.server_pid and self.server_pid not in pids_to_kill:
            pids_to_kill.append(self.server_pid)
            
        if not pids_to_kill:
            wx.MessageBox("서버 PID를 찾을 수 없습니다.", "정보", wx.OK | wx.ICON_INFORMATION)
            self.txt_server_status.SetLabel("Server Status: No PID")
            if self.main_frame_ref: 
                self.main_frame_ref.SetStatusText("서버 PID를 찾을 수 없습니다.")
            self._update_ui_for_server_stopped()
            return
        
        # UI 업데이트
        pid_list = ', '.join(map(str, pids_to_kill))
        self.main_frame_ref.SetStatusText(f"서버를 종료하는 중입니다 (PIDs: {pid_list})...")
        self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 서버 종료 시작 (PIDs: {pid_list}) ---")
        
        # 로그 읽기 스레드 중지 신호 설정
        self.stop_event.set()
        
        # 비동기 서버 종료 처리를 위한 스레드 시작
        shutdown_thread = threading.Thread(target=self._async_stop_server, args=(pids_to_kill,))
        shutdown_thread.daemon = True
        shutdown_thread.start()
        
        # UI 상태 업데이트
        self.txt_server_status.SetLabel("Server Status: Stopping...")
        if self.main_frame_ref:
            self.main_frame_ref.SetStatusText(f"서버 종료 요청이 전송되었습니다 (PIDs: {pid_list}).")

    def _async_stop_server(self, pids_to_kill):
        """비동기적으로 서버를 종료하는 내부 메서드"""
        try:
            # 로그 스레드가 종료될 때까지 약간 대기
            if self.log_thread and self.log_thread.is_alive():
                try:
                    wx.CallAfter(self._append_log_message, 
                        f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 로그 읽기 스레드 종료 대기 중... ---")
                    self.log_thread.join(timeout=2.0)
                except Exception as e:
                    print(f"[AdminPanel] Error waiting for log thread: {e}")
            
            # 모든 PID에 대해 종료 처리 시도
            for pid in pids_to_kill:
                try:
                    wx.CallAfter(self._append_log_message, 
                        f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PID {pid} 프로세스 종료 시도 중... ---")
                    
                    try:
                        # Windows에서 안정적인 taskkill 명령 사용
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], 
                                    check=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=3)
                        
                        wx.CallAfter(self._append_log_message, 
                            f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PID {pid} 프로세스가 종료되었습니다 ---")
                        
                    except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                        wx.CallAfter(self._append_log_message, 
                            f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PID {pid} 종료 중 오류: {e} ---")
                        
                        # 2차 시도: psutil 사용
                        try:
                            process = psutil.Process(pid)
                            process.kill()  # 강제 종료
                            wx.CallAfter(self._append_log_message, 
                                f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PID {pid} 강제 종료 완료 ---")
                        except:
                            pass
                        
                except Exception as e:
                    wx.CallAfter(self._append_log_message, 
                        f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PID {pid} 종료 중 오류: {e} ---")
            
            # PID 파일 정리
            if os.path.exists(self.server_pid_file):
                try:
                    os.remove(self.server_pid_file)
                    print(f"[AdminPanel] Removed PID file {self.server_pid_file}")
                except Exception as e:
                    print(f"[AdminPanel] Error removing PID file: {e}")
            
            # 리소스 정리
            if self.server_process:
                try:
                    if self.server_process.stdout:
                        self.server_process.stdout.close()
                except:
                    pass
                self.server_process = None
            
            # 모든 PID 정보 초기화
            self.server_pid_temp_for_status = None
            self.server_pid = None
            
            # UI 상태 업데이트
            wx.CallAfter(self._update_ui_for_server_stopped)
            wx.CallAfter(self._append_log_message, 
                f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 서버 종료 절차 완료 ---")
                
        except Exception as e:
            print(f"[AdminPanel] Error in async server shutdown: {e}")
            wx.CallAfter(wx.LogError, f"서버 비동기 종료 중 오류: {e}")
                
    def _append_log_message(self, message):
        """로그 텍스트 컨트롤에 메시지를 추가합니다."""
        if not hasattr(self, 'log_text_ctrl') or not self.log_text_ctrl: 
            return
        
        if not hasattr(self, 'log_lines'):
            self.log_lines = []
            
        self.log_lines.append(message.rstrip())
        if len(self.log_lines) > MAX_LOG_LINES:
            self.log_lines = self.log_lines[-MAX_LOG_LINES:]
        
        wx.CallAfter(self.log_text_ctrl.SetValue, "\n".join(self.log_lines))
        wx.CallAfter(self.log_text_ctrl.SetInsertionPointEnd)
        wx.CallAfter(self.log_text_ctrl.ShowPosition, self.log_text_ctrl.GetLastPosition())
        
    def _update_ui_for_server_stopped(self):
        """서버가 중지되었을 때 UI 상태를 업데이트합니다."""
        try:
            # 스플래시가 남아있다면 닫기
            self._hide_loading_splash()

            # UI 버튼 상태 업데이트
            self.btn_start_server.Enable()
            self.btn_stop_server.Disable()
            self.btn_check_port.Enable()
            self.port_input.Enable()
            
            # 서버 상태 텍스트 업데이트
            self.txt_server_status.SetLabel("서버 상태: 중지됨")
        except Exception as e:
            print(f"[AdminPanel] Error updating UI for server stopped: {e}")
            wx.LogError(f"서버 중지 UI 업데이트 오류: {e}")
            if hasattr(self, 'log_text_ctrl') and self.log_text_ctrl:
                wx.CallAfter(self._append_log_message, f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] UI 업데이트 중 오류: {e} ---")

        if len(self.log_lines) > MAX_LOG_LINES:
            self.log_lines = self.log_lines[-MAX_LOG_LINES:]
        
        wx.CallAfter(self.log_text_ctrl.SetValue, "\n".join(self.log_lines))
        wx.CallAfter(self.log_text_ctrl.SetInsertionPointEnd)
        wx.CallAfter(self.log_text_ctrl.ShowPosition, self.log_text_ctrl.GetLastPosition())
        
    def on_check_port(self, event):
        """특정 포트를 사용 중인 프로세스를 확인합니다."""
        try:
            port_str = self.port_input.GetValue()
            if not port_str.isdigit():
                wx.MessageBox("유효한 포트 번호를 입력해주세요.", "오류", wx.OK | wx.ICON_ERROR)
                return

            port_to_check = int(port_str)
            if port_to_check < 1 or port_to_check > 65535:
                wx.MessageBox("유효한 포트 번호는 1-65535 사이입니다.", "오류", wx.OK | wx.ICON_ERROR)
                return
                
            print(f"[AdminPanel] on_check_port: About to call is_port_in_use with port {port_to_check} (type: {type(port_to_check)})")
            port_in_use = is_port_in_use(port_to_check)
            
            if not port_in_use:
                wx.MessageBox(f"포트 {port_to_check}는 현재 사용 중이 아닙니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                self.btn_kill_process.Disable()
                return
                
            # 프로세스 정보 가져오기
            process_info = get_process_using_port(port_to_check)
            
            if not process_info:
                wx.MessageBox(f"포트 {port_to_check}는 사용 중이지만, 사용 중인 프로세스 정보를 찾을 수 없습니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                self.btn_kill_process.Disable()
                return
                
            # 프로세스 정보 표시
            process_info_text = f"포트 {port_to_check}를 사용 중인 프로세스:\n\n"
            process_info_text += f"PID: {process_info['pid']}\n"
            process_info_text += f"프로세스 이름: {process_info['name']}\n"
            process_info_text += f"생성 시간: {process_info['create_time']}\n"
            process_info_text += f"명령어: {process_info['cmd']}"
            
            # 프로세스 정보 대화상자 생성 및 표시
            dlg = wx.Dialog(self, title=f"포트 중복", size=(400, 300))
            
            # 대화상자 레이아웃
            vbox = wx.BoxSizer(wx.VERTICAL)
            
            # 아이콘 및 텍스트 패널
            info_panel = wx.Panel(dlg)
            info_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # 정보 아이콘 추가
            info_icon = wx.StaticBitmap(info_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_MESSAGE_BOX))
            info_sizer.Add(info_icon, 0, wx.ALL | wx.CENTER, 10)
            
            # 메시지 텍스트 추가
            message = wx.StaticText(info_panel, label=process_info_text)
            info_sizer.Add(message, 1, wx.ALL | wx.EXPAND, 10)
            
            info_panel.SetSizer(info_sizer)
            vbox.Add(info_panel, 0, wx.ALL | wx.EXPAND, 5)
            
            # 버튼 패널
            btn_panel = wx.Panel(dlg)
            btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # OK 버튼
            btn_ok = wx.Button(btn_panel, wx.ID_OK, "확인")
            btn_sizer.Add(btn_ok, 0, wx.ALL, 5)
            
            # 프로세스 종료 버튼
            btn_kill = wx.Button(btn_panel, wx.ID_ANY, "프로세스 종료")
            btn_sizer.Add(btn_kill, 0, wx.ALL, 5)
            
            # 버튼 이벤트 바인딩
            dlg.Bind(wx.EVT_BUTTON, lambda evt: self._kill_process_from_dialog(evt, process_info, port_to_check, dlg), btn_kill)
            
            btn_panel.SetSizer(btn_sizer)
            vbox.Add(btn_panel, 0, wx.ALL | wx.CENTER, 5)
            
            dlg.SetSizer(vbox)
            dlg.ShowModal()
            dlg.Destroy()
            
            # 프로세스 종료 버튼 활성화
            self.btn_kill_process.Enable()
            
            # 현재 확인된 프로세스 정보 저장
            self.current_port_process = process_info
            self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 포트 {port_to_check}를 사용 중인 프로세스 PID {process_info['pid']} 확인됨 ---")
            
        except Exception as e:
            wx.MessageBox(f"포트 확인 중 오류가 발생했습니다: {e}", "오류", wx.OK | wx.ICON_ERROR)
            self.btn_kill_process.Disable()
        
    def _kill_process_from_dialog(self, event, process_info, port, dlg=None):
        """대화상자에서 직접 프로세스를 종료합니다."""
        try:
            # 프로세스 종료
            if kill_process(process_info['pid']):
                wx.MessageBox(f"프로세스(PID: {process_info['pid']})가 성공적으로 종료되었습니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                
                # 포트가 실제로 해제될 때까지 약간 대기
                time.sleep(1)
                
                # 포트 상태 다시 확인
                port_available = not is_port_in_use(port)
                if port_available:
                    wx.MessageBox(f"프로세스는 종료되었지만 포트 {port}가 여전히 사용 중입니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox(f"포트 {port}가 성공적으로 해제되었습니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                    
                # 종료 버튼 비활성화
                self.btn_kill_process.Disable()
                self.current_port_process = None
            else:
                wx.MessageBox(f"프로세스(PID: {process_info['pid']}) 종료에 실패했습니다.", "오류", wx.OK | wx.ICON_ERROR)
        
        except Exception as e:
            wx.MessageBox(f"프로세스 종료 중 오류가 발생했습니다: {e}", "오류", wx.OK | wx.ICON_ERROR)
        
        # 대화상자가 전달된 경우 닫기
        if dlg and dlg.IsShown():
            dlg.EndModal(wx.ID_OK)
            
    def on_kill_process(self, event):
        """확인된 프로세스를 종료합니다."""
        if not hasattr(self, 'current_port_process') or not self.current_port_process:
            wx.MessageBox("종료할 프로세스 정보가 없습니다. 먼저 포트 확인을 실행해주세요.", "오류", wx.OK | wx.ICON_ERROR)
            return
            
        process_info = self.current_port_process
        port = int(self.port_input.GetValue())
        
        # 종료 확인 대화상자
        if wx.MessageBox(
            f"정말로 포트 {port}를 사용 중인 프로세스(PID: {process_info['pid']}, 이름: {process_info['name']})를 종료하시겠습니까?",
            "프로세스 종료 확인",
            wx.YES_NO | wx.ICON_QUESTION
        ) != wx.YES:
            return
            
        self._kill_process_from_dialog(None, process_info, port)

    def on_start_monitoring(self, event):
        """모니터링 시작 버튼 클릭 처리"""
        print("[AdminPanel] 모니터링 시작 버튼 클릭됨")
        if self.monitoring_daemon is None:
            raise ValueError("Monitoring daemon not initialized.")
            
        self.monitoring_daemon.start()
        self.btn_start_monitoring.Disable()
        self.btn_stop_monitoring.Enable()
        self.monitoring_interval_input.Disable()
        self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모니터링 시작 ---")
        
        # 모니터링 결과 업데이트를 위한 타이머 시작
        print("[AdminPanel] 모니터링 타이머 시작: 1초 간격")
        self.monitoring_timer.Start(1000)  # 1초마다 UI 업데이트
        
        # 즉시 결과 UI 업데이트 호출
        wx.CallAfter(self._update_monitoring_result)

    def on_stop_monitoring(self, event):
        """모니터링 중지 버튼 클릭 처리"""
        self.monitoring_daemon.stop()
        self.btn_start_monitoring.Enable()
        self.btn_stop_monitoring.Disable()
        self.monitoring_interval_input.Enable()
        self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모니터링 중지 ---")
        
        # 타이머 중지
        self.monitoring_timer.Stop()
        
        # 마지막 결과 업데이트
        self._update_monitoring_result()

    def on_monitoring_interval_changed(self, event):
        """모니터링 간격 입력 변경 처리"""
        try:
            new_interval = int(self.monitoring_interval_input.GetValue())
            self.monitoring_daemon.set_interval(new_interval)
            self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모니터링 간격 변경: {new_interval}초 ---")
        except ValueError:
            wx.MessageBox("유효한 숫자를 입력해주세요.", "오류", wx.OK | wx.ICON_ERROR)

    def on_monitoring_timer(self, event):
        """모니터링 타이머 이벤트 처리"""
        # 로그 출력 제거
        wx.CallAfter(self._update_monitoring_result)
        
    def _update_monitoring_result(self):
        """모니터링 결과 UI 업데이트"""
        try:
            # 로그 출력 제거
            # 모니터링 결과 가져오기
            result = self.monitoring_daemon.get_monitoring_result()
            
            # 시간 정보 업데이트
            start_time = result.get("start_time")
            last_check_time = result.get("last_check_time")
            
            if start_time and last_check_time:
                # 한글 날짜 형식 대신 영어 형식 사용 - 인코딩 오류 방지
                start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
                end_str = last_check_time.strftime("%H:%M:%S")
                self.txt_time_period.SetLabel(f"- 시작 ~ 종료 시간: {start_str} ~ {end_str}")
                # 로그 출력 제거
                
                # 소요 시간 (각 모니터링 주기별 소요 시간)
                duration = result.get('run_duration', '계산 중...')
                self.txt_duration.SetLabel(f"- 걸린 시간: {duration}")
                # 로그 출력 제거
                
                # 파일 변경 결과 - 이번 주기에서 감지된 변경사항만 표시
                file_changes_text = ""
                
                # 추가된 파일
                added_files = result.get("added_files", [])
                if added_files:
                    file_changes_text += "  [추가된 파일]\n"
                    for file in added_files:
                        file_changes_text += f"  - {file}\n"
                    file_changes_text += "\n"
                    # 변경 정보는 중요한 로그이므로 유지
                    print(f"[AdminPanel] 추가된 파일 {len(added_files)}개 발견")
                
                # 수정된 파일
                modified_files = result.get("modified_files", [])
                if modified_files:
                    file_changes_text += "  [수정된 파일]\n"
                    for file in modified_files:
                        file_changes_text += f"  - {file}\n"
                    file_changes_text += "\n"
                    # 변경 정보는 중요한 로그이므로 유지
                    print(f"[AdminPanel] 수정된 파일 {len(modified_files)}개 발견")
                
                # 삭제된 파일
                deleted_files = result.get("deleted_files", [])
                if deleted_files:
                    file_changes_text += "  [삭제된 파일]\n"
                    for file in deleted_files:
                        file_changes_text += f"  - {file}\n"
                    # 변경 정보는 중요한 로그이므로 유지
                    print(f"[AdminPanel] 삭제된 파일 {len(deleted_files)}개 발견")
                
                total_files = len(added_files) + len(modified_files) + len(deleted_files)
                if total_files == 0:
                    file_changes_text = "  이번 주기에서 변경된 파일이 없습니다."
                    # 변경된 파일이 없을 때 로그를 출력하지 않음
                else:
                    # 마지막 확인 시간 표시
                    last_check_str = last_check_time.strftime("%H:%M:%S")
                    file_changes_text = f"  [주기 종료 시간: {last_check_str}]\n" + file_changes_text
                
                # 항상 텍스트 업데이트
                self.txt_file_changes.SetValue(file_changes_text)
                
                # 변경된 파일이 있을 때만 파일 변경 내용 업데이트 완료 로그 출력
                if total_files > 0:
                    print("[AdminPanel] 파일 변경 내용 UI 업데이트 완료")
            else:
                self.txt_time_period.SetLabel("- 시작 ~ 종료 시간: 아직 시작되지 않음")
                self.txt_duration.SetLabel("- 걸린 시간: 0시간 0분 0초")
                self.txt_file_changes.SetValue("  아직 변경된 파일이 없습니다.")
                print("[AdminPanel] 모니터링이 아직 시작되지 않았거나 시간 정보가 없음")
        except Exception as e:
            print(f"[AdminPanel] 모니터링 결과 업데이트 중 오류: {e}")
            import traceback
            traceback.print_exc()  # 상세 오류 스택 출력
            self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모니터링 결과 업데이트 오류: {e} ---")

    # ===================== 로딩 스플래시 제어 =====================
    def _show_loading_splash(self):
        """loading.gif 스플래시 창을 띄웁니다."""
        try:
            if self.loading_splash is None:
                gif_path = os.path.join(os.getcwd(), "loading.gif")
                self.loading_splash = LoadingSplash(parent=self.GetTopLevelParent(), gif_path=gif_path)
                self.loading_splash.Show()
                print("[AdminPanel] Loading splash shown")
        except Exception as e:
            print(f"[AdminPanel] Error showing splash: {e}")

    def _hide_loading_splash(self):
        """스플래시 창을 닫습니다."""
        try:
            if self.loading_splash:
                self.loading_splash.close()
                self.loading_splash = None
                print("[AdminPanel] Loading splash closed")
        except Exception as e:
            print(f"[AdminPanel] Error hiding splash: {e}")

    def _auto_start_monitoring(self):
        """서버 시작 완료 후 10초 뒤 모니터링 데몬 자동 시작"""
        try:
            if self.btn_start_monitoring.IsEnabled():
                print("[AdminPanel] Auto starting monitoring daemon")
                self.on_start_monitoring(None)
        except Exception as e:
            print(f"[AdminPanel] Error auto starting monitoring: {e}")