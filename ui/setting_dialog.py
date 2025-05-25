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

        # Knox ID
        hbox_knox = wx.BoxSizer(wx.HORIZONTAL)
        lbl_knox = wx.StaticText(panel, label='Knox ID:')
        self.txt_knox = wx.TextCtrl(panel, value=self.config.get('knox_id', ''))
        hbox_knox.Add(lbl_knox, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        hbox_knox.Add(self.txt_knox, proportion=1, flag=wx.EXPAND)
        panel_vbox.Add(hbox_knox, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Client IP
        hbox_client_ip = wx.BoxSizer(wx.HORIZONTAL)
        lbl_client_ip = wx.StaticText(panel, label='내 PC IP:')
        self.txt_client_ip = wx.TextCtrl(panel, value=self.config.get('client_ip', ''))
        hbox_client_ip.Add(lbl_client_ip, flag=wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border=8)
        hbox_client_ip.Add(self.txt_client_ip, proportion=1, flag=wx.EXPAND)
        panel_vbox.Add(hbox_client_ip, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # Port
        hbox_port = wx.BoxSizer(wx.HORIZONTAL)
        lbl_port = wx.StaticText(panel, label='포트:')
        self.txt_port = wx.TextCtrl(panel, value=str(self.config.get('port', '8123')))
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
        knox_id = self.txt_knox.GetValue().strip()
        client_ip = self.txt_client_ip.GetValue().strip()
        port = self.txt_port.GetValue().strip()

        # Knox ID 필수
        if not knox_id:
            wx.MessageBox("Knox ID를 입력해주세요.", "오류", wx.OK | wx.ICON_ERROR)
            return
        # IP 주소 유효성 검사
        try:
            socket.inet_aton(client_ip)
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

        self.config['knox_id'] = knox_id
        self.config['client_ip'] = client_ip
        self.config['port'] = port
        self.EndModal(wx.ID_OK)

    def get_configuration(self):
        return self.config