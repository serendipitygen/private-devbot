import wx
import email
from email.parser import Parser

import sys
import os

import asyncio

from fastapi import UploadFile
from io import BytesIO

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

#from document_extractor_for_remote_server import DocumentExtractor
from document_reader import DocumentReader


class EMailFrame(wx.Frame):
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(600, 400))

        panel = wx.Panel(self)
        self.text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)

        open_button = wx.Button(panel, label="Open EML File")
        open_button.Bind(wx.EVT_BUTTON, self.on_open_file)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(open_button, 0, wx.ALL | wx.CENTER, 5)
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)

        self.Centre()

        self.extractor = DocumentReader()

    def on_open_file(self, event):
        open_dialog = wx.FileDialog(self, "Open EML File", wildcard="Any files (*.*)|*.*",
                                     style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

        if open_dialog.ShowModal() == wx.ID_CANCEL:
            return

        pathname = open_dialog.GetPath()

        try:
            with open(pathname, "rb") as f:
                file_content = f.read()

            file_name = os.path.basename(pathname)
            file_lie_object = BytesIO(file_content)
            upload_file = UploadFile(filename=file_name, file=file_lie_object)

            contents = asyncio.run(self.extractor.get_contents(upload_file, pathname))

            self.text_ctrl.SetValue(contents['contents'])
        except Exception as e:
            wx.MessageBox(f"Error reading file: {e}", "Error", wx.OK | wx.ICON_ERROR)

class MyApp(wx.App):
    def OnInit(self):
        frame = EMailFrame(None, "EML Reader")
        frame.Show()
        return True

if __name__ == '__main__':
    app = MyApp()
    app.MainLoop()