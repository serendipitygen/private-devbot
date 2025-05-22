# 필요한 Import 구문
import wx
import socket

# --- UI Panels ---
class SettingsDialog(wx.Dialog):
    def __init__(self, parent, title, current_config):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.config = current_config.copy() 

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)

        panel = wx.Panel(self)
        panel_vbox = wx.BoxSizer(wx.VERTICAL)

        # IP 주소 설정
        hbox_ip = wx.BoxSizer(wx.HORIZONTAL)
        lbl_ip = wx.StaticText(panel, label='서버 IP 주소:')
        self.txt_ip = wx.TextCtrl(panel, value=self.config.get('api_base_url', 'http://localhost:8125').split('://')[1].split(':')[0])
        hbox_ip.Add(lbl_ip, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        hbox_ip.Add(self.txt_ip, proportion=1, flag=wx.EXPAND)
        panel_vbox.Add(hbox_ip, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # 포트 설정
        hbox_port = wx.BoxSizer(wx.HORIZONTAL)
        lbl_port = wx.StaticText(panel, label='포트:')
        self.txt_port = wx.TextCtrl(panel, value=self.config.get('api_base_url', 'http://localhost:8125').split(':')[-1])
        hbox_port.Add(lbl_port, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        hbox_port.Add(self.txt_port, proportion=1, flag=wx.EXPAND)
        panel_vbox.Add(hbox_port, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        
        panel.SetSizer(panel_vbox)
        dialog_sizer.Add(panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        std_button_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        if std_button_sizer:
            dialog_sizer.Add(std_button_sizer, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)

        self.SetSizerAndFit(dialog_sizer)
        self.CenterOnParent()

        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CANCEL), id=wx.ID_CANCEL)

    def on_ok(self, event):
        ip = self.txt_ip.GetValue().strip()
        port = self.txt_port.GetValue().strip()
        
        # IP 주소 유효성 검사
        try:
            socket.inet_aton(ip)
        except socket.error:
            wx.MessageBox("유효한 IP 주소를 입력해주세요.", "오류", wx.OK | wx.ICON_ERROR)
            return
            
        # 포트 번호 유효성 검사
        try:
            port_num = int(port)
            if not (1 <= port_num <= 65535):
                raise ValueError
        except ValueError:
            wx.MessageBox("유효한 포트 번호(1-65535)를 입력해주세요.", "오류", wx.OK | wx.ICON_ERROR)
            return
            
        self.config['api_base_url'] = f"http://{ip}:{port}"
        self.EndModal(wx.ID_OK)

    def get_configuration(self):
        return self.config