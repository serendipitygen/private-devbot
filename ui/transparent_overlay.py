# 필요한 패키지 import
import wx

# 반투명 오버레이 패널 클래스 - 로딩 중 화면을 어둡게 처리
# 참고: https://wiki.wxpython.org/OverlayWindow
class TransparentOverlay(wx.Panel):
    def __init__(self, parent, message="문서 목록을 읽고 있습니다", alpha=120):
        wx.Panel.__init__(self, parent, -1, style=wx.TRANSPARENT_WINDOW)
        self.parent = parent
        self.message = message
        self.alpha = alpha  # 0-255, 0은 투명, 255는 막히는 정도 (더 낮은 값을 사용하여 덕게 표시)
        
        # 배경 색상 - 검은색 투명하게
        self.SetBackgroundColour(wx.BLACK)
        self.SetTransparent(self.alpha)
        
        # 중앙 패널 (흰색 배경의 반투명 패널)
        self.center_panel = wx.Panel(self)
        self.center_panel.SetBackgroundColour(wx.Colour(255, 255, 255, 200))
        
        # 메세지 텍스트
        self.text = wx.StaticText(self.center_panel, -1, self.message, style=wx.ALIGN_CENTER)
        font = self.text.GetFont()
        font.SetPointSize(12)
        self.text.SetFont(font)
        
        # 로딩 애니메이션 이미지 추가
        # wxPython에서 ActivityIndicator를 사용
        self.activity_indicator = wx.ActivityIndicator(self.center_panel)
        self.activity_indicator.Start()
        
        # 중앙 패널 레이아웃
        center_sizer = wx.BoxSizer(wx.VERTICAL)
        center_sizer.Add(self.activity_indicator, 0, wx.ALIGN_CENTER | wx.TOP, 15)
        center_sizer.Add(self.text, 0, wx.ALIGN_CENTER | wx.ALL, 15)
        self.center_panel.SetSizer(center_sizer)
        
        # 전체 레이아웃
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(self.center_panel, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        sizer.AddStretchSpacer(1)
        self.SetSizer(sizer)
        
        # 화면 크기에 맞게 오버레이 상태 유지
        self.parent.Bind(wx.EVT_SIZE, self.on_parent_resize)
        
        # 처음에는 숨김
        self.Hide()
        
    def on_parent_resize(self, event):
        """Parent 패널 크기가 변경되면 오버레이 크기도 자동 조정"""
        parent_size = self.parent.GetSize()
        self.SetSize(parent_size)
        self.Layout()
        event.Skip()
        
    def show(self, message=None):
        """ 오버레이 화면 표시 """
        if message:
            self.message = message
            self.text.SetLabel(self.message)
        
        # 해당 패널의 크기에 맞게 오버레이 크기 재설정
        parent_size = self.parent.GetSize()
        self.SetSize(parent_size)
        
        # 애니메이션 시작 (ActivityIndicator는 이미 Start() 상태)
        
        # 화면 최상위에 표시
        self.Show()
        self.parent.Refresh()
        self.parent.Update()
        self.Layout()
        
    def hide(self):
        """ 오버레이 화면 숨김 """
        # ActivityIndicator는 계속 실행 상태로 두고 패널만 숨김
        self.Hide()
        self.parent.Refresh()
        self.parent.Update()
        
    # 타이머 및 게이지 관련 메소드 제거 (ActivityIndicator 사용으로 필요없음)