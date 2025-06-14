import wx
import wx.html2
import markdown

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
