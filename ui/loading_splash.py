import wx
import wx.adv
import os

class LoadingSplash(wx.Frame):
    """서버가 준비될 때까지 애니메이션 GIF를 표시하는 간단한 스플래시 창"""

    def __init__(self, parent=None, gif_path="loading.gif"):
        style = wx.NO_BORDER | wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP
        super().__init__(parent, title="Loading", style=style)

        # GIF 애니메이션 컨트롤 준비
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)

        if os.path.exists(gif_path):
            # GIF 존재 시 애니메이션으로 표시
            anim = wx.adv.Animation(gif_path)
            ctrl = wx.adv.AnimationCtrl(self, id=wx.ID_ANY, style=wx.adv.AC_DEFAULT_STYLE)
            ctrl.SetAnimation(anim)
            ctrl.Play()
            sizer.Add(ctrl, 1, wx.EXPAND)
            self.SetClientSize(anim.GetSize())
        else:
            # GIF 미존재 시 텍스트로 대체
            txt = wx.StaticText(self, label="Loading...")
            sizer.Add(txt, 1, wx.ALIGN_CENTER|wx.ALL, 20)
            self.Fit()

        # 화면 중앙 배치
        self.Center()

    def close(self):
        """스플래시 창을 닫습니다."""
        if self and self.IsShown():
            self.Destroy() 