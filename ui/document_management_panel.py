# 필요한 패키지 Import
import wx
import datetime
import wx.grid
import wx.html2
import markdown
import os
import threading
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ui.transparent_overlay import TransparentOverlay
from ui.config_util import load_json_config, save_json_config
from ui.api_client import ApiClient
from monitoring_daemon import MonitoringDaemon
from ui.ui_setting import MODERN_COLORS
from logger_util import ui_logger
from ui.dialogs import FileViewerDialog

class DocManagementPanel(wx.Panel):
    def __init__(self, parent, api_client:ApiClient, main_frame_ref, monitoring_daemon:MonitoringDaemon=None):
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(MODERN_COLORS['notebook_background'])
        self.api_client:ApiClient = api_client
        self.main_frame_ref = main_frame_ref # MainFrame 참조 저장
        self.monitoring_daemon:MonitoringDaemon = monitoring_daemon
        
        # config에서 page_size 불러오기
        config = load_json_config()
        self.page_size = int(config.get('page_size', 50))
        self._config = config
        
        # 로딩용 오버레이 패널 초기화
        self.overlay = TransparentOverlay(self, "문서 로딩 중...")
        self.current_page = 1
        self.total_pages = 1
        self.total_documents = 0
        self.filtered_documents = []
        
        
        # 메인 사이저
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 상태 정보 섹션
        status_box = wx.StaticBox(self, label="문서 관리")
        status_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)
        status_box.SetForegroundColour(MODERN_COLORS['title_text'])
        status_box.SetFont(main_frame_ref.FONT_LIST['title_font'])
        
        
        # 문서 저장소 상태 정보와 새로고침 버튼을 포함한 패널
        status_info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # 상태 정보 텍스트와 경로 링크
        status_line_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.status_text_prefix = wx.StaticText(self, label="문서: 0건, DB 크기: 0MB, 벡터 스토어 경로: ")
        self.status_path_link = wx.StaticText(self, label="N/A")
        
        # 링크처럼 보이도록 스타일링
        link_font = self.status_path_link.GetFont()
        link_font.SetUnderlined(True)
        self.status_path_link.SetFont(link_font)
        self.status_path_link.SetForegroundColour(wx.BLUE)
        
        # 클릭 및 커서 이벤트 바인딩
        self.status_path_link.Bind(wx.EVT_LEFT_DOWN, self.on_path_click)
        self.status_path_link.Bind(wx.EVT_ENTER_WINDOW, self.on_enter_link)
        self.status_path_link.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave_link)
        self.vector_store_path = "N/A" # 경로 저장용 변수
        
        status_line_sizer.Add(self.status_text_prefix, 0, wx.ALIGN_CENTER_VERTICAL)
        status_line_sizer.Add(self.status_path_link, 0, wx.ALIGN_CENTER_VERTICAL)

        self.btn_refresh_status = wx.Button(self, label="새로고침(F5)")
        self.btn_refresh_status.Bind(wx.EVT_BUTTON, self.on_refresh_status)
        self.btn_refresh_status.SetBackgroundColour(MODERN_COLORS['primary'])
        
        status_info_sizer.Add(status_line_sizer, 1, wx.ALIGN_CENTER_VERTICAL)
        status_info_sizer.Add(self.btn_refresh_status, 0, wx.LEFT, 10)
        
        status_sizer.Add(status_info_sizer, 0, wx.ALL | wx.EXPAND, 5)
    
        
        # 액션 버튼 행
        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_upload_file = wx.Button(self, label="파일 등록")
        self.btn_upload_folder = wx.Button(self, label="폴더 기준 모든 파일 등록")
        self.btn_delete_selected = wx.Button(self, label="선택된 파일 삭제")
        self.btn_delete_all = wx.Button(self, label="전체 삭제")

        self.btn_upload_file.SetBackgroundColour(MODERN_COLORS['button_background'])
        self.btn_upload_folder.SetBackgroundColour(MODERN_COLORS['button_background'])
        self.btn_delete_selected.SetBackgroundColour(MODERN_COLORS['delete_button_background'])
        self.btn_delete_all.SetBackgroundColour(MODERN_COLORS['delete_button_background'])
        
        action_sizer.Add(self.btn_upload_file, 1, wx.RIGHT, 5)
        action_sizer.Add(self.btn_upload_folder, 1, wx.RIGHT, 5)
        action_sizer.Add(self.btn_delete_selected, 1, wx.RIGHT, 5)
        action_sizer.Add(self.btn_delete_all, 1)
        
        status_sizer.Add(action_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(status_sizer, 0, wx.EXPAND)
        
        # 필터링 섹션
        filter_box = wx.StaticBox(self, label="필터링")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.VERTICAL)
        filter_box.SetForegroundColour(MODERN_COLORS['title_text'])
        filter_box.SetFont(self.main_frame_ref.FONT_LIST['title_font'])
        
        filter_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # RAG 선택 필터
        rag_sizer = wx.BoxSizer(wx.VERTICAL)
        rag_label = wx.StaticText(self, label="문서 저장소")
        # 기존 store 하위 폴더명을 읽어 RAG 목록 생성
        store_root = os.path.join(os.getcwd(), 'store')
        rag_choices = ['default']
        if os.path.isdir(store_root):
            rag_choices += [d for d in os.listdir(store_root) if os.path.isdir(os.path.join(store_root, d)) and d not in rag_choices]
        self.rag_choice = wx.Choice(self, choices=rag_choices)
        self.rag_choice.SetSelection(0)
        self.rag_choice.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        rag_sizer.Add(rag_label, 0, wx.BOTTOM, 3)
        rag_choice_line = wx.BoxSizer(wx.HORIZONTAL)
        rag_choice_line.Add(self.rag_choice, 1, wx.RIGHT, 3)
        self.btn_add_rag = wx.Button(self, label="추가")
        rag_choice_line.Add(self.btn_add_rag, 0)
        rag_sizer.Add(rag_choice_line, 0, wx.EXPAND)
        filter_controls_sizer.Add(rag_sizer, 1, wx.RIGHT, 5)
        
        # 파일명 필터
        filename_sizer = wx.BoxSizer(wx.VERTICAL)
        filename_label = wx.StaticText(self, label="파일명")
        self.filename_ctrl = wx.TextCtrl(self)
        self.filename_ctrl.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        filename_sizer.Add(filename_label, 0, wx.BOTTOM, 3)
        filename_sizer.Add(self.filename_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(filename_sizer, 1, wx.RIGHT, 5)
        
        # 파일 경로 필터
        filepath_sizer = wx.BoxSizer(wx.VERTICAL)
        filepath_label = wx.StaticText(self, label="파일 경로")
        self.filepath_ctrl = wx.TextCtrl(self)
        self.filepath_ctrl.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        filepath_sizer.Add(filepath_label, 0, wx.BOTTOM, 3)
        filepath_sizer.Add(self.filepath_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(filepath_sizer, 1, wx.RIGHT, 5)
        
        # 파일 유형 필터
        filetype_sizer = wx.BoxSizer(wx.VERTICAL)
        filetype_label = wx.StaticText(self, label="파일 유형")
        file_types = ['전체', '.md', '.txt', '.pdf', '.docx']
        self.filetype_ctrl = wx.Choice(self, choices=file_types)
        self.filetype_ctrl.SetSelection(0)
        self.filetype_ctrl.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        filetype_sizer.Add(filetype_label, 0, wx.BOTTOM, 3)
        filetype_sizer.Add(self.filetype_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(filetype_sizer, 1, wx.RIGHT, 5)
        
        # 최소 청크 필터
        min_chunk_sizer = wx.BoxSizer(wx.VERTICAL)
        min_chunk_label = wx.StaticText(self, label="최소 청크")
        self.min_chunk_ctrl = wx.TextCtrl(self)
        self.min_chunk_ctrl.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        min_chunk_sizer.Add(min_chunk_label, 0, wx.BOTTOM, 3)
        min_chunk_sizer.Add(self.min_chunk_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(min_chunk_sizer, 1, wx.RIGHT, 5)
        
        # 최대 청크 필터
        max_chunk_sizer = wx.BoxSizer(wx.VERTICAL)
        max_chunk_label = wx.StaticText(self, label="최대 청크")
        self.max_chunk_ctrl = wx.TextCtrl(self)
        self.max_chunk_ctrl.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        max_chunk_sizer.Add(max_chunk_label, 0, wx.BOTTOM, 3)
        max_chunk_sizer.Add(self.max_chunk_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(max_chunk_sizer, 1, wx.RIGHT, 5)
        
        # 조회 개수 입력 박스 (제목 포함)
        page_size_sizer = wx.BoxSizer(wx.VERTICAL)
        page_size_label = wx.StaticText(self, label="조회 개수")
        page_size_sizer.Add(page_size_label, 0, wx.BOTTOM, 3)
        self.page_size_ctrl = wx.TextCtrl(self, value=str(self.page_size), size=(50, -1), style=wx.TE_PROCESS_ENTER)
        self.page_size_ctrl.SetBackgroundColour(MODERN_COLORS['textbox_background'])
        page_size_sizer.Add(self.page_size_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(page_size_sizer, 0, wx.RIGHT, 5)
        
        # 필터링 버튼
        self.btn_filter = wx.Button(self, label="필터링")
        filter_controls_sizer.Add(self.btn_filter, 0, wx.ALIGN_BOTTOM)
        self.btn_filter.SetBackgroundColour(MODERN_COLORS['button_background'])
        
        filter_sizer.Add(filter_controls_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(filter_sizer, 0, wx.EXPAND | wx.TOP, 10)
        
        # 문서 목록 테이블
        list_sizer = wx.BoxSizer(wx.VERTICAL)
    
        # SINGLE_SEL을 사용하지 않으면 기본적으로 다중 선택이 활성화됨
        self.list_ctrl_docs = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.list_ctrl_docs.InsertColumn(0, "", width=30) # 체크박스용 열
        self.list_ctrl_docs.InsertColumn(1, "파일명", width=200)
        self.list_ctrl_docs.InsertColumn(2, "경로", width=300)
        self.list_ctrl_docs.InsertColumn(3, "유형", width=50)
        self.list_ctrl_docs.InsertColumn(4, "청크수", width=60)
        self.list_ctrl_docs.InsertColumn(5, "등록일", width=150)
        self.list_ctrl_docs.InsertColumn(6, "액션", width=50)

        # 폰트 크기 조정
        list_font = self.list_ctrl_docs.GetFont()
        list_font.SetPointSize(list_font.GetPointSize() - 1)
        self.list_ctrl_docs.SetFont(list_font)

        # 행 높이 조정을 위한 이미지 리스트 설정 (높이 22px)
        img_list = wx.ImageList(1, 22)
        bmp = wx.Bitmap(1, 22, 32) # 32비트 깊이로 알파 채널 활성화
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0))) # 완전 투명
        dc.Clear()
        del dc
        img_list.Add(bmp)
        self.list_ctrl_docs.AssignImageList(img_list, wx.IMAGE_LIST_SMALL)
        list_sizer.Add(self.list_ctrl_docs, 1, wx.EXPAND | wx.ALL, 5)
        self.list_ctrl_docs.SetBackgroundColour(MODERN_COLORS['list_background'])
        
        # 페이징 컨트롤
        paging_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_prev_page = wx.Button(self, label="이전 페이지")
        self.page_info = wx.StaticText(self, label="1 / 1 페이지 (총 0개)")
        self.btn_next_page = wx.Button(self, label="다음 페이지")

        self.btn_prev_page.SetBackgroundColour(MODERN_COLORS['navigation_background'])
        self.btn_next_page.SetBackgroundColour(MODERN_COLORS['navigation_background'])
        
        paging_sizer.Add(self.btn_prev_page, 0, wx.RIGHT, 5)
        paging_sizer.Add(self.page_info, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        paging_sizer.Add(self.btn_next_page, 0)
        
        list_sizer.Add(paging_sizer, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 15)
        main_sizer.Add(list_sizer, 1, wx.EXPAND | wx.TOP, 10)
        
        # 이벤트 바인딩
        self.btn_upload_file.Bind(wx.EVT_BUTTON, self.on_upload_file)
        self.btn_upload_folder.Bind(wx.EVT_BUTTON, self.on_upload_folder)
        self.btn_delete_selected.Bind(wx.EVT_BUTTON, self.on_delete_selected)
        self.btn_delete_all.Bind(wx.EVT_BUTTON, self.on_delete_all)
        self.btn_filter.Bind(wx.EVT_BUTTON, self.on_filter)
        self.btn_prev_page.Bind(wx.EVT_BUTTON, self.on_prev_page)
        self.btn_next_page.Bind(wx.EVT_BUTTON, self.on_next_page)
        self.page_size_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_page_size_changed)
        self.page_size_ctrl.Bind(wx.EVT_KILL_FOCUS, self.on_page_size_changed)
        self.rag_choice.Bind(wx.EVT_CHOICE, self.on_rag_changed)
        self.btn_add_rag.Bind(wx.EVT_BUTTON, self.on_add_rag)

        self.btn_add_rag.SetBackgroundColour(MODERN_COLORS['button_background'])
        
        # 문서 목록 항목 클릭 이벤트
        self.list_ctrl_docs.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_item_activated)

        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F5, self.btn_refresh_status.GetId())
        ])
        self.SetAcceleratorTable(accel_tbl)
        
        self.SetSizer(main_sizer)
        self.Layout()

    def on_item_activated(self, event):
        """문서 목록에서 항목을 더블클릭했을 때 호출됩니다."""
        item_index = event.GetIndex()
        doc_index = self.list_ctrl_docs.GetItemData(item_index)
        doc = self.filtered_documents[doc_index]
        
        doc_id = doc.get('doc_id')
        if not doc_id:
            wx.MessageBox("문서 ID를 찾을 수 없습니다.", "오류", wx.OK | wx.ICON_ERROR)
            return

        try:
            content_response = self.api_client.get_document_content(doc_id)
            if 'error' in content_response:
                wx.MessageBox(f"문서 내용을 가져오는 데 실패했습니다: {content_response.get('details')}", "오류", wx.OK | wx.ICON_ERROR)
                return
            
            content = content_response.get('content', '')
            file_name = doc.get('file_name', '파일 내용')
            file_type = doc.get('file_type', '')

            # 파일 뷰어 대화상자 표시
            dlg = FileViewerDialog(self, title=file_name, content=content, file_type=file_type)
            dlg.ShowModal()
            dlg.Destroy()

        except Exception as e:
            ui_logger.exception("파일 내용 보기 중 오류 발생")
            wx.MessageBox(f"파일 내용을 표시하는 중 오류가 발생했습니다: {e}", "오류", wx.OK | wx.ICON_ERROR)


        # API 클라이언트에 초기 RAG 설정
        self.api_client.set_rag_name('default')

    def set_monitoring_daemon(self, monitoring_daemon):
        if monitoring_daemon is None:
            raise ValueError("monitoring_daemon이 None입니다.")
        self.monitoring_daemon = monitoring_daemon

    def fetch_documents(self, page=1, page_size=10, file_name=None, file_path=None, file_type=None, min_chunks=None, max_chunks=None):
        """API에서 문서 목록을 가져옵니다."""
        params = {
            'page': page,
            'page_size': page_size,
            'rag_name': self.api_client.get_rag_name()
        }
        
        # 필터 파라미터 추가
        if file_name:
            params['file_name'] = file_name
        if file_path:
            params['file_path'] = file_path
        if file_type and file_type != '전체':
            params['file_type'] = file_type
        if min_chunks and min_chunks.isdigit():
            params['min_chunks'] = int(min_chunks)
        if max_chunks and max_chunks.isdigit():
            params['max_chunks'] = int(max_chunks)
            
        try:
            response = self.api_client.get_documents(params)
            
            if isinstance(response, dict) and "error" in response:
                wx.MessageBox(f"문서 목록을 가져오는 중 오류 발생: {response.get('details', '알 수 없는 오류')}", "오류", wx.OK | wx.ICON_ERROR)
                return [], 0, 0
                
            if isinstance(response, dict):
                documents = response.get("documents", [])
                total = response.get("total", len(documents))
                total_pages = response.get("total_pages", 1)
                return documents, total, total_pages
            
            return [], 0, 0
            
        except Exception as e:
            wx.LogError(f"문서 목록을 가져오는 중 오류 발생: {e}")
            wx.MessageBox(f"문서 목록을 가져오는 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
            ui_logger.exception("문서 목록 가져오기 실패")
            return [], 0, 0
    
    def _get_filter_params(self):
        """UI에서 현재 필터 설정을 가져옵니다."""
        file_name = self.filename_ctrl.GetValue().strip() if self.filename_ctrl.GetValue() else None
        file_path = self.filepath_ctrl.GetValue().strip() if self.filepath_ctrl.GetValue() else None
        file_type = None
        selected_type = self.filetype_ctrl.GetStringSelection()
        if selected_type and selected_type != '전체':
            file_type = selected_type
        min_chunks = self.min_chunk_ctrl.GetValue().strip() if self.min_chunk_ctrl.GetValue() else None
        max_chunks = self.max_chunk_ctrl.GetValue().strip() if self.max_chunk_ctrl.GetValue() else None
        return {
            'file_name': file_name,
            'file_path': file_path,
            'file_type': file_type,
            'min_chunks': min_chunks,
            'max_chunks': max_chunks,
        }

    def update_document_list(self, filter_params, ui_update=True):
        """문서 목록을 가져오고 필요한 경우 UI를 업데이트합니다."""
        # API에서 문서 목록 가져오기
        self.documents, self.total_documents, self.total_pages = self.fetch_documents(
            page=self.current_page,
            page_size=self.page_size,
            **filter_params
        )
        
        # 필터링된 문서 업데이트
        self.filtered_documents = self.documents
        
        if ui_update:
            # 페이징 정보 업데이트
            self.update_page_info()
            # 문서 목록 표시
            self.populate_document_list()
            # 문서 저장소 정보 업데이트
            self.update_status_info()
        
    def update_status_info(self):
        """문서 저장소 상태 정보를 업데이트합니다."""
        try:
            response = self.api_client.get_store_info()
            if isinstance(response, dict):
                doc_count = response.get("document_count", self.total_documents)
                db_size = response.get("db_size_mb", 0)
                self.vector_store_path = response.get("vector_store_path", "N/A")
                
                prefix = f"문서: {doc_count}건, DB 크기: {db_size:.2f}MB, 벡터 스토어 경로: "
                self.status_text_prefix.SetLabel(prefix)
                self.status_path_link.SetLabel(self.vector_store_path)
                self.status_path_link.GetParent().Layout()
            else:
                self.vector_store_path = "N/A"
                self.status_text_prefix.SetLabel(f"문서: {self.total_documents}건, DB 크기: N/A, 벡터 스토어 경로: ")
                self.status_path_link.SetLabel(self.vector_store_path)
                self.status_path_link.GetParent().Layout()
        except Exception as e:
            ui_logger.exception(f"[문서 저장소 정보] 오류 발생: {e}")
            self.vector_store_path = "N/A"
            self.status_text_prefix.SetLabel(f"문서: {self.total_documents}건, DB 크기: N/A, 벡터 스토어 경로: ")
            self.status_path_link.SetLabel(self.vector_store_path)
            self.status_path_link.GetParent().Layout()
    
    def update_page_info(self):
        """페이징 정보를 업데이트합니다."""
        self.page_info.SetLabel(f"{self.current_page} / {self.total_pages} 페이지 (총 {self.total_documents}개)")
        
        # 페이지 버튼 활성화/비활성화
        self.btn_prev_page.Enable(self.current_page > 1)
        self.btn_next_page.Enable(self.current_page < self.total_pages)
    
    def populate_document_list(self):
        """문서 목록을 UI에 표시합니다."""
        self.list_ctrl_docs.DeleteAllItems()
        
        for idx, doc in enumerate(self.filtered_documents):
            if not isinstance(doc, dict):
                continue
                
            index = self.list_ctrl_docs.InsertItem(idx, "")
            file_name = doc.get("file_name", "N/A")
            file_path = doc.get("file_path", "N/A")
            file_type = doc.get("file_type", "N/A")
            chunk_count = str(doc.get("chunk_count", 0))
            last_updated = doc.get("last_updated", 0)

            # SetItemData를 사용하여 문서의 인덱스 저장
            self.list_ctrl_docs.SetItemData(index, idx)

            if last_updated:
                date_obj = datetime.fromtimestamp(last_updated)
                last_updated_str = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_updated_str = "N/A"
            
            self.list_ctrl_docs.SetItem(index, 1, file_name)
            self.list_ctrl_docs.SetItem(index, 2, file_path)
            self.list_ctrl_docs.SetItem(index, 3, file_type)
            self.list_ctrl_docs.SetItem(index, 4, chunk_count)
            self.list_ctrl_docs.SetItem(index, 5, last_updated_str)
            self.list_ctrl_docs.SetItem(index, 6, "👁️")
            self.list_ctrl_docs.SetItemData(index, idx)
        
        for i in range(self.list_ctrl_docs.GetColumnCount()):
            self.list_ctrl_docs.SetColumnWidth(i, wx.LIST_AUTOSIZE_USEHEADER)

    def on_path_click(self, event):
        """벡터 스토어 경로를 클릭했을 때 파일 탐색기를 엽니다."""
        path = self.vector_store_path
        if os.path.isdir(path):
            try:
                # Windows에서 파일 탐색기 열기
                os.startfile(path)
            except Exception as e:
                wx.LogError(f"폴더를 열 수 없습니다: {path}\n오류: {e}")
        else:
            wx.LogWarning(f"경로가 존재하지 않거나 폴더가 아닙니다: {path}")
        event.Skip()

    def on_enter_link(self, event):
        """마우스가 링크 위로 올라왔을 때 커서 변경"""
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        event.Skip()

    def on_leave_link(self, event):
        """마우스가 링크를 벗어났을 때 커서 복원"""
        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
        event.Skip()

    def on_refresh_documents(self, event):
        """문서 목록을 새로고침합니다."""
        if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
            self.GetTopLevelParent().SetStatusText("문서 목록을 불러오는 중입니다...")
        self.current_page = 1
        try:
            filter_params = self._get_filter_params()
            self.update_document_list(filter_params, ui_update=True)
            if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                self.GetTopLevelParent().SetStatusText(f"{self.total_documents}개 문서를 불러왔습니다.")
        except Exception as e:
            ui_logger.exception("문서 목록 새로고침 중 오류 발생")
            wx.MessageBox(f"문서 목록 새로고침 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)

    def on_prev_page(self, event):
        """이전 페이지로 이동합니다."""
        if self.current_page > 1:
            self.current_page -= 1
            filter_params = self._get_filter_params()
            self.update_document_list(filter_params, ui_update=True)

    def on_next_page(self, event):
        """다음 페이지로 이동합니다."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            filter_params = self._get_filter_params()
            self.update_document_list(filter_params, ui_update=True)

    def on_filter(self, event):
        """필터링을 적용합니다."""
        self.current_page = 1
        filter_params = self._get_filter_params()
        self.update_document_list(filter_params, ui_update=True)

    def on_refresh_status(self, event):
        """새로고침 버튼을 눌렀을 때 문서 목록과 저장소 정보를 새로고칩니다."""
        if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
            self.GetTopLevelParent().SetStatusText("문서 목록과 저장소 정보를 새로고침 중...")
        try:
            self.on_refresh_documents(None)
        except Exception as e:
            ui_logger.exception("상태 정보 새로고침 중 오류 발생")

    def on_upload_file(self, event):
        """파일 업로드 다이얼로그를 열고 선택한 파일을 업로드합니다."""
        with wx.FileDialog(
            self, "업로드할 파일 선택", wildcard="모든 파일 (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE
        ) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            file_paths = file_dialog.GetPaths()
            if file_paths:
                self._start_upload_job(file_paths, "파일 업로드")

    def on_upload_folder(self, event):
        """폴더를 선택하고 그 안의 모든 파일을 업로드합니다."""
        with wx.DirDialog(self, "업로드할 폴더 선택", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dir_dialog:
            if dir_dialog.ShowModal() == wx.ID_CANCEL:
                return
            folder_path = dir_dialog.GetPath()
            file_paths = []
            for root, _, files in os.walk(folder_path):
                for filename in files:
                    if not filename.startswith('.') and not filename.startswith('~'):
                        file_paths.append(os.path.join(root, filename))
            if file_paths:
                self._start_upload_job(file_paths, "폴더 업로드")
            else:
                wx.MessageBox("폴더에 업로드할 파일이 없습니다.", "정보", wx.OK | wx.ICON_INFORMATION)

    def _start_upload_job(self, file_paths, title):
        """업로드와 새로고침 과정을 순차적으로 실행하고 UI를 제어합니다."""
        self.monitoring_daemon.pause_monitoring()
        self.disable_action_buttons()

        progress_dialog = wx.ProgressDialog(
            f"{title} 진행", "업로드 준비 중...", maximum=len(file_paths) + 1, # +1 for refresh step
            parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME | wx.PD_CAN_ABORT
        )

        # 결과를 저장할 컨테이너
        result_container = {'success': 0, 'fail': 0, 'cancelled': False, 'error': None}

        # 1. 파일 업로드 스레드 실행 및 대기
        upload_thread = threading.Thread(target=self._upload_worker, args=(file_paths, progress_dialog, result_container))
        upload_thread.daemon = True
        upload_thread.start()
        
        # 업로드 스레드가 완료될 때까지 대기 (UI 이벤트 루프는 계속 동작)
        while upload_thread.is_alive():
            wx.GetApp().Yield()
            time.sleep(0.1)

        if result_container['cancelled']:
            progress_dialog.Destroy()
            self.enable_action_buttons()
            self.monitoring_daemon.resume_monitoring()
            msg = f"업로드가 사용자에 의해 취소되었습니다.\n성공: {result_container['success']}건, 실패: {result_container['fail']}건"
            wx.MessageBox(msg, "업로드 취소", wx.OK | wx.ICON_INFORMATION)
            return

        # 2. 문서 목록 새로고침
        try:
            progress_dialog.Pulse("서버 처리 및 목록 새로고침 중...")
            filter_params = self._get_filter_params()
            self.update_document_list(filter_params, ui_update=True) # UI 업데이트까지 완료
        except Exception as e:
            ui_logger.exception("문서 목록 새로고침 중 오류 발생")
            result_container['error'] = e
        finally:
            progress_dialog.Destroy()

        # 3. 최종 결과 표시
        self.enable_action_buttons()
        self.monitoring_daemon.resume_monitoring()

        if result_container['error']:
            wx.MessageBox(f"문서 목록 새로고침 중 오류 발생: {result_container['error']}", "오류", wx.OK | wx.ICON_ERROR)

        msg = f"업로드 완료: 성공 {result_container['success']}건, 실패: {result_container['fail']}건"
        wx.MessageBox(msg, "업로드 완료", wx.OK | wx.ICON_INFORMATION)

    def _upload_worker(self, file_paths, progress_dialog, result_container):
        """파일 업로드만 수행하는 워커 스레드."""
        success_count, fail_count = 0, 0
        total = len(file_paths)

        for i, file_path in enumerate(file_paths):
            message = f"[{i + 1}/{total}] 업로드 중: {os.path.basename(file_path)}"
            if not self._update_progress_from_thread(progress_dialog, i + 1, message):
                result_container['cancelled'] = True
                break
            
            try:
                result = self.api_client.upload_file_path(file_path)
                if result and result.get('status') == 'success':
                    success_count += 1
                    self.monitoring_daemon.append_monitoring_file(file_path=file_path, rag_name=self.api_client.get_rag_name())
                else:
                    fail_count += 1
                    ui_logger.error(f"파일 업로드 실패: {os.path.basename(file_path)}, 오류: {result.get('message', '알 수 없는 오류')}")
            except Exception as e:
                fail_count += 1
                ui_logger.exception(f"파일 업로드 중 예외 발생: {file_path}")

        result_container['success'] = success_count
        result_container['fail'] = fail_count

    def _update_progress_from_thread(self, progress_dialog, current_value, message):
        """
        백그라운드 스레드에서 메인 스레드의 progress_dialog를 안전하게 업데이트하고
        사용자의 취소 여부를 반환합니다.
        """
        keep_going = [True]
        event = threading.Event()

        def update_ui():
            try:
                keep_going[0], _ = progress_dialog.Update(current_value, message)
            except wx.wxAssertionError:
                keep_going[0] = False
            finally:
                event.set()

        wx.CallAfter(update_ui)
        event.wait()
        return keep_going[0]

    def disable_action_buttons(self):
        """모든 주요 액션 버튼을 비활성화합니다."""
        for btn in [self.btn_upload_file, self.btn_upload_folder, self.btn_delete_selected, 
                    self.btn_delete_all, self.btn_refresh_status, self.btn_filter, 
                    self.btn_prev_page, self.btn_next_page, self.btn_add_rag]:
            btn.Disable()
        self.rag_choice.Disable()

    def enable_action_buttons(self):
        """모든 주요 액션 버튼을 활성화합니다."""
        for btn in [self.btn_upload_file, self.btn_upload_folder, self.btn_delete_selected, 
                    self.btn_delete_all, self.btn_refresh_status, self.btn_filter, 
                    self.btn_prev_page, self.btn_next_page, self.btn_add_rag]:
            btn.Enable()
        self.rag_choice.Enable()
        self.update_page_info() # 페이지 버튼 상태는 페이징 정보에 따라 다시 결정

    def on_item_activated(self, event):
        """리스트에서 항목을 더블 클릭했을 때 파일을 엽니다."""
        idx = event.GetIndex()
        if idx < 0: return
        data_idx = self.list_ctrl_docs.GetItemData(idx)
        if data_idx >= len(self.filtered_documents): return
        doc = self.filtered_documents[data_idx]
        file_path = doc.get("file_path")
        if file_path and os.path.exists(file_path):
            try:
                os.startfile(file_path)
            except Exception as e:
                wx.MessageBox(f"파일을 여는 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
                ui_logger.exception("파일 열기 오류")
        else:
            wx.MessageBox("파일을 찾을 수 없습니다.", "오류", wx.OK | wx.ICON_ERROR)

    def on_delete_selected(self, event):
        """선택한 문서를 삭제합니다."""
        selected_items_indices = []
        item = self.list_ctrl_docs.GetFirstSelected()
        while item != -1:
            selected_items_indices.append(item)
            item = self.list_ctrl_docs.GetNextSelected(item)

        if not selected_items_indices:
            wx.MessageBox("선택한 문서가 없습니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            return

        if wx.MessageBox(f"선택한 {len(selected_items_indices)}개 문서를 삭제하시겠습니까?", "확인", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return

        file_paths_to_delete = []
        for item_idx in selected_items_indices:
            data_idx = self.list_ctrl_docs.GetItemData(item_idx)
            if data_idx < len(self.filtered_documents):
                file_paths_to_delete.append(self.filtered_documents[data_idx].get("file_path"))

        if not file_paths_to_delete:
            return

        try:
            self.api_client.delete_documents(file_paths_to_delete)
        except Exception as e:
            wx.MessageBox(f"문서 삭제 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
            ui_logger.exception("선택 문서 삭제 오류")
        finally:
            self.on_refresh_documents(None)

    def on_delete_all(self, event):
        """모든 문서를 삭제합니다."""
        if wx.MessageBox("모든 문서를 삭제하시겠습니까? 이 작업은 취소할 수 없습니다.", "최종 확인", wx.YES_NO | wx.ICON_WARNING) != wx.YES:
            return
        try:
            self.api_client.delete_all_documents()
        except Exception as e:
            wx.MessageBox(f"모든 문서 삭제 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
            ui_logger.exception("전체 문서 삭제 오류")
        finally:
            self.on_refresh_documents(None)

    def on_page_size_changed(self, event):
        """조회 개수를 변경합니다."""
        new_page_size = self.page_size_ctrl.GetValue().strip()
        if new_page_size.isdigit() and int(new_page_size) > 0:
            self.page_size = int(new_page_size)
            self._config['page_size'] = self.page_size
            save_json_config(self._config)
            self.update_document_list()
        else:
            self.page_size_ctrl.SetValue(str(self.page_size))

    def on_rag_changed(self, event):
        rag_name = self.rag_choice.GetStringSelection()
        self.api_client.set_rag_name(rag_name)
        self.on_refresh_status(None)

    def on_add_rag(self, event):
        with wx.TextEntryDialog(self, "새 RAG 이름 입력", "RAG 추가") as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                rag_name = dlg.GetValue().strip()
                if rag_name:
                    if rag_name not in [self.rag_choice.GetString(i) for i in range(self.rag_choice.GetCount())]:
                        self.rag_choice.Append(rag_name)
                    self.rag_choice.SetStringSelection(rag_name)
                    self.on_rag_changed(None)