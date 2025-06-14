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
from ui.config_util import load_json_config, load_initial_json_config
from ui.loading_splash import LoadingSplash
from monitoring_daemon import MonitoringDaemon
from ui.ui_setting import MODERN_COLORS
from logger_util import ui_logger


class CustomTabArt(wx.aui.AuiDefaultTabArt):
    def __init__(self):
        super().__init__()

    def DrawBackground(self, dc, wnd, rect):
        # 배경을 노트북 배경색으로 채워서 테두리 문제 해결
        dc.SetBrush(wx.Brush(MODERN_COLORS['notebook_background']))
        dc.SetPen(wx.Pen(MODERN_COLORS['notebook_background']))
        dc.DrawRectangle(rect)

    def GetColour(self, id):
        if id == wx.aui.AUI_TAB_COLOUR_BACKGROUND:
            return MODERN_COLORS['notebook_background']
        return super().GetColour(id)

    def GetActiveColour(self, id):
        if id == wx.aui.AUI_TAB_COLOUR_BACKGROUND:
            return MODERN_COLORS['selected']
        return super().GetActiveColour(id)




class MainFrame(wx.Frame):
    def __init__(self, parent, title, show_ui: bool = True, loading_splash: LoadingSplash | None = None):
        super(MainFrame, self).__init__(parent, title=title, size=(1000, 800))

        self.FONT_LIST = {
            'title_font': wx.Font(15, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        }

        # 프로그램 아이콘 설정
        icon_path = os.path.join(os.getcwd(), "private_devbot.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))

        # 모던한 색상 테마 적용
        self.SetBackgroundColour(MODERN_COLORS['notebook_background'])
        
        # UI 초기화
        self.CreateMenuBar()
        self.CreateStatusBar()
        
        # 상태바 스타일 설정
        self.GetStatusBar().SetBackgroundColour(MODERN_COLORS['background'])
        self.GetStatusBar().SetForegroundColour(MODERN_COLORS['text'])
        
        self.SetStatusText("준비 중...")
        
        # 탭 컨트롤 생성 (AuiNotebook 사용)
        self.notebook = wx.aui.AuiNotebook(self, style=wx.aui.AUI_NB_TOP | wx.aui.AUI_NB_TAB_SPLIT | wx.aui.AUI_NB_TAB_MOVE | wx.BORDER_NONE)
        self.notebook.SetBackgroundColour(MODERN_COLORS['notebook_background'])

        # 사용자 정의 탭 아트 제공자 설정
        art = CustomTabArt()
        self.notebook.SetArtProvider(art)
        
        self.notebook.SetThemeEnabled(True)
        
        self.monitoring_daemon:MonitoringDaemon = MonitoringDaemon(main_frame_ref=self)
        
        self.api_client:ApiClient = ApiClient(self.get_current_upload_config, monitoring_daemon=self.monitoring_daemon)
        self.doc_panel:DocManagementPanel = DocManagementPanel(self.notebook, api_client=self.api_client, main_frame_ref=self, monitoring_daemon=self.monitoring_daemon)
        self.search_panel:SearchPanel = SearchPanel(self.notebook, api_client=self.api_client)
        self.admin_panel:AdminPanel = AdminPanel(self.notebook, api_client=self.api_client, main_frame_ref=self, monitoring_daemon=self.monitoring_daemon)

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
        status_bar = self.GetStatusBar()
        status_bar.SetBackgroundColour(MODERN_COLORS['status_background'])
        if self.admin_panel:
            # 진행 대화상자를 사용하지 않고 상태표시줄만 사용하여 이벤트 루프 충돌 방지
            wx.CallAfter(self.auto_start_server)
            
        # 서버 준비 상태를 주기적으로 확인하여 스플래시를 닫고 UI 표시
        if not show_ui:
            wx.CallLater(500, self._check_server_ready)

    def auto_start_server(self):
        """프로그램 시작 시 서버 자동 시작"""
        try:
            #self.loading_splash.Show()
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
        from ui.config_util import save_json_config
        dlg = SettingsDialog(self, "Application Settings", load_json_config())
        if dlg.ShowModal() == wx.ID_OK:
            config = dlg.get_configuration()
            save_json_config(config)
            self.SetStatusText("설정이 업데이트되었습니다.")

            # AdminPanel이 존재하고, 모니터링 데몬이 활성 상태인지 확인
            if hasattr(self, 'admin_panel') and self.admin_panel and \
                hasattr(self.admin_panel, 'monitoring_daemon') and \
                self.admin_panel.monitoring_daemon is not None and \
                hasattr(self.admin_panel.monitoring_daemon, 'is_active') and \
                self.admin_panel.monitoring_daemon.is_active():
                
                self.doc_panel.set_monitoring_daemon(self.admin_panel.monitoring_daemon)
                
                ui_logger.info("[MainFrame] 설정 변경 감지: 모니터링 데몬 재시작 시도")
                # 현재 모니터링 중지
                self.admin_panel.on_stop_monitoring(None)
                
                # 잠시 후 새 설정으로 모니터링 다시 시작
                # wx.CallLater를 사용하여 UI 스레드에서 안전하게 호출
                wx.CallLater(200, self.admin_panel.on_start_monitoring, None)
                ui_logger.info("[MainFrame] 모니터링 데몬 재시작 요청 완료")
            elif hasattr(self, 'admin_panel') and self.admin_panel:
                # 모니터링 데몬이 실행 중이 아니거나 admin_panel은 있지만 monitoring_daemon이 없는 경우
                # (예: 초기 실행 시 아직 모니터링 시작 전)
                # 이 경우, 다음 on_start_monitoring 호출 시 새 설정을 사용하게 됨
                ui_logger.info("[MainFrame] 설정 변경 감지: 모니터링 데몬이 실행 중이 아니므로 재시작 건너뜀.")
            
        dlg.Destroy()

    def on_server_fully_ready_for_docs(self, success, message=""):
        """서버가 완전히 준비된 후 호출되는 콜백"""
        if success:
            self.SetStatusText("문서 저장소가 준비되었습니다.")
        else:
            self.SetStatusText(f"문서 저장소 시작 실패: {message}")

    def on_close(self, event):
        """애플리케이션 종료 시 서버가 확실히 종료되도록 처리합니다."""
        try:
            # 1. 모니터링 데몬 중지
            if self.admin_panel and self.monitoring_daemon and self.monitoring_daemon.running:
                self.SetStatusText("모니터링을 종료하는 중...")
                self.admin_panel.on_stop_monitoring(None)
                time.sleep(1)  # 데몬이 완전히 멈출 시간을 줌

            # 2. 서버 중지
            if self.admin_panel and self.admin_panel.is_datastore_running:
                self.SetStatusText("서버를 종료하는 중...")
                self.admin_panel.on_stop_server(None)
                time.sleep(0.5) # 서버가 완전히 멈출 시간을 줌

        except Exception as e:
            ui_logger.exception(f"[MainFrame] 종료 처리 중 오류: {e}")
        finally:
            self.Destroy()

    def on_quit(self, event):
        self.Close()

    def get_current_upload_config(self):
        return {"chunk_size": 1024 * 1024}

    # -----------------------------------------------------------
    # 스플래시 제어 및 서버 준비 확인
    def _check_server_ready(self):
        """AdminPanel에서 서버가 실행되었는지 확인하고 UI 표시"""
        try:        
            if self.loading_splash:
                self.loading_splash.close()
                self.loading_splash = None

            # 메인 프레임 표시 및 전경으로 가져오기
            if not self.IsShown():
                self.Show(True)
            self.Raise()
            self.SetStatusText("문서 저장소 서버가 시작되었습니다.")
            
        except Exception as e:
            ui_logger.exception(f"[MainFrame] 서버 준비 확인 중 오류")

class App(wx.App):
    def OnInit(self):
        from ui.config_util import save_json_config
        from ui.setting_dialog import SettingsDialog
        from ip_middleware import get_local_ips

        
        # wx.SystemSettings.SetColour(wx.SYS_COLOUR_BACKGROUND, wx.Colour(245, 236, 213))
        # wx.SystemSettings.SetColour(wx.SYS_COLOUR_FOREGROUND, wx.Colour(240, 187, 120))


        # 1) 스플래시 먼저 표시
        gif_path = os.path.join(os.getcwd(), "loading.gif")
        self.splash = LoadingSplash(None, gif_path=gif_path)

        config = load_initial_json_config()
        
        need_input = False
        if not config.get('knox_id'):
            need_input = True
        if not config.get('client_ip'):
            ips = list(get_local_ips())
            
            ui_logger.debug(ips)
            
            config['client_ip'] = ips[0] if ips else ''
            need_input = True
        if not config.get('port'):
            config['port'] = '8123'
            need_input = True
        if need_input:
            dlg = SettingsDialog(None, "Application Settings", config)
            if dlg.ShowModal() == wx.ID_OK:
                config = dlg.get_configuration()
                save_json_config(config)
            dlg.Destroy()
        
        # 2) 메인 프레임은 숨긴 상태로 생성 (스플래시 유지)
        time.sleep(0.2)
        self.splash.Show()
        time.sleep(0.2)
        self.main_frame = MainFrame(None, 'Private DevBot UI', show_ui=False, loading_splash=self.splash)

        # MainLoop로 진입 (스플래시가 화면에 보임)
        return True

if __name__ == '__main__':
    app = App(False)
    app.MainLoop()