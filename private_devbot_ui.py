import wx
import wx.grid
import wx.html2
import wx.aui
import os
import subprocess
import time

from ui.api_client import ApiClient
from ui.document_management_panel import DocManagementPanel
from ui.admin_panel import AdminPanel
from ui.search_panel import SearchPanel
from ui.config_util import load_json_config, get_config_file, load_initial_json_config
from ui.loading_splash import LoadingSplash
from monitoring_daemon import MonitoringDaemon

# 모던한 색상 테마 정의
MODERN_COLORS = {
    'background': '#FFFFFF',
    'primary': '#2196F3',
    'secondary': '#607D8B',
    'text': '#212121',
    'text_secondary': '#757575',
    'border': '#E0E0E0',
    'hover': '#E3F2FD',
    'selected': '#BBDEFB'
}

class MainFrame(wx.Frame):
    def __init__(self, parent, title, show_ui: bool = True, loading_splash: LoadingSplash | None = None):
        super(MainFrame, self).__init__(parent, title=title, size=(900, 700))
        # 프로그램 아이콘 설정
        icon_path = os.path.join(os.getcwd(), "private_devbot.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))

        self.config = load_json_config(get_config_file())
        self.api_client = ApiClient(self.get_current_config, self.get_current_upload_config)

        # 모던한 색상 테마 적용
        self.SetBackgroundColour(MODERN_COLORS['background'])
        
        # UI 초기화
        self.CreateMenuBar()
        self.CreateStatusBar()
        
        # 상태바 스타일 설정
        self.GetStatusBar().SetBackgroundColour(MODERN_COLORS['background'])
        self.GetStatusBar().SetForegroundColour(MODERN_COLORS['text'])
        
        self.SetStatusText("준비 중...")
        
        # 탭 컨트롤 생성 (AuiNotebook 사용)
        self.notebook = wx.aui.AuiNotebook(self, style=wx.aui.AUI_NB_TOP | wx.aui.AUI_NB_TAB_SPLIT | wx.aui.AUI_NB_TAB_MOVE)
        self.notebook.SetBackgroundColour(MODERN_COLORS['background'])
        
        # 문서 관리 탭
        self.monitoring_daemon = MonitoringDaemon()
        self.doc_panel = DocManagementPanel(self.notebook, self.api_client, main_frame_ref=self, monitoring_daemon=self.monitoring_daemon)
        self.search_panel = SearchPanel(self.notebook, self.api_client)
        self.admin_panel = AdminPanel(self.notebook, self.api_client, main_frame_ref=self, monitoring_daemon=self.monitoring_daemon)

        self.notebook.AddPage(self.doc_panel, "Documents")
        self.notebook.AddPage(self.search_panel, "Search")
        self.notebook.AddPage(self.admin_panel, "Admin")

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self.Layout()
        self.Center()

        # UI 즉시 표시 여부 (스플래시가 먼저 나와야 할 때는 False)
        if show_ui:
            self.Show(True)
        else:
            # 프레임은 생성하되 숨겨두기
            self.Hide()

        # 스플래시 핸들 저장
        self.loading_splash = loading_splash

        self.Bind(wx.EVT_CLOSE, self.on_close)

        # 서버 자동 시작
        self.SetStatusText("문서 저장소 시작 중입니다. 잠시만 기다려주세요...")
        if self.admin_panel:
            # 진행 대화상자를 사용하지 않고 상태표시줄만 사용하여 이벤트 루프 충돌 방지
            wx.CallAfter(self.auto_start_server)
            
        # 서버 준비 상태를 주기적으로 확인하여 스플래시를 닫고 UI 표시
        if not show_ui:
            wx.CallLater(500, self._check_server_ready)

    def auto_start_server(self):
        """프로그램 시작 시 서버 자동 시작"""
        try:
            # 진행 대화상자를 사용하지 않고 상태 표시줄만 사용하여 이벤트 루프 충돌 납지
            self.SetStatusText("문서 저장소 서버를 시작하는 중...")
            
            # 관리자 패널의 서버 시작 메서드 호출
            if hasattr(self, 'admin_panel') and self.admin_panel:
                # 서버 시작
                self.admin_panel.auto_start_server(self.on_server_fully_ready_for_docs)
                
                # # 서버 시작 진행 상황을 간단히 5초 동안 상태바에 표시
                # for i in range(5):
                #     self.SetStatusText(f"문서 저장소 서버를 시작하는 중... ({i+1}/5)")
                #     time.sleep(1.0)

                # 서버 시작 완료 후 상태 텍스트 업데이트 (모니터링 자동 시작은 AdminPanel에서 10초 후 실행)
                self.SetStatusText("문서 저장소 서버가 시작되었습니다.")
                self.monitoring_daemon.start()
                
        except Exception as e:
            wx.LogError(f"서버 자동 시작 중 오류: {e}")
            self.SetStatusText(f"서버 시작 오류: {str(e)}")
            time.sleep(0.5)

    def CreateMenuBar(self):
        menubar = wx.MenuBar()
        fileMenu = wx.Menu()
        settings_item = fileMenu.Append(wx.ID_PREFERENCES, '&Settings...\tCtrl+S', 'Configure application settings')
        fileMenu.AppendSeparator()
        exit_item = fileMenu.Append(wx.ID_EXIT, '&Quit\tCtrl+Q', 'Exit application')
        menubar.Append(fileMenu, '&File')
        self.SetMenuBar(menubar)

        # 메뉴바 스타일 설정
        self.GetMenuBar().SetBackgroundColour(MODERN_COLORS['background'])
        self.GetMenuBar().SetForegroundColour(MODERN_COLORS['text'])

        self.Bind(wx.EVT_MENU, self.on_settings, settings_item)
        self.Bind(wx.EVT_MENU, self.on_quit, exit_item)

    def on_settings(self, event):
        from ui.setting_dialog import SettingsDialog
        from ui.config_util import save_json_config, get_config_file
        dlg = SettingsDialog(self, "Application Settings", self.config)
        if dlg.ShowModal() == wx.ID_OK:
            self.config = dlg.get_configuration()
            save_json_config(get_config_file(), self.config)
            self.SetStatusText("설정이 업데이트되었습니다.")

            # AdminPanel이 존재하고, 모니터링 데몬이 활성 상태인지 확인
            if hasattr(self, 'admin_panel') and self.admin_panel and \
                hasattr(self.admin_panel, 'monitoring_daemon') and \
                self.admin_panel.monitoring_daemon is not None and \
                hasattr(self.admin_panel.monitoring_daemon, 'is_active') and \
                self.admin_panel.monitoring_daemon.is_active():
                
                self.doc_panel.set_monitoring_daemon(self.admin_panel.monitoring_daemon)
                
                print("[MainFrame] 설정 변경 감지: 모니터링 데몬 재시작 시도")
                # 현재 모니터링 중지
                self.admin_panel.on_stop_monitoring(None)
                
                # 잠시 후 새 설정으로 모니터링 다시 시작
                # wx.CallLater를 사용하여 UI 스레드에서 안전하게 호출
                wx.CallLater(200, self.admin_panel.on_start_monitoring, None)
                print("[MainFrame] 모니터링 데몬 재시작 요청 완료")
            elif hasattr(self, 'admin_panel') and self.admin_panel:
                # 모니터링 데몬이 실행 중이 아니거나 admin_panel은 있지만 monitoring_daemon이 없는 경우
                # (예: 초기 실행 시 아직 모니터링 시작 전)
                # 이 경우, 다음 on_start_monitoring 호출 시 새 설정을 사용하게 됨
                print("[MainFrame] 설정 변경 감지: 모니터링 데몬이 실행 중이 아니므로 재시작 건너뜀.")
            
        dlg.Destroy()

    def on_server_fully_ready_for_docs(self, success, message=""):
        """서버가 완전히 준비된 후 호출되는 콜백"""
        if success:
            self.SetStatusText("문서 저장소가 준비되었습니다.")
        else:
            self.SetStatusText(f"문서 저장소 시작 실패: {message}")

    def on_close(self, event):
        """애플리케이션 종료 시 서버가 확실히 종료되도록 처리합니다."""
        admin_panel = self.admin_panel 
        
        # 서버가 실행 중인지 여부 확인
        server_running = False
        server_pid = None
        
        if admin_panel and hasattr(admin_panel, 'server_process') and admin_panel.server_process:
            if admin_panel.server_process.poll() is None: 
                server_running = True
                server_pid = admin_panel.server_process.pid
                
        if server_running and server_pid:
            # 사용자에게 서버 종료에 대한 확인 메시지 표시
            if wx.MessageBox("백엔드 서버가 실행 중입니다. 종료하기 전에 서버를 중지하시겠습니까?",
                                "Confirm Exit",
                                wx.ICON_QUESTION | wx.YES_NO) == wx.YES:
                try:
                    self.SetStatusText("서버를 종료하는 중...")
                    
                    # 타임아웃을 통한 비동기 종료 처리 - subprocess 사용 방식
                    try:
                        # 강제 종료를 위한 커맨드 실행 - UI 블록 방지를 위한 타임아웃 설정
                        subprocess.run(['taskkill', '/F', '/T', '/PID', str(server_pid)], 
                                       creationflags=subprocess.CREATE_NO_WINDOW,
                                       timeout=2)  # 2초 타임아웃으로 UI가 내리지 않도록 방지
                        
                        # PID 파일 삭제
                        if hasattr(admin_panel, 'server_pid_file') and admin_panel.server_pid_file:
                            if os.path.exists(admin_panel.server_pid_file):
                                try:
                                    os.remove(admin_panel.server_pid_file)
                                except:
                                    pass
                        
                        # 짧은 대기 시간
                        time.sleep(0.5)
                        
                    except Exception as e:
                        print(f"Error killing server: {e}")
                        
                except Exception as e:
                    print(f"Error during server shutdown: {e}")
        
        # 애플리케이션 종료
        self.Destroy()

    def on_quit(self, event):
        self.Close()

    def get_current_config(self):
        return self.config

    def get_current_upload_config(self):
        return {"chunk_size": 1024 * 1024} # Example

    # -----------------------------------------------------------
    # 스플래시 제어 및 서버 준비 확인
    def _check_server_ready(self):
        """AdminPanel에서 서버가 실행되었는지 확인하고 UI 표시"""
        try:
            ready = hasattr(self, 'admin_panel') and getattr(self.admin_panel, 'server_running', False)
            if ready:
                # 스플래시 닫기
                if self.loading_splash:
                    self.loading_splash.close()
                    self.loading_splash = None

                # 메인 프레임 표시 및 전경으로 가져오기
                if not self.IsShown():
                    self.Show(True)
                self.Raise()
                self.SetStatusText("문서 저장소 서버가 시작되었습니다.")
            else:
                # 아직 준비되지 않았으면 500ms 후 재확인
                wx.CallLater(500, self._check_server_ready)
        except Exception as e:
            print(f"[MainFrame] 서버 준비 확인 중 오류: {e}")

class App(wx.App):
    def OnInit(self):
        from ui.config_util import get_config_file, load_json_config, save_json_config
        from ui.setting_dialog import SettingsDialog
        from ip_middleware import get_local_ips
        config_path = get_config_file()
        print(config_path)
        config = load_initial_json_config(config_path)
        
        need_input = False
        if not config.get('knox_id'):
            need_input = True
        if not config.get('client_ip'):
            ips = list(get_local_ips())
            print("-------------------------------")
            print(ips)
            print("-------------------------------")
            config['client_ip'] = ips[0] if ips else ''
            need_input = True
        if not config.get('port'):
            config['port'] = '8123'
            need_input = True
        if need_input:
            dlg = SettingsDialog(None, "Application Settings", config)
            if dlg.ShowModal() == wx.ID_OK:
                config = dlg.get_configuration()
                # api_base_url 동적 생성
                config['api_base_url'] = f"http://{config['client_ip']}:{config['port']}"
                save_json_config(config_path, config)
            dlg.Destroy()
        # config 값이 있더라도 api_base_url을 항상 동적으로 생성
        if config.get('client_ip') and config.get('port'):
            config['api_base_url'] = f"http://{config['client_ip']}:{config['port']}"
            save_json_config(config_path, config)

        # 1) 스플래시 먼저 표시
        gif_path = os.path.join(os.getcwd(), "loading.gif")
        self.splash = LoadingSplash(None, gif_path)
        self.splash.Show()

        # 2) 메인 프레임은 숨긴 상태로 생성 (스플래시 유지)
        self.main_frame = MainFrame(None, 'Private DevBot UI', show_ui=False, loading_splash=self.splash)

        # MainLoop로 진입 (스플래시가 화면에 보임)
        return True

if __name__ == '__main__':
    app = App(False)
    app.MainLoop()