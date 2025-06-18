import wx
import wx.grid
import threading
import time
import json
import datetime
import requests
import websocket
from typing import Dict, Any
from ui.ui_setting import MODERN_COLORS

class UploadStatusPanel(wx.Panel):
    def __init__(self, parent, upload_queue_manager=None):
        super().__init__(parent)
        self.SetBackgroundColour(MODERN_COLORS['notebook_background'])
        
        self.upload_queue_manager = upload_queue_manager
        self.upload_items = {}
        self.ws = None
        self.ws_thread = None
        self.running = True
        self.completed_files = {}  # 완료된 파일 추적 {file_path: completion_time}
        self.last_processing_file = None  # 이전 폴링에서의 처리 중인 파일
        
        # 포트 설정
        self.port = self._get_port_from_config()
        
        self._init_ui()
        self._setup_websocket()
        self._start_status_timer()
    
    def _get_port_from_config(self):
        """설정 파일에서 포트 번호를 가져옵니다."""
        try:
            import os
            config_path = os.path.join(os.path.dirname(__file__), '..', 'devbot_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get('port', 8123)
        except Exception:
            return 8123
    
    def _init_ui(self):
        """UI 초기화"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 상태 정보 섹션
        status_box = wx.StaticBox(self, label="업로드 큐 상태")
        status_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)
        status_box.SetForegroundColour(MODERN_COLORS['title_text'])
        
        # 큐 상태 표시
        status_info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.status_label = wx.StaticText(self, label="대기 중인 파일: 0건, 남은 용량: 10000건")
        self.status_label.SetForegroundColour(MODERN_COLORS['text'])
        
        self.clear_btn = wx.Button(self, label="완료된 항목 지우기")
        self.clear_btn.SetBackgroundColour(MODERN_COLORS['button_background'])
        self.clear_btn.SetForegroundColour(MODERN_COLORS['button_text'])
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear_completed)
        
        status_info_sizer.Add(self.status_label, 1, wx.ALIGN_CENTER_VERTICAL)
        status_info_sizer.Add(self.clear_btn, 0, wx.LEFT, 10)
        
        status_sizer.Add(status_info_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(status_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # 업로드 목록 그리드
        self.grid = wx.grid.Grid(self)
        self.grid.CreateGrid(0, 6)
        
        # 컬럼 설정
        columns = ["파일명", "경로", "상태", "추가 시간", "완료 시간", "메시지"]
        widths = [200, 300, 100, 150, 150, 200]
        
        for i, (col_name, width) in enumerate(zip(columns, widths)):
            self.grid.SetColLabelValue(i, col_name)
            self.grid.SetColSize(i, width)
        
        # 그리드 스타일
        self.grid.SetBackgroundColour(MODERN_COLORS['list_background'])
        self.grid.SetDefaultCellBackgroundColour(MODERN_COLORS['list_background'])
        self.grid.SetDefaultCellTextColour(MODERN_COLORS['text'])
        self.grid.SetLabelBackgroundColour(MODERN_COLORS['button_background'])
        self.grid.SetLabelTextColour(MODERN_COLORS['button_text'])
        self.grid.EnableEditing(False)
        
        main_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)
        
        # 연결 상태 표시
        self.connection_label = wx.StaticText(self, label="서버 연결 중...")
        self.connection_label.SetForegroundColour(MODERN_COLORS['text'])
        main_sizer.Add(self.connection_label, 0, wx.ALL, 5)
        
        self.SetSizer(main_sizer)
        self.Layout()
    
    def _setup_websocket(self):
        """WebSocket 연결 설정 (현재는 폴링 방식으로 대체)"""
        # WebSocket 연결 대신 폴링으로 상태 확인
        wx.CallAfter(self.connection_label.SetLabel, "폴링 방식으로 서버 상태 확인 중...")
        
        # 업로드 상태 추적을 위한 폴링 시작
        self._start_upload_polling()
    
    def _start_upload_polling(self):
        """업로드 상태 폴링 시작"""
        def poll_upload_status():
            while self.running:
                try:
                    # 큐 상태 확인
                    response = requests.get(f"http://127.0.0.1:{self.port}/upload_queue_status", timeout=3)
                    if response.status_code == 200:
                        queue_data = response.json()
                        queue_size = queue_data.get('queue_size', 0)
                        worker_active = queue_data.get('worker_active', False)
                        current_processing_file = queue_data.get('current_processing_file')
                        
                        # 연결 상태 업데이트
                        status_msg = f"서버 연결됨 (큐: {queue_size}개"
                        if worker_active:
                            status_msg += ", 작업 중)"
                        else:
                            status_msg += ", 대기 중)"
                        
                        wx.CallAfter(self.connection_label.SetLabel, status_msg)
                        
                        # 현재 처리 중인 파일이 있으면 그리드에 표시
                        if current_processing_file:
                            wx.CallAfter(self._update_current_processing_file, current_processing_file)
                        else:
                            # 처리 중인 파일이 없으면 그리드 정리
                            wx.CallAfter(self._clear_processing_files)
                            
                            # 이전에 처리 중이던 파일이 있었다면 완료된 것으로 간주
                            if self.last_processing_file:
                                completed_file = self.last_processing_file.copy()
                                completed_file['status'] = 'completed'
                                completed_file['completed_time'] = time.time()
                                print(f"[DEBUG] 파일 완료 감지: {completed_file.get('file_name', '알 수 없음')}")
                                wx.CallAfter(self._update_current_processing_file, completed_file)
                                wx.CallAfter(self._request_document_refresh)
                        
                        # 현재 처리 중인 파일 상태 저장
                        self.last_processing_file = current_processing_file
                        
                        # 완료된 파일 정리 (10초 후)
                        wx.CallAfter(self._cleanup_completed_files)
                            
                    else:
                        wx.CallAfter(self.connection_label.SetLabel, "서버 응답 오류")
                        
                except Exception as e:
                    wx.CallAfter(self.connection_label.SetLabel, f"서버 연결 실패: {e}")
                
                # 2초마다 폴링
                time.sleep(2)
        
        self.polling_thread = threading.Thread(target=poll_upload_status, daemon=True)
        self.polling_thread.start()
    
    def _update_processing_status(self):
        """처리 중 상태 업데이트"""
        # 간단한 처리 중 메시지 표시
        if hasattr(self, 'grid') and self.grid.GetNumberRows() == 0:
            # 그리드가 비어있으면 처리 중 메시지 추가
            self.grid.AppendRows(1)
            self.grid.SetCellValue(0, 0, "파일 처리 중...")
            self.grid.SetCellValue(0, 1, "처리 중")
            self.grid.SetCellBackgroundColour(0, 1, wx.Colour(255, 165, 0))  # 주황색
            self.grid.AutoSizeColumns()
    
    def _update_current_processing_file(self, file_info):
        """현재 처리 중인 파일 정보를 그리드에 표시"""
        if not file_info:
            return
            
        file_name = file_info.get('file_name', '알 수 없는 파일')
        file_path = file_info.get('file_path', '')
        status = file_info.get('status', 'processing')
        processing_time = file_info.get('processing_time', 0)
        
        # 처리 시작 시간 포맷팅
        if processing_time:
            time_str = datetime.datetime.fromtimestamp(processing_time).strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "알 수 없음"
        
        # 기존 행에서 같은 파일 찾기
        existing_row = -1
        for row in range(self.grid.GetNumberRows()):
            if self.grid.GetCellValue(row, 1) == file_path:
                existing_row = row
                break
        
        # 새 행이 필요한 경우
        if existing_row == -1:
            self.grid.AppendRows(1)
            existing_row = self.grid.GetNumberRows() - 1
            self.grid.SetCellValue(existing_row, 0, file_name)
            self.grid.SetCellValue(existing_row, 1, file_path)
        
        # 상태별 처리
        if status == 'processing':
            self.grid.SetCellValue(existing_row, 2, "처리 중")
            self.grid.SetCellValue(existing_row, 3, time_str)
            self.grid.SetCellValue(existing_row, 4, "")  # 완료 시간은 비워둠
            self.grid.SetCellValue(existing_row, 5, "파일 처리 중...")
            
            # 처리 중 색상 설정 (연한 노란색)
            for col in range(self.grid.GetNumberCols()):
                self.grid.SetCellBackgroundColour(existing_row, col, wx.Colour(255, 255, 200))
        
        elif status == 'completed':
            completed_time = file_info.get('completed_time', 0)
            if completed_time:
                completed_time_str = datetime.datetime.fromtimestamp(completed_time).strftime("%Y-%m-%d %H:%M:%S")
            else:
                completed_time_str = "알 수 없음"
            
            print(f"[DEBUG] 완료 상태 업데이트: {file_name} -> {completed_time_str}")
            
            self.grid.SetCellValue(existing_row, 2, "업로드 완료")
            self.grid.SetCellValue(existing_row, 4, completed_time_str)
            self.grid.SetCellValue(existing_row, 5, "업로드가 성공적으로 완료되었습니다.")
            
            # 완료 색상 설정 (연한 녹색)
            for col in range(self.grid.GetNumberCols()):
                self.grid.SetCellBackgroundColour(existing_row, col, wx.Colour(200, 255, 200))
            
            # 완료된 파일 추적에 추가 (10초 후 삭제를 위해)
            self.completed_files[file_path] = time.time()
            print(f"[DEBUG] 완료된 파일 추적에 추가: {file_path}")
        
        elif status == 'failed':
            failed_time = file_info.get('failed_time', 0)
            if failed_time:
                failed_time_str = datetime.datetime.fromtimestamp(failed_time).strftime("%Y-%m-%d %H:%M:%S")
            else:
                failed_time_str = "알 수 없음"
            
            error_msg = file_info.get('error', '알 수 없는 오류')
            self.grid.SetCellValue(existing_row, 2, "업로드 실패")
            self.grid.SetCellValue(existing_row, 4, failed_time_str)
            self.grid.SetCellValue(existing_row, 5, f"오류: {error_msg}")
            
            # 실패 색상 설정 (연한 빨간색)
            for col in range(self.grid.GetNumberCols()):
                self.grid.SetCellBackgroundColour(existing_row, col, wx.Colour(255, 200, 200))
            
            # 실패한 파일도 추적에 추가 (10초 후 삭제를 위해)
            self.completed_files[file_path] = time.time()
        
        self.grid.AutoSizeColumns()
        self.grid.Refresh()
    
    def _clear_processing_files(self):
        """처리 중인 파일 정보를 그리드에서 제거"""
        # 처리 중 상태의 행들을 찾아서 제거
        rows_to_delete = []
        for row in range(self.grid.GetNumberRows()):
            status = self.grid.GetCellValue(row, 2)
            if status == "처리 중":
                rows_to_delete.append(row)
        
        # 역순으로 삭제 (인덱스 변경 방지)
        for row in reversed(rows_to_delete):
            self.grid.DeleteRows(row, 1)
        
        if rows_to_delete:
            self.grid.Refresh()
    
    def _cleanup_completed_files(self):
        """10초 이상 지난 완료된 파일들을 그리드에서 제거"""
        current_time = time.time()
        files_to_remove = []
        
        for file_path, completion_time in self.completed_files.items():
            if current_time - completion_time > 10:  # 10초 후 삭제
                files_to_remove.append(file_path)
        
        # 그리드에서 해당 행들 삭제
        for file_path in files_to_remove:
            for row in range(self.grid.GetNumberRows()):
                if self.grid.GetCellValue(row, 1) == file_path:
                    print(f"[DEBUG] 완료된 파일 삭제: {file_path}")
                    self.grid.DeleteRows(row, 1)
                    break
            del self.completed_files[file_path]
        
        if files_to_remove:
            self.grid.Refresh()
            print(f"[DEBUG] {len(files_to_remove)}개 완료된 파일이 정리되었습니다")
    
    def _get_websocket_url(self):
        """WebSocket URL 생성"""
        try:
            import os
            import json
            config_path = os.path.join(os.path.dirname(__file__), '..', 'devbot_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            port = config.get('port', 8123)
            return f"ws://localhost:{port}/ws/upload_status"
        except Exception:
            return "ws://localhost:8123/ws/upload_status"
    
    def _get_status_url(self):
        """상태 조회 URL 생성"""
        try:
            import os
            import json
            config_path = os.path.join(os.path.dirname(__file__), '..', 'devbot_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            port = config.get('port', 8123)
            return f"http://localhost:{port}/upload_queue_status"
        except Exception:
            return "http://localhost:8123/upload_queue_status"
    
    def _on_ws_open(self, ws):
        """WebSocket 연결 성공"""
        wx.CallAfter(self.connection_label.SetLabel, "서버와 실시간 연결됨")
        print("[DEBUG] WebSocket 연결 성공")
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket 연결 종료"""
        wx.CallAfter(self.connection_label.SetLabel, f"서버 연결 종료 (코드: {close_status_code})")
        print(f"[DEBUG] WebSocket 연결 종료: {close_status_code}, {close_msg}")
    
    def _on_ws_error(self, ws, error):
        """WebSocket 오류"""
        wx.CallAfter(self.connection_label.SetLabel, f"연결 오류: {error}")
        print(f"[DEBUG] WebSocket 오류: {error}")
    
    def _on_ws_message(self, ws, message):
        """WebSocket 메시지 수신"""
        try:
            print(f"[DEBUG] WebSocket 메시지 수신: {message}")
            data = json.loads(message)
            wx.CallAfter(self._handle_upload_event, data)
        except Exception as e:
            print(f"[DEBUG] 메시지 처리 오류: {e}")
            wx.CallAfter(self.connection_label.SetLabel, f"메시지 처리 오류: {e}")
    
    def _handle_upload_event(self, event_data: Dict[str, Any]):
        """업로드 이벤트 처리"""
        file_path = event_data.get('file_path', '')
        file_name = event_data.get('file_name', '')
        status = event_data.get('status', '')
        
        if not file_path:
            return
        
        # 새로운 업데이트 메서드 사용
        self._update_current_processing_file(event_data)
        
        # 업로드 완료 시 Documents 탭 새로고침 요청
        if status == 'completed':
            self._request_document_refresh()
    
    def _request_document_refresh(self):
        """Documents 탭의 문서 리스트 새로고침을 요청"""
        try:
            print("[DEBUG] Documents 탭 새로고침 시도")
            
            # 부모 윈도우 체인을 따라 올라가면서 MainFrame 찾기
            parent = self.GetParent()
            main_frame = None
            
            while parent:
                if hasattr(parent, 'doc_panel'):  # MainFrame에는 doc_panel이 있음
                    main_frame = parent
                    break
                parent = parent.GetParent()
            
            if main_frame and hasattr(main_frame, 'doc_panel'):
                print("[DEBUG] MainFrame을 찾았습니다. Documents 탭 새로고침 실행")
                # Documents 탭 새로고침
                wx.CallAfter(main_frame.doc_panel.on_refresh_documents, None)
                print("[DEBUG] Documents 탭 새로고침 요청 완료")
            else:
                print("[DEBUG] MainFrame을 찾을 수 없습니다")
                
        except Exception as e:
            print(f"[DEBUG] Documents 탭 새로고침 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _find_row_by_path(self, file_path: str) -> int:
        """파일 경로로 그리드 행 찾기"""
        for row in range(self.grid.GetNumberRows()):
            if self.grid.GetCellValue(row, 1) == file_path:
                return row
        return -1
    
    def _update_row_status(self, row_idx: int, event_data: Dict[str, Any]):
        """그리드 행 상태 업데이트"""
        status = event_data.get('status', '')
        
        # 상태 텍스트 설정
        status_text = self._get_status_text(status)
        self.grid.SetCellValue(row_idx, 2, status_text)
        
        # 시간 정보 설정
        if status == 'pending':
            added_time = event_data.get('added_time', 0)
            if added_time:
                time_str = datetime.datetime.fromtimestamp(added_time).strftime("%Y-%m-%d %H:%M:%S")
                self.grid.SetCellValue(row_idx, 3, time_str)
        elif status in ['completed', 'failed']:
            completed_time = event_data.get('completed_time', event_data.get('failed_time', 0))
            if completed_time:
                time_str = datetime.datetime.fromtimestamp(completed_time).strftime("%Y-%m-%d %H:%M:%S")
                self.grid.SetCellValue(row_idx, 4, time_str)
        
        # 메시지 설정
        if status == 'failed':
            error_msg = event_data.get('error', '알 수 없는 오류')
            self.grid.SetCellValue(row_idx, 5, error_msg)
        elif status == 'completed':
            result = event_data.get('result', {})
            message = result.get('message', '처리 완료') if isinstance(result, dict) else '처리 완료'
            self.grid.SetCellValue(row_idx, 5, message)
        
        # 행 색상 설정
        self._set_row_color(row_idx, status)
    
    def _get_status_text(self, status: str) -> str:
        """상태 코드를 한글로 변환"""
        status_map = {
            'pending': '대기 중',
            'processing': '처리 중',
            'completed': '완료',
            'failed': '실패'
        }
        return status_map.get(status, status)
    
    def _set_row_color(self, row_idx: int, status: str):
        """행 색상 설정"""
        if status == 'completed':
            color = wx.Colour(200, 255, 200)  # 연한 녹색
        elif status == 'failed':
            color = wx.Colour(255, 200, 200)  # 연한 빨간색
        elif status == 'processing':
            color = wx.Colour(255, 255, 200)  # 연한 노란색
        else:
            color = wx.Colour(255, 255, 255)  # 흰색
        
        for col in range(self.grid.GetNumberCols()):
            self.grid.SetCellBackgroundColour(row_idx, col, color)
    
    def _start_status_timer(self):
        """상태 업데이트 타이머 시작"""
        self.status_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._update_queue_status)
        self.status_timer.Start(2000)  # 2초마다 업데이트
    
    def _update_queue_status(self, event=None):
        """큐 상태 정보 업데이트"""
        def update_status():
            try:
                status_url = self._get_status_url()
                response = requests.get(status_url, timeout=3)
                
                if response.status_code == 200:
                    data = response.json()
                    queue_size = data.get('queue_size', 0)
                    remaining = data.get('remaining_capacity', 0)
                    worker_active = data.get('worker_active', False)
                    
                    status_text = f"대기 중인 파일: {queue_size}건, 남은 용량: {remaining}건"
                    if not worker_active:
                        status_text += " (워커 중단됨)"
                    
                    wx.CallAfter(self.status_label.SetLabel, status_text)
                    
                    # 용량 부족 시 색상 변경
                    if remaining <= 100:
                        wx.CallAfter(self.status_label.SetForegroundColour, wx.Colour(255, 0, 0))
                    else:
                        wx.CallAfter(self.status_label.SetForegroundColour, MODERN_COLORS['text'])
                        
                else:
                    wx.CallAfter(self.status_label.SetLabel, "서버 상태 조회 실패")
                    
            except Exception as e:
                wx.CallAfter(self.status_label.SetLabel, f"상태 조회 오류: {e}")
        
        # 별도 스레드에서 실행
        threading.Thread(target=update_status, daemon=True).start()
    
    def on_clear_completed(self, event):
        """완료된 항목 지우기"""
        rows_to_delete = []
        
        for row in range(self.grid.GetNumberRows()):
            status = self.grid.GetCellValue(row, 2)
            if status in ['완료', '실패']:
                rows_to_delete.append(row)
        
        # 역순으로 삭제 (인덱스 변경 방지)
        for row in reversed(rows_to_delete):
            self.grid.DeleteRows(row, 1)
        
        self.grid.Refresh()
    
    def Destroy(self):
        """패널 종료 시 정리"""
        self.running = False
        
        if hasattr(self, 'status_timer'):
            self.status_timer.Stop()
        
        if hasattr(self, 'polling_thread') and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=1)
        
        if self.ws:
            self.ws.close()
        
        return super().Destroy()

# 사용 예시 (탭에 추가)
if __name__ == "__main__":
    app = wx.App(False)
    frame = wx.Frame(None, title="파일 업로드 상태 테스트", size=(950, 500))
    panel = UploadStatusPanel(frame, None)
    frame.Show()
    app.MainLoop()
