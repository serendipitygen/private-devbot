import wx
import wx.html2
import markdown
import re

class RagNameDialog(wx.Dialog):
    """새 RAG 이름을 입력받는 다이얼로그.

    • 영문자와 숫자, 최대 10자, 공백 불가.
    • 실시간으로 유효성 검사를 수행하고 OK 버튼을 토글.
    • 이미 존재하는 RAG 이름은 사용할 수 없음.
    """

    def __init__(self, parent, existing_names: list[str]):
        super().__init__(parent, title="RAG 추가", style=wx.DEFAULT_DIALOG_STYLE)

        self.existing_names = set(n.lower() for n in existing_names)

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.msg_label = wx.StaticText(panel, label="새 RAG 이름 입력 (영문자, 숫자로만 공백없이 10자 이내로 작성하세요)")
        vbox.Add(self.msg_label, 0, wx.ALL, 10)

        self.input_ctrl = wx.TextCtrl(panel)
        vbox.Add(self.input_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        self.ok_btn = wx.Button(panel, wx.ID_OK)
        self.ok_btn.Enable(False)
        cancel_btn = wx.Button(panel, wx.ID_CANCEL)
        btn_sizer.AddButton(self.ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(vbox)
        vbox.Fit(self)
        self.CentreOnParent()

        # Bind events
        self.input_ctrl.Bind(wx.EVT_TEXT, self.on_text_change)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def get_name(self) -> str:
        return self.input_ctrl.GetValue().strip()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def on_text_change(self, event):
        name = self.input_ctrl.GetValue().strip()
        is_valid = bool(re.fullmatch(r"[A-Za-z0-9]{1,10}", name)) and name.lower() not in self.existing_names
        self.ok_btn.Enable(is_valid)
        self.msg_label.SetForegroundColour("black" if is_valid else "red")
        event.Skip()


class FileViewerDialog(wx.Dialog):
    def __init__(self, parent, title, content, file_type):
        super(FileViewerDialog, self).__init__(parent, title=title, size=(800, 700), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        is_markdown = file_type in ['.md', '.markdown']

        if is_markdown:
            try:
                # 마크다운 렌더링을 위한 기본 CSS 스타일 추가
                html_header = """
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; padding: 20px; }
                    h1, h2, h3, h4, h5, h6 { border-bottom: 1px solid #dfe2e5; padding-bottom: 0.3em; }
                    code { background-color: rgba(27,31,35,.05); border-radius: 3px; padding: 0.2em 0.4em; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;}
                    pre { background-color: #f6f8fa; border-radius: 3px; padding: 16px; overflow: auto; }
                    pre > code { background-color: transparent; padding: 0; }
                    table { border-collapse: collapse; }
                    th, td { border: 1px solid #dfe2e5; padding: 6px 13px; }
                </style>
                """
                html_body = markdown.markdown(content, extensions=['fenced_code', 'tables'])
                html_content = html_header + html_body
                
                self.viewer = wx.html2.WebView.New(panel)
                self.viewer.SetPage(html_content, "")
            except Exception as e:
                # 마크다운 렌더링 실패 시 텍스트 뷰어로 대체
                is_markdown = False
                content = f"마크다운 렌더링 중 오류가 발생했습니다:\n{e}\n\n--- 원본 내용 ---\n\n{content}"
        
        if not is_markdown:
            self.viewer = wx.TextCtrl(panel, value=content, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
            # 고정폭 글꼴로 설정하여 가독성 향상
            font = wx.Font(11, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            self.viewer.SetFont(font)

        sizer.Add(self.viewer, 1, wx.EXPAND | wx.ALL, 5)

        # 닫기 버튼
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        close_button = wx.Button(panel, label="닫기")
        close_button.Bind(wx.EVT_BUTTON, self.on_close)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(close_button, 0, wx.ALL, 5)
        btn_sizer.AddStretchSpacer()

        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        self.CentreOnParent()

    def on_close(self, event):
        self.Close()
