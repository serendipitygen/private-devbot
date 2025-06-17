import wx
import threading
import time
import json
import datetime
import websocket  # websocket-client 패키지 필요
import requests
import wx.grid
from ui.ui_setting import MODERN_COLORS

UPLOAD_WS_URL = "ws://localhost:8123/ws/upload_status"  # 포트는 환경에 맞게 변경
QUEUE_STATUS_URL = "http://localhost:8123/upload_queue_status"

class UploadStatusPanel(wx.Panel):
    def __init__(self, parent, upload_queue_manager):
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(MODERN_COLORS['notebook_background'])
        self.upload_queue_manager = upload_queue_manager
        self.upload_list = []  # 업로드 상태 리스트
        self.ws = None
        self.ws_thread = None
        self.poll_thread = None
        self.running = True

        # 메인 사이저
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 상태 정보 섹션
        status_box = wx.StaticBox(self, label="업로드 상태")
        status_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)
        status_box.SetForegroundColour(MODERN_COLORS['title_text'])
        
        # 큐 상태 정보
        queue_info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.queue_status_text = wx.StaticText(self, label="대기 중인 파일: 0건, 남은 용량: 10000건")
        self.btn_clear_completed = wx.Button(self, label="완료된 항목 지우기")
        self.btn_clear_completed.SetBackgroundColour(MODERN_COLORS['button_background'])
        
        queue_info_sizer.Add(self.queue_status_text, 1, wx.ALIGN_CENTER_VERTICAL)
        queue_info_sizer.Add(self.btn_clear_completed, 0, wx.LEFT, 10)
        
        status_sizer.Add(queue_info_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(status_sizer, 0, wx.EXPAND)
        
        # 업로드 목록 그리드
        self.grid = wx.grid.Grid(self)
        self.grid.CreateGrid(0, 5)
        self.grid.SetColLabelValue(0, "파일명")
        self.grid.SetColLabelValue(1, "경로")
        self.grid.SetColLabelValue(2, "상태")
        self.grid.SetColLabelValue(3, "추가 시간")
        self.grid.SetColLabelValue(4, "완료 시간")
        
        # 컬럼 너비 설정
        self.grid.SetColSize(0, 200)  # 파일명
        self.grid.SetColSize(1, 300)  # 경로
        self.grid.SetColSize(2, 100)  # 상태
        self.grid.SetColSize(3, 150)  # 추가 시간
        self.grid.SetColSize(4, 150)  # 완료 시간
        
        # 그리드 스타일 설정
        self.grid.SetBackgroundColour(MODERN_COLORS['list_background'])
        self.grid.EnableEditing(False)
        
        main_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)
        
        # 이벤트 바인딩
        self.btn_clear_completed.Bind(wx.EVT_BUTTON, self.on_clear_completed)
        
        # 업로드 큐 매니저 이벤트 구독
        self.upload_queue_manager.subscribe('file_added', self.on_file_added)
        self.upload_queue_manager.subscribe('file_completed', self.on_file_completed)
        self.upload_queue_manager.subscribe('file_failed', self.on_file_failed)
        
        self.SetSizer(main_sizer)
        self.Layout()
        
        # 상태 업데이트 타이머
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_queue_status)
        self.timer.Start(1000)  # 1초마다 업데이트
        
        # WebSocket 및 폴링 스레드 시작
        self.start_ws_thread()
        self.start_poll_thread()

    def start_ws_thread(self):
        def run_ws():
            try:
                self.ws = websocket.WebSocketApp(
                    UPLOAD_WS_URL,
                    on_message=self.on_ws_message,
                    on_error=self.on_ws_error,
                    on_close=self.on_ws_close
                )
                self.ws.on_open = self.on_ws_open
                self.ws.run_forever()
            except Exception as e:
                wx.CallAfter(self.queue_status_text.SetLabel, f"WebSocket 연결 실패: {e}")
        self.ws_thread = threading.Thread(target=run_ws, daemon=True)
        self.ws_thread.start()

    def on_ws_open(self, ws):
        wx.CallAfter(self.queue_status_text.SetLabel, "서버와 실시간 업로드 상태 연결됨")

    def on_ws_close(self, ws, code, msg):
        wx.CallAfter(self.queue_status_text.SetLabel, "WebSocket 연결 종료")

    def on_ws_error(self, ws, error):
        wx.CallAfter(self.queue_status_text.SetLabel, f"WebSocket 오류: {error}")

    def on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            filename = data.get("filename", "")
            filepath = data.get("filepath", "")
            mtime = data.get("mtime", 0)
            status = data.get("status", "")
            msg = data.get("result", {}).get("message", "") if status == "done" else data.get("error", "")
            mtime_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S") if mtime else ""
            wx.CallAfter(self.update_or_append_row, filename, filepath, mtime_str, status, msg)
        except Exception as e:
            wx.CallAfter(self.queue_status_text.SetLabel, f"메시지 처리 오류: {e}")

    def update_or_append_row(self, filename, filepath, mtime_str, status, msg):
        # 이미 있는 파일이면 상태만 갱신, 없으면 추가
        found = False
        for idx in range(self.grid.GetNumberRows()):
            if self.grid.GetCellValue(idx, 0) == filename and self.grid.GetCellValue(idx, 1) == filepath:
                self.grid.SetCellValue(idx, 2, self.status_to_kor(status))
                self.grid.SetCellValue(idx, 4, mtime_str)
                found = True
                break
        if not found:
            row = self.grid.GetNumberRows()
            self.grid.AppendRows(1)
            self.grid.SetCellValue(row, 0, filename)
            self.grid.SetCellValue(row, 1, filepath)
            self.grid.SetCellValue(row, 2, self.status_to_kor(status))
            self.grid.SetCellValue(row, 3, mtime_str)
            self.grid.SetCellValue(row, 4, mtime_str)

    def status_to_kor(self, status):
        if status == "pending":
            return "대기"
        elif status == "done":
            return "완료"
        elif status == "error":
            return "실패"
        return status

    def start_poll_thread(self):
        def poll():
            while self.running:
                try:
                    resp = requests.get(QUEUE_STATUS_URL, timeout=3)
                    if resp.status_code == 200:
                        data = resp.json()
                        remaining = data.get("remaining_capacity", 0)
                        queue_size = data.get("queue_size", 0)
                        wx.CallAfter(self.queue_status_text.SetLabel, f"현재 업로드 대기열: {queue_size}건 / 남은 업로드 가능: {remaining}건")
                        if remaining <= 0:
                            wx.CallAfter(self.queue_status_text.SetForegroundColour, wx.Colour(200,0,0))
                        else:
                            wx.CallAfter(self.queue_status_text.SetForegroundColour, wx.Colour(0,80,0))
                except Exception:
                    wx.CallAfter(self.queue_status_text.SetLabel, "서버 상태 조회 실패")
                time.sleep(5)
        self.poll_thread = threading.Thread(target=poll, daemon=True)
        self.poll_thread.start()

    def update_queue_status(self, event):
        """큐 상태 정보를 업데이트합니다."""
        queue_size = self.upload_queue_manager.get_queue_size()
        remaining = self.upload_queue_manager.get_remaining_capacity()
        self.queue_status_text.SetLabel(f"대기 중인 파일: {queue_size}건, 남은 용량: {remaining}건")
        
    def on_file_added(self, file_info):
        """새 파일이 추가되었을 때 호출됩니다."""
        wx.CallAfter(self._add_file_to_grid, file_info)
        
    def on_file_completed(self, file_info):
        """파일 처리가 완료되었을 때 호출됩니다."""
        wx.CallAfter(self._update_file_status, file_info)
        
    def on_file_failed(self, file_info):
        """파일 처리 실패 시 호출됩니다."""
        wx.CallAfter(self._update_file_status, file_info)
        
    def _add_file_to_grid(self, file_info):
        """그리드에 새 파일을 추가합니다."""
        row = self.grid.GetNumberRows()
        self.grid.AppendRows(1)
        
        self.grid.SetCellValue(row, 0, file_info['file_name'])
        self.grid.SetCellValue(row, 1, file_info['file_path'])
        self.grid.SetCellValue(row, 2, "대기 중")
        self.grid.SetCellValue(row, 3, datetime.datetime.fromtimestamp(file_info['added_time']).strftime("%Y-%m-%d %H:%M:%S"))
        
    def _update_file_status(self, file_info):
        """파일 상태를 업데이트합니다."""
        for row in range(self.grid.GetNumberRows()):
            if self.grid.GetCellValue(row, 1) == file_info['file_path']:
                status = "완료" if file_info['status'] == 'completed' else f"실패: {file_info.get('error', '')}"
                self.grid.SetCellValue(row, 2, status)
                if file_info['status'] == 'completed':
                    self.grid.SetCellValue(row, 4, datetime.datetime.fromtimestamp(file_info['completed_time']).strftime("%Y-%m-%d %H:%M:%S"))
                break
                
    def on_clear_completed(self, event):
        """완료된 항목을 그리드에서 제거합니다."""
        rows_to_delete = []
        for row in range(self.grid.GetNumberRows()):
            if self.grid.GetCellValue(row, 2) == "완료":
                rows_to_delete.append(row)
                
        # 뒤에서부터 삭제 (인덱스가 변경되지 않도록)
        for row in sorted(rows_to_delete, reverse=True):
            self.grid.DeleteRows(row)

    def Destroy(self):
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        return super().Destroy()

# 사용 예시 (탭에 추가)
if __name__ == "__main__":
    app = wx.App(False)
    frame = wx.Frame(None, title="파일 업로드 상태 테스트", size=(950, 500))
    panel = UploadStatusPanel(frame, None)
    frame.Show()
    app.MainLoop()
