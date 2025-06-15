from datetime import datetime
import os
import sys
import subprocess
import threading
import time
import traceback
from logger_util import ui_logger

import wx

from ui.config_util import get_datastore_port, load_json_config, save_port_config

from ui.ui_setting import MODERN_COLORS
from ui.process_util import (
    get_process_using_port,
    is_port_in_use,
    kill_process_by_pids,
)
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# TODO: 설정 파일로 옮기고 UI도 추가 필요
MAX_LOG_LINES = 3000

class AdminPanel(wx.Panel):
    def __init__(self, parent, api_client, main_frame_ref, monitoring_daemon=None):
        super().__init__(parent)
        self.SetBackgroundColour(MODERN_COLORS['notebook_background'])
        self.api_client = api_client
        self.main_frame_ref = main_frame_ref # Store reference to MainFrame
        self.log_lines = []
        self.datastore_process = None
        self.is_datastore_running = False
        self.monitoring_daemon = monitoring_daemon
    
        
        # 프로세스 종료 후 서버 자동 시작 관련 변수
        self._start_server_after_kill = False
        self._port_to_use = None
        
        # For auto-start server readiness detection
        self.server_ready_callback_for_auto_start = None
        self.initial_server_ready_signal_sent = False

        vbox = wx.BoxSizer(wx.VERTICAL)

        # 서버 제어 섹션
        server_control_static_box = wx.StaticBox(self, label="문서 저장소 제어 및 포트 관리")
        server_control_static_box.SetForegroundColour(MODERN_COLORS['title_text'])
        server_control_sizer = wx.StaticBoxSizer(server_control_static_box, wx.VERTICAL)
        
        # 서버 시작/종료 버튼
        server_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start_server = wx.Button(self, label='문서 저장소 시작')
        self.btn_start_server.SetBackgroundColour(MODERN_COLORS['button_background'])
        self.btn_start_server.SetForegroundColour(MODERN_COLORS['button_text'])
        self.btn_start_server.SetToolTip("문서 저장소 프로세스를 실행합니다")
        self.btn_stop_server = wx.Button(self, label='문서 저장소 종료')
        self.btn_stop_server.SetBackgroundColour(MODERN_COLORS['delete_button_background'])
        self.btn_stop_server.SetForegroundColour(MODERN_COLORS['button_text'])
        self.btn_stop_server.SetToolTip("실행 중인 문서 저장소 프로세스를 중지합니다")
        self.btn_stop_server.Disable()

        # 초기 버튼 상태 설정
        self._update_button_state(self.btn_start_server)
        self._update_button_state(self.btn_stop_server)

        server_buttons_sizer.Add(self.btn_start_server, 1, wx.RIGHT, 5)
        server_buttons_sizer.Add(self.btn_stop_server, 1, wx.LEFT, 5)
        server_control_sizer.Add(server_buttons_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # 구분선 추가
        separator = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        server_control_sizer.Add(separator, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        
        # 포트 충돌 관리 섹션 추가 (레이블 추가)
        port_title = wx.StaticText(self, label="포트 충돌 확인 및 해결")
        port_title.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        port_title.SetForegroundColour(MODERN_COLORS['text'])
        server_control_sizer.Add(port_title, 0, wx.ALL, 5)
        
        port_conflict_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.port_input = wx.TextCtrl(self, value="8123", size=(60, -1))
        self.port_input.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        self.port_input.SetForegroundColour(MODERN_COLORS['text'])
        self.btn_check_port = wx.Button(self, label='포트 확인')
        self.btn_check_port.SetBackgroundColour(MODERN_COLORS['button_background'])
        self.btn_kill_process = wx.Button(self, label='프로세스 종료')
        self.btn_kill_process.SetBackgroundColour(MODERN_COLORS['delete_button_background'])
        self.btn_kill_process.SetForegroundColour(MODERN_COLORS['button_text'])
        # 포트 관리 툴팁
        self.btn_check_port.SetToolTip("입력한 포트를 사용 중인 프로세스가 있는지 확인합니다")
        self.btn_kill_process.SetToolTip("선택한 포트를 점유 중인 프로세스를 종료합니다")
        self.btn_kill_process.Disable()  # 처음에는 비활성화
        self._update_button_state(self.btn_check_port)
        self._update_button_state(self.btn_kill_process)
        
        port_conflict_sizer.Add(wx.StaticText(self, label="포트:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        port_conflict_sizer.Add(self.port_input, 0, wx.RIGHT, 5)
        port_conflict_sizer.Add(self.btn_check_port, 1, wx.RIGHT, 5)
        port_conflict_sizer.Add(self.btn_kill_process, 1)
        server_control_sizer.Add(port_conflict_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # 구분선 추가
        separator2 = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        server_control_sizer.Add(separator2, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        
        self.txt_server_status = wx.StaticText(self, label="문서 저장소 상태: 알 수 없음")
        self.txt_server_status.SetForegroundColour(MODERN_COLORS['text'])
        server_control_sizer.Add(self.txt_server_status, 0, wx.EXPAND | wx.ALL, 5)
        
        vbox.Add(server_control_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # 문서 파일 모니터링 섹션
        monitoring_static_box = wx.StaticBox(self, label="문서 파일 모니터링")
        monitoring_static_box.SetForegroundColour(MODERN_COLORS['title_text'])
        monitoring_sizer = wx.StaticBoxSizer(monitoring_static_box, wx.VERTICAL)
        
        # 모니터링 컨트롤
        monitoring_controls = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start_monitoring = wx.Button(self, label='모니터링 시작')
        self.btn_start_monitoring.SetBackgroundColour(MODERN_COLORS['button_background'])
        self.btn_start_monitoring.SetForegroundColour(MODERN_COLORS['button_text'])
        self.btn_start_monitoring.SetToolTip("문서 디렉터리 변경 감지를 시작합니다")
        self.btn_stop_monitoring = wx.Button(self, label='모니터링 중지')
        self.btn_stop_monitoring.SetBackgroundColour(MODERN_COLORS['delete_button_background'])
        self.btn_stop_monitoring.SetForegroundColour(MODERN_COLORS['button_text'])
        self.btn_stop_monitoring.SetToolTip("문서 변경 감지를 중지합니다")
        self.btn_stop_monitoring.Disable()
        self._update_button_state(self.btn_start_monitoring)
        self._update_button_state(self.btn_stop_monitoring)
        
        self.monitoring_thread = None
        self.monitoring_interval = 10  # 초기 모니터링 간격 (초)
        monitoring_interval_label = wx.StaticText(self, label="모니터링 간격(초):")
        monitoring_interval_label.SetForegroundColour(MODERN_COLORS['text'])
        self.monitoring_interval_input = wx.TextCtrl(self, value=str(self.monitoring_interval), style=wx.TE_PROCESS_ENTER)
        self.monitoring_interval_input.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        self.monitoring_interval_input.SetForegroundColour(MODERN_COLORS['text'])
        self.monitoring_interval_input.SetToolTip("감지 주기를 초 단위로 입력 후 Enter")
        
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
        self.txt_time_period = wx.StaticText(self, label="- 시작 - 종료 시간: 파일 변경에 따른 모니터링 결과 없음")
        self.txt_time_period.SetForegroundColour(MODERN_COLORS['text'])
        result_sizer.Add(self.txt_time_period, 0, wx.ALL, 5)
        
        # 걸린 시간
        self.txt_duration = wx.StaticText(self, label="- 걸린 시간: 0시간 0분 0초")
        self.txt_duration.SetForegroundColour(MODERN_COLORS['text'])
        result_sizer.Add(self.txt_duration, 0, wx.ALL, 5)
        
        # 파일 목록 헤더
        file_list_header = wx.StaticText(self, label="- 파일 변경 감지 결과:")
        file_list_header.SetForegroundColour(MODERN_COLORS['text'])
        result_sizer.Add(file_list_header, 0, wx.ALL, 5)
        
        # 추가/수정/삭제된 파일 목록을 표시할 텍스트 컨트롤
        self.txt_file_changes = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL, size=(-1, 100))
        self.txt_file_changes.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        self.txt_file_changes.SetForegroundColour(MODERN_COLORS['text'])
        result_sizer.Add(self.txt_file_changes, 1, wx.ALL | wx.EXPAND, 5)
        self.txt_file_changes_history = []
        
        monitoring_sizer.Add(result_sizer, 1, wx.ALL | wx.EXPAND, 5)
        
        vbox.Add(monitoring_sizer, 0, wx.ALL | wx.EXPAND, 10)

        log_static_box = wx.StaticBox(self, label="Logs")
        log_static_box.SetForegroundColour(MODERN_COLORS['title_text'])
        log_box_sizer = wx.StaticBoxSizer(log_static_box, wx.VERTICAL)

        self.log_text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.log_text_ctrl.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        self.log_text_ctrl.SetForegroundColour(MODERN_COLORS['text'])
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

    def __make_default_and_next_port(self):
        default_port = get_datastore_port()
        default_next_port = int(default_port) + 1
        if default_next_port >= 65535:
            default_next_port = 65533

        return default_port, default_next_port

    def _show_port_change_dialog(self):
        default_port, default_next_port = self.__make_default_and_next_port()
        
        process_info, message_text = get_process_using_port(default_next_port)
        
        dlg = wx.Dialog(self, title="포트 충돌", size=(450, 320))
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 아이콘 및 메시지 패널
        info_panel = wx.Panel(dlg)
        info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # 경고 아이콘 추가
        info_icon = wx.StaticBitmap(info_panel, bitmap=wx.ArtProvider.GetBitmap(wx.ART_WARNING, wx.ART_MESSAGE_BOX))
        info_sizer.Add(info_icon, 0, wx.ALL | wx.CENTER, 10)
        
        message = wx.StaticText(info_panel, label="포트를 변경하여 문서 저장소를 실행 하시겠습니까?")
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
            btn_kill.Bind(wx.EVT_BUTTON, lambda evt: self._on_kill_process_from_dialog(dlg, process_info, default_next_port))
        
        # 다른 포트 사용 버튼
        btn_use_other = wx.Button(btn_panel, wx.ID_OK, "포트 사용")
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
                if port <= 1024 or port > 65535:
                    wx.MessageBox("유효한 포트 번호는 1025에서 65535 사이입니다.", "오류", wx.OK | wx.ICON_ERROR)
                    return self._show_port_change_dialog()  # 재귀적으로 다시 대화상자 표시
                if is_port_in_use(port):
                    wx.MessageBox(f"포트 {port}도 이미 사용 중입니다. 다른 포트를 선택해주세요.", "오류", wx.OK | wx.ICON_ERROR)
                    return self._show_port_change_dialog()  # 재귀적으로 다시 대화상자 표시
                return port
            except ValueError:
                wx.MessageBox("유효한 숫자를 입력해주세요.", "오류", wx.OK | wx.ICON_ERROR)
                return self._show_port_change_dialog()  # 재귀적으로 다시 대화상자 표시
        else:
            dlg.Destroy()
            return None
        
        dlg.Destroy()
        return None  # 사용자가 취소함
            
    def _on_kill_process_from_dialog(self, dlg, process_info, port):
        """포트 변경 대화상자에서 프로세스 종료 후 계속 옵션 처리"""
        # 포트를 점유하고 있는 프로세스 종료
        if kill_process_by_pids(process_info['pid']):
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
            self._update_button_state(self.btn_kill_process)
        else:
            wx.MessageBox(f"프로세스(PID: {process_info['pid']}) 종료에 실패했습니다.", "오류", wx.OK | wx.ICON_ERROR)
        
        # 대화상자가 전달된 경우 닫기
        if dlg and dlg.IsShown():
            dlg.EndModal(wx.ID_OK)

    def _force_document_refresh(self):
        """문서 패널의 문서 목록을 강제로 새로고침합니다."""
        try:
            ui_logger.info("[AdminPanel] Forcing document list refresh")
            if hasattr(self.main_frame_ref, 'doc_panel') and self.main_frame_ref.doc_panel:
                # API URL 갱신 후 직접 문서 목록 업데이트 호출
                try:
                    # 새로고침 버튼 클릭을 시럼레이션
                    ui_logger.info("[AdminPanel] Forcing document panel to update document list")
                    self.main_frame_ref.doc_panel.on_refresh_documents(None)
                    
                    # 문서 저장소 상태 정보도 업데이트
                    self.main_frame_ref.doc_panel.update_status_info()
                    
                    ui_logger.info("[AdminPanel] Document list refresh request completed")
                    self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 문서 목록 강제 새로고침 완료 ---")
                except Exception as e:
                    ui_logger.exception(f"[AdminPanel] Error in document refresh simulation: {e}")
                    # 대체 방법 시도 - 직접 패널의 메소드 호출
                    try:
                        self.main_frame_ref.doc_panel.update_document_list()
                        ui_logger.info("[AdminPanel] Alternative document list update completed")
                    except Exception as alt_err:
                        ui_logger.exception(f"[AdminPanel] Alternative update also failed: {alt_err}")
            else:
                ui_logger.error("[AdminPanel] Cannot refresh document list: document_panel not found")
        except Exception as e:
            ui_logger.exception(f"[AdminPanel] Error in _force_document_refresh: {e}")
    
    def _update_ui_for_server_running(self):
        """서버가 시작되었을 때 UI 상태를 업데이트합니다."""
        try:
            #self._hide_loading_splash()
            ui_logger.info("[AdminPanel] Updating UI for DataStore running state")
            
            # 버튼 상태 업데이트
            self.btn_start_server.Disable()
            self.btn_stop_server.Enable()
            self._update_button_state(self.btn_start_server)
            self._update_button_state(self.btn_stop_server)
            self.btn_check_port.Disable()
            self.port_input.Disable()
            self._update_button_state(self.btn_check_port)
            
            # 포트 상태 업데이트
            #current_port = int(self.port_input.GetValue())
            #save_port_config(current_port)
            current_port = get_datastore_port()
            self.port_input.SetValue(str(current_port))
            
            self._force_document_refresh()
            # 서버 상태 텍스트 업데이트
            self.txt_server_status.SetLabel(f"문서 저장소 상태: 실행 중 (포트: {current_port})")
            
            # 로그에 메시지 추가
            self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 문서 저장소가 성공적으로 시작되었습니다. (포트: {current_port}) ---")
            
            ui_logger.info(f"[AdminPanel] UI updated for DataStore running on port {current_port}")

            # 10초 뒤 모니터링 데몬 자동 시작
            wx.CallLater(10000, self._auto_start_monitoring)
        except Exception as e:
            ui_logger.exception(f"[AdminPanel] Error updating UI for DataStore running: {e}")
            wx.LogError(f"문서 저장소 실행 UI 업데이트 오류: {e}")
            self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] UI 업데이트 중 오류: {e} ---")

    def _update_button_state(self, button):
        """버튼의 활성화/비활성화 상태에 따라 스타일을 업데이트합니다."""
        if button.IsEnabled():
            if '종료' in button.GetLabel():
                button.SetBackgroundColour(MODERN_COLORS['delete_button_background'])
            else:
                button.SetBackgroundColour(MODERN_COLORS['button_background'])
            button.SetForegroundColour(MODERN_COLORS['button_text'])
            button.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        else:
            button.SetBackgroundColour(MODERN_COLORS['disabled_button_background'])
            button.SetForegroundColour(MODERN_COLORS['disabled_button_text'])
            button.SetCursor(wx.Cursor(wx.CURSOR_NO_ENTRY))

    def auto_start_server(self, ready_callback=None):
        """프로그램 시작 시 서버 자동 시작
        
        Args:
            ready_callback: 서버가 완전히 준비된 후 호출될 콜백 함수
        """
        ui_logger.debug("[AdminPanel] auto_start_server 진입")
        try:
            ui_logger.debug("[AdminPanel] auto_start_server called.")
            self.initial_server_ready_signal_sent = False  # Reset flag for this attempt
            self.server_ready_callback_for_auto_start = ready_callback

            port_to_check_auto = get_datastore_port()
            if port_to_check_auto is None:
                ui_logger.debug("[AdminPanel] Auto-start: Port not configured or is None.")
                if self.main_frame_ref: 
                    wx.CallAfter(self.main_frame_ref.SetStatusText, "자동 시작 실패: 포트가 설정되지 않았습니다.")
                return

            ui_logger.debug(f"[AdminPanel] auto_start_server: About to call is_port_in_use with port {port_to_check_auto} (type: {type(port_to_check_auto)})")
            if is_port_in_use(port_to_check_auto):
                ui_logger.debug(f"[AdminPanel] Auto-start: Default port {port_to_check_auto} is already in use.")
                #TODO: 해당 포트의 프로세스를 죽이고 실행할 것인지 묻는 대화상자 출력 필요
                self._run_server_when_port_in_use(port_to_check_auto)
            else:
                ui_logger.debug("[AdminPanel] Auto-start: Attempting to start DataStore process.")
                self.on_start_server_internal(auto_start_mode=True)

            # Check if our managed server process is already running
            if self._is_datastore_running():
                ui_logger.debug("[AdminPanel] Auto-start: DataStore process already managed by this UI instance and running.")
                return
        except Exception as e:
            ui_logger.exception("auto_start_server 실행 오류")
            raise e

    def on_start_server(self, event): # Bound to the GUI button
        try:
            wx.CallAfter(self.main_frame_ref.SetStatusText, f"DataStore를 포트 {get_datastore_port()}에서 시작 중입니다...")
            self.on_start_server_internal(auto_start_mode=False)
            wx.CallAfter(self.main_frame_ref.SetStatusText, f"DataStore를 포트 {get_datastore_port()}에서 시작했습니다.")
        except Exception as e:
            ui_logger.exception('문서 저장소 시작 오류')
            raise e
        
    def on_start_server_internal(self, auto_start_mode=False):
        """서버 시작 로직을 처리하는 내부 메서드"""
        ui_logger.debug(f"[AdminPanel] on_start_server_internal 진입, auto_start_mode={auto_start_mode}")

        # 프로세스 종료 후 서버 시작이 요청된 경우를 위한 변수 초기화
        if not hasattr(self, '_start_server_after_kill'):
            self._start_server_after_kill = False
            self._port_to_use = None
            
        # 이미 서버 프로세스가 실행 중인지 확인
        if self._is_datastore_running():
            if not auto_start_mode:
                wx.MessageBox("문서 저장소가 이미 실행 중입니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            else:
                ui_logger.debug("[AdminPanel] on_start_server_internal (auto_start): DataStore already managed and running.")
            return

        try:
            port_to_check_internal = get_datastore_port()
            if port_to_check_internal is None:
                ui_logger.warning("[AdminPanel] on_start_server_internal: Port not configured or is None.")
                if self.main_frame_ref: wx.CallAfter(self.main_frame_ref.SetStatusText, "문서 저장소 시작 실패: 포트가 설정되지 않았습니다.")
                return

            ui_logger.debug(f"[AdminPanel] on_start_server_internal: About to call is_port_in_use with port {port_to_check_internal} (type: {type(port_to_check_internal)})")

            status_msg = f"문서 저장소 시작 중..."
            detailed_status_msg = f"문서 저장소 시작 중입니다. 잠시만 기다려 주세요..."
            self.txt_server_status.SetLabel(status_msg)
            if self.main_frame_ref:
                wx.CallAfter(self.main_frame_ref.SetStatusText, detailed_status_msg)

            self._start_datastore()

            while not self._is_datastore_running():
                time.sleep(1)

            self._update_ui_for_server_running()

            status_msg = f"DataStore is Started"
            detailed_status_msg = f"문서 저장소가 시작되었습니다. ※ 모든 파일 정보는 개인 PC에서만 활용됩니다."
            self.txt_server_status.SetLabel(status_msg)
            if self.main_frame_ref:
                wx.CallAfter(self.main_frame_ref.SetStatusText, detailed_status_msg)
            ui_logger.info(f"[AdminPanel] DataStore process started. Log monitoring initiated.")
            
            self.on_start_monitoring(None)
        except Exception as e_monitor:
            ui_logger.exception(f"[AdminPanel] Error during on_start_monitoring: {e_monitor}")
            wx.LogError(f"모니터링 시작 중 오류 발생: {e_monitor}")

        except Exception as e:
            ui_logger.exception('문서 저장소 시작 오류')
            error_message = str(e) if e else "Unknown error"
            wx.LogError(f"Failed to start DataStore: {error_message}")
            self.txt_server_status.SetLabel("DataStore Status: Error starting")
            if self.main_frame_ref: 
                wx.CallAfter(self.main_frame_ref.SetStatusText, "문서 저장소 시작 중 오류가 발생했습니다.")
 

    def _run_server_when_port_in_use(self, default_port_int: int):
        """포트가 사용 중일 때 서버 실행을 위한 포트 선택 및 프로세스 종료/변경 처리 로직을 별도 함수로 분리"""
        # default_port_int는 이미 정수형으로 전달받음
        ui_logger.debug(f"[AdminPanel] *** Port {default_port_int} is already in use! Showing port change dialog. ***")
        
        # 포트 선택 처리 중단 여부를 위한 플래그
        break_out_of_port_selection = False
        
        # 재시도를 통한 포트를 사용하는 프로세스 정보 가져오기
        # 처음 시도에서 실패한 경우가 있을 수 있으므로 재시도
        retry_count = 0
        max_retries = 3
        process_info = None
        
        # 최대 3회까지 프로세스 정보 가져오기 시도
        while retry_count < max_retries:
            process_info, message_text = get_process_using_port(default_port_int)
            if process_info:
                ui_logger.debug(f"[AdminPanel] Successfully found process using port {default_port_int} on attempt {retry_count+1}")
                break
            ui_logger.debug(f"[AdminPanel] Retry {retry_count+1}/{max_retries} to find process using port {default_port_int}")
            retry_count += 1
            time.sleep(0.5)  # 재시도 전 잠시 대기
        
        if len(message_text) > 0:
            message_text += "\n\n"

        # 사용자 선택 대화상자 표시
        if threading.current_thread() is threading.main_thread():
            dlg = wx.MessageDialog(
                self, 
                message_text  + "실행 중인 프로세스를 종료하고 문서 저장소를 기본 포트로 시작할까요?",
                "포트 충돌: 프로세스 처리 방법 선택",
                wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION
            )
            dlg.SetYesNoLabels("프로세스 종료 후 계속", "다른 포트 사용")
            result = dlg.ShowModal()
            dlg.Destroy()
            
            if result == wx.ID_YES:  # 프로세스 종료 선택
                if kill_process_by_pids(process_info['pid']):
                    ui_logger.info(f"[AdminPanel] Successfully killed process")
                    wx.MessageBox(f"{default_port_int} 포트를 사용하는 프로세스가 종료되었습니다. 기본 포트로 재시작합니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                        
                if is_port_in_use(default_port_int):
                    ui_logger.info(f"[AdminPanel] Port {default_port_int} is still in use after killing process. Asking for different port.")
                    wx.MessageBox(f"포트 {default_port_int}를 사용하는 프로세스를 종료할 수 없습니다. 다른 포트를 선택해주세요.", "정보", wx.OK | wx.ICON_INFORMATION)
                    default_port_int = self._show_port_change_dialog()
                    if default_port_int is not None:
                        save_port_config(default_port_int)
                    else:
                        return
            elif result == wx.ID_NO:  # 다른 포트 사용 선택
                ui_logger.info(f"[AdminPanel] User chose to use a different port")
                default_port_int = self._show_port_change_dialog()
                if default_port_int is not None:
                    save_port_config(default_port_int)
                else:
                    return
            else:  # 취소 선택
                ui_logger.info(f"[AdminPanel] User canceled the operation")
                default_port_int = None  
    
                ui_logger.debug(f"[AdminPanel] User canceled port change dialog. Aborting DataStore start.")
                wx.CallAfter(self._append_log_message, f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 문서 저장소 시작이 취소되었습니다. ---")
                self.txt_server_status.SetLabel("DataStore Status: Startup canceled by user")
                if self.main_frame_ref:
                    wx.CallAfter(self.main_frame_ref.SetStatusText, "문서 저장소 시작이 취소되었습니다.")
                return


        status_msg = f"DataStore is Starting..."
        detailed_status_msg = f"문서 저장소 시작 중입니다. 잠시만 기다려 주세요..."
        self.txt_server_status.SetLabel(status_msg)
        if self.main_frame_ref:
            wx.CallAfter(self.main_frame_ref.SetStatusText, detailed_status_msg)
        ui_logger.info(f"[AdminPanel] DataStore process started. Log monitoring initiated.")

        self._start_datastore()
        time.sleep(10)

        while not self._is_datastore_running():
            time.sleep(2)

        #wx.CallAfter(self._update_ui_for_server_running())
        self._update_ui_for_server_running()

        status_msg = f"DataStore is Started."
        detailed_status_msg = f"문서 저장소가 시작되었습니다. ※ 모든 파일 정보는 개인 PC에서만 활용됩니다."
        self.txt_server_status.SetLabel(status_msg)
        if self.main_frame_ref:
            wx.CallAfter(self.main_frame_ref.SetStatusText, detailed_status_msg)
        ui_logger.info(f"[AdminPanel] DataStore process started. Log monitoring initiated.")

        # API 클라이언트 URL 업데이트
        save_port_config(default_port_int)
        self._force_document_refresh()

    def _start_datastore(self):
        ui_logger.debug("[AdminPanel] _start_datastore 진입")
        port = get_datastore_port()

        python_path = os.path.join(os.getcwd(), "private_devbot_conda", "python.exe")
        ui_logger.debug(f"실행할 python.exe 위치: {python_path}")
        main_py_dir = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(), "main.py")))
        self.datastore_process = subprocess.Popen(
            [python_path, "main.py", "--port", str(port)],
            cwd=main_py_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            encoding='utf-8',
            errors='replace'
        )

        threading.Thread(
            target=self._handle_datastore_stdout,
            args=(self.datastore_process.stdout,),
            daemon=True
        ).start()

    def _handle_datastore_stdout(self, stream):
        try:
            for line in iter(stream.readline, ''):
                if line is None or line == "" or len(line) <= 5:
                    time.sleep(0.5)
                    continue

                if "Application startup complete." in line:
                    self.is_datastore_running = True

                ui_logger.debug(f"[DataStore]: {line.strip()}")
        except ValueError as e: # 스트림이 닫힌 경우 
            ui_logger.exception(f"[DataStore Error] 스트림이 닫혔습니다: {e}") 
        except Exception as e: # 기타 예외 처리 
            ui_logger.exception(f"[DataStore Error] 출력 처리 중 오류 발생: {e}")


    def _stop_datastore(self):
        self.on_stop_monitoring(None)
        shutdown_tread = threading.Thread(target=self._async_stop_datastore)
        shutdown_tread.daemon = True
        shutdown_tread.start()

        while self.datastore_process:
            time.sleep(1)

        self.is_datastore_running = False
        
        self._update_ui_for_server_stopped()

    def _async_stop_datastore(self):
        try:
            subprocess.run(
                [
                    'taskkill',
                    '/F',
                    '/T',
                    '/PID',
                    str(self.datastore_process.pid)
                ],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=10
            )
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            wx.CallAfter(self._append_log_message, 
            
            f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PID {self.datastore_process.pid} 종료 중 오류: {e} ---")
            
            # 2차 시도: psutil 사용
            try:
                import psutil
                process = psutil.Process(self.datastore_process.pid)
                process.kill()  # 강제 종료
                wx.CallAfter(self._append_log_message, 
                    f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PID {self.datastore_process.pid} 강제 종료 완료 ---")
            except:
                pass
        finally:
            self.datastore_process = None

    def on_stop_server(self, event):
        wx.CallAfter(self.main_frame_ref.SetStatusText, f"문서 저장소를 중지 중입니다...")
        self._stop_datastore()
        wx.CallAfter(self.main_frame_ref.SetStatusText, f"문서 저장소를 중지했습니다.")
                
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

    def _is_datastore_running(self):
        try:
            result = self.api_client.check_server_status()
            ui_logger.debug(f"[AdminPanel] _is_datastore_running check_server_status result: {result}")
            if not result or (isinstance(result, dict) and result.get('status') != 'success'):
                return False
            return True
        except Exception as e:
            ui_logger.debug(f"[AdminPanel] _is_datastore_running exception: {e}")
            return False
        
    def _update_ui_for_server_stopped(self):
        """서버가 중지되었을 때 UI 상태를 업데이트합니다."""
        try:
            # 스플래시가 남아있다면 닫기
            #self._hide_loading_splash()

            # UI 버튼 상태 업데이트
            self.btn_start_server.Enable()
            self.btn_stop_server.Disable()
            self._update_button_state(self.btn_start_server)
            self._update_button_state(self.btn_stop_server)
            self.btn_check_port.Enable()
            self.port_input.Enable()
            self._update_button_state(self.btn_check_port)
            
            # 서버 상태 텍스트 업데이트
            self.txt_server_status.SetLabel("문서 저장소 상태: 중지됨")
        except Exception as e:
            ui_logger.exception(f"[AdminPanel] Error updating UI for DataStore stopped: {e}")
            wx.LogError(f"문서 저장소 중지 UI 업데이트 오류: {e}")
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
                
            ui_logger.debug(f"[AdminPanel] on_check_port: About to call is_port_in_use with port {port_to_check} (type: {type(port_to_check)})")
            port_in_use = is_port_in_use(port_to_check)
            
            if not port_in_use:
                wx.MessageBox(f"포트 {port_to_check}는 현재 사용 중이 아닙니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                self.btn_kill_process.Disable()
                self._update_button_state(self.btn_kill_process)
                return
                
            # 프로세스 정보 가져오기
            process_info, message_text = get_process_using_port(port_to_check)
            
            if not process_info:
                wx.MessageBox(f"포트 {port_to_check}는 사용 중이지만, 사용 중인 프로세스 정보를 찾을 수 없습니다.", "정보", wx.OK | wx.ICON_INFORMATION)
                self.btn_kill_process.Disable()
                self._update_button_state(self.btn_kill_process)
                return
            
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
            message = wx.StaticText(info_panel, label=message_text)
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
            self._update_button_state(self.btn_kill_process)
            
            # 현재 확인된 프로세스 정보 저장
            self.current_port_process = process_info
            self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 포트 {port_to_check}를 사용 중인 프로세스 PID {process_info['pid']} 확인됨 ---")
            
        except Exception as e:
            wx.MessageBox(f"포트 확인 중 오류가 발생했습니다: {e}", "오류", wx.OK | wx.ICON_ERROR)
            self.btn_kill_process.Disable()
            self._update_button_state(self.btn_kill_process)
        
    def _kill_process_from_dialog(self, event, process_info, port, dlg=None):
        """대화상자에서 직접 프로세스를 종료합니다."""
        try:
            # 프로세스 종료
            if kill_process_by_pids(process_info['pid']):
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
                self._update_button_state(self.btn_kill_process)
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
        ui_logger.debug("[AdminPanel] 모니터링 시작 버튼 클릭됨")
        if self.monitoring_daemon is None:
            raise ValueError("Monitoring daemon not initialized.")
            
        self.monitoring_daemon.start()
        self.btn_start_monitoring.Disable()
        self.btn_stop_monitoring.Enable()
        self._update_button_state(self.btn_start_monitoring)
        self._update_button_state(self.btn_stop_monitoring)
        self.monitoring_interval_input.Disable()
        self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모니터링 시작 ---")
        
        # 모니터링 결과 업데이트를 위한 타이머 시작
        config = load_json_config()
        interval = int(config['monitoring_interval'])
        ui_logger.info(f"[AdminPanel] 모니터링 타이머 시작: {interval}초 간격")
        self.monitoring_timer.Start(interval * 1000)
        
        # 즉시 결과 UI 업데이트 호출
        wx.CallAfter(self._update_monitoring_result)

    def on_stop_monitoring(self, event):
        """모니터링 중지 버튼 클릭 처리"""
        self.monitoring_daemon.stop()
        self.btn_start_monitoring.Enable()
        self.btn_stop_monitoring.Disable()
        self._update_button_state(self.btn_start_monitoring)
        self._update_button_state(self.btn_stop_monitoring)
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
            ui_logger.exception("모니터링 주기 설정 오류")
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
                    ui_logger.debug(f"[AdminPanel] 추가된 파일 {len(added_files)}개 발견")
                
                # 수정된 파일
                modified_files = result.get("modified_files", [])
                if modified_files:
                    file_changes_text += "  [수정된 파일]\n"
                    for file in modified_files:
                        file_changes_text += f"  - {file}\n"
                    file_changes_text += "\n"
                    # 변경 정보는 중요한 로그이므로 유지
                    ui_logger.debug(f"[AdminPanel] 수정된 파일 {len(modified_files)}개 발견")
                
                # 삭제된 파일
                deleted_files = result.get("deleted_files", [])
                if deleted_files:
                    file_changes_text += "  [삭제된 파일]\n"
                    for file in deleted_files:
                        file_changes_text += f"  - {file}\n"
                    # 변경 정보는 중요한 로그이므로 유지
                    ui_logger.debug(f"[AdminPanel] 삭제된 파일 {len(deleted_files)}개 발견")
                
                total_files = len(added_files) + len(modified_files) + len(deleted_files)
                if total_files != 0:
                    # 마지막 확인 시간 표시
                    last_check_str = last_check_time.strftime("%H:%M:%S")
                    file_changes_text = f"변경 사항 반영 완료: {start_str} - {last_check_str}]\n" + file_changes_text
                
                # 항상 텍스트 업데이트
                if len(self.txt_file_changes_history) > 100:
                    self.txt_file_changes_history.pop(0)

                self.txt_file_changes_history.append(file_changes_text)
                self.txt_file_changes.SetValue('\n'.join(self.txt_file_changes_history))
                
                # 변경된 파일이 있을 때만 파일 변경 내용 업데이트 완료 로그 출력
                if total_files > 0:
                    ui_logger.info("[AdminPanel] 파일 변경 내용 UI 업데이트 완료")
            else:
                self.txt_time_period.SetLabel("- 시작 ~ 종료 시간: 아직 시작되지 않음")
                self.txt_duration.SetLabel("- 걸린 시간: 0시간 0분 0초")
                self.txt_file_changes.SetValue("  아직 변경된 파일이 없습니다.")
                ui_logger.info("[AdminPanel] 모니터링이 아직 시작되지 않았거나 시간 정보가 없음")
        except Exception as e:
            ui_logger.exception(f"[AdminPanel] 모니터링 결과 업데이트 중 오류: {e}")
            self._append_log_message(f"--- [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 모니터링 결과 업데이트 오류: {e} ---")

    def _auto_start_monitoring(self):
        """서버 시작 완료 후 10초 뒤 모니터링 데몬 자동 시작"""
        try:
            if self.btn_start_monitoring.IsEnabled():
                ui_logger.info("[AdminPanel] Auto starting monitoring daemon")
                self.on_start_monitoring(None)
        except Exception as e:
            ui_logger.exception(f"[AdminPanel] Error auto starting monitoring: {e}")