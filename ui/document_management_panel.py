# 필요한 패키지 Import
import wx
import datetime
import wx.grid
import wx.html2
import markdown
import os
import shutil
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
from ui.dialogs import FileViewerDialog, RagNameDialog
from ui.api_client_for_public_devbot import registerOrUpdateToPublicDevbot

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
        # 백업 기본 경로 (선택되지 않았을 수도 있음)
        if 'backup_base_path' not in config:
            config['backup_base_path'] = ''
        self.backup_base_path = config.get('backup_base_path', '')
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
        self.status_text_prefix = wx.StaticText(self, label="문서: 0건, 저장소 크기: 0MB, 문서 저장소 경로: ")
        self.status_path_link = wx.StaticText(self, label="N/A")
        
        # 링크처럼 보이도록 스타일링
        link_font = self.status_path_link.GetFont()
        link_font.SetUnderlined(True)
        self.status_path_link.SetFont(link_font)
        self.status_path_link.SetForegroundColour(MODERN_COLORS['hover'])
        
        # 클릭 및 커서 이벤트 바인딩
        self.status_path_link.Bind(wx.EVT_LEFT_DOWN, self.on_path_click)
        self.status_path_link.Bind(wx.EVT_ENTER_WINDOW, self.on_enter_link)
        self.status_path_link.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave_link)
        self.vector_store_path = "N/A" # 경로 저장용 변수
        
        status_line_sizer.Add(self.status_text_prefix, 0, wx.ALIGN_CENTER_VERTICAL)
        status_line_sizer.Add(self.status_path_link, 0, wx.ALIGN_CENTER_VERTICAL)

        self.btn_refresh_status = wx.Button(self, label="새로고침(F5)")
        # --- Backup & Restore Buttons ---
        self.btn_backup_store = wx.Button(self, label="백업")
        self.btn_restore_store = wx.Button(self, label="복원")
        for _btn in [self.btn_backup_store, self.btn_restore_store]:
            _btn.SetBackgroundColour(MODERN_COLORS['button_background'])
        self.btn_backup_store.Bind(wx.EVT_BUTTON, self.on_backup_store)
        self.btn_restore_store.Bind(wx.EVT_BUTTON, self.on_restore_store)
        self.btn_refresh_status.Bind(wx.EVT_BUTTON, self.on_refresh_status)
        self.btn_refresh_status.SetBackgroundColour(MODERN_COLORS['primary'])
        
        status_info_sizer.Add(status_line_sizer, 1, wx.ALIGN_CENTER_VERTICAL)
        status_info_sizer.Add(self.btn_refresh_status, 0, wx.LEFT, 10)
        status_info_sizer.Add(self.btn_backup_store, 0, wx.LEFT, 10)
        status_info_sizer.Add(self.btn_restore_store, 0, wx.LEFT, 5)
        
        status_sizer.Add(status_info_sizer, 0, wx.ALL | wx.EXPAND, 5)
    
        
        # 액션 버튼 행
        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_upload_file = wx.Button(self, label="파일 등록")
        self.btn_upload_folder = wx.Button(self, label="폴더 기준 모든 파일 등록")
        self.btn_delete_selected = wx.Button(self, label="선택된 파일 삭제(Del)")
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
        filter_box = wx.StaticBox(self, label="검색 조건")
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
        self.btn_add_rag = wx.Button(self, label="그룹 추가")
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
        self.btn_filter = wx.Button(self, label="조회")
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
        # --- 버튼 툴팁 설정 ---
        self.btn_refresh_status.SetToolTip("문서 목록과 저장소 정보를 새로고침합니다 (F5)")
        self.btn_backup_store.SetToolTip("현재 벡터 스토어를 선택한 경로에 백업합니다")
        self.btn_restore_store.SetToolTip("선택한 백업으로 벡터 스토어를 복원합니다")
        self.btn_upload_file.SetToolTip("하나 이상의 파일을 선택해 문서 저장소에 등록합니다")
        self.btn_upload_folder.SetToolTip("폴더를 선택해 하위 파일을 모두 등록합니다")
        self.btn_delete_selected.SetToolTip("선택된 문서를 삭제합니다 (Del)")
        self.btn_delete_all.SetToolTip("모든 문서를 영구 삭제합니다")
        self.btn_filter.SetToolTip("현재 필터 조건으로 문서를 조회합니다")
        self.btn_prev_page.SetToolTip("이전 페이지로 이동합니다")
        self.btn_next_page.SetToolTip("다음 페이지로 이동합니다")
        self.btn_add_rag.SetToolTip("새 문서 저장소 그룹(RAG)을 추가합니다")
        
        # 문서 목록 항목 클릭 이벤트
        self.list_ctrl_docs.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_item_activated)

        # 단축키 설정: F5(새로고침), Delete(선택 삭제)
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F5, self.btn_refresh_status.GetId()),
            (wx.ACCEL_NORMAL, wx.WXK_DELETE, self.btn_delete_selected.GetId())
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
                # 서버에서 큐 상태 확인
                try:
                    remaining = self._get_queue_remaining_capacity()
                    if len(file_paths) > remaining:
                        wx.MessageBox(
                            f"업로드 가능한 파일 수를 초과했습니다.\n현재 업로드 가능한 파일 수: {remaining}건",
                            "업로드 제한",
                            wx.OK | wx.ICON_WARNING
                        )
                        return
                except Exception as e:
                    wx.MessageBox(f"서버 상태 확인 실패: {e}", "오류", wx.OK | wx.ICON_ERROR)
                    return
                    
                self._start_upload_job(file_paths, "파일 업로드")

    def on_upload_folder(self, event):
        """폴더를 선택하고 그 안의 모든 파일을 업로드합니다."""
        try:
            # 로딩 표시
            self.overlay.show("폴더 선택 중...")
            wx.Yield()  # UI 업데이트를 위해 이벤트 루프 처리

            with wx.DirDialog(self, "업로드할 폴더 선택", 
                            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dir_dialog:
                if dir_dialog.ShowModal() == wx.ID_CANCEL:
                    self.overlay.hide()
                    return
                    
                folder_path = dir_dialog.GetPath()
                self.overlay.show("파일 수집 중...")
                
                # 백그라운드에서 파일 수집
                threading.Thread(
                    target=self._collect_and_upload_files,
                    args=(folder_path,),
                    daemon=True
                ).start()
                
        except Exception as e:
            self.overlay.hide()
            wx.MessageBox(f"폴더 선택 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
            ui_logger.exception("폴더 업로드 오류")

    def _collect_and_upload_files(self, folder_path):
        """백그라운드에서 파일을 수집하고 업로드합니다."""
        try:
            file_paths = []
            for root, _dirs, files in os.walk(folder_path):
                for f in files:
                    file_paths.append(os.path.join(root, f))
                    
            if not file_paths:
                wx.CallAfter(wx.MessageBox, "선택한 폴더에 업로드할 파일이 없습니다.", 
                            "알림", wx.OK | wx.ICON_INFORMATION)
                return
                    
            try:
                remaining = self._get_queue_remaining_capacity()
                if len(file_paths) > remaining:
                    wx.CallAfter(wx.MessageBox,
                                f"업로드 가능한 파일 수를 초과했습니다.\n현재 업로드 가능한 파일 수: {remaining}건",
                                "업로드 제한",
                                wx.OK | wx.ICON_WARNING)
                    return
            except Exception as e:
                wx.CallAfter(wx.MessageBox, f"서버 상태 확인 실패: {e}", "오류", wx.OK | wx.ICON_ERROR)
                return
                    
            wx.CallAfter(self._start_upload_job, file_paths, "폴더 업로드")
            
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"파일 수집 중 오류 발생: {e}", 
                        "오류", wx.OK | wx.ICON_ERROR)
            ui_logger.exception("파일 수집 오류")
        finally:
            wx.CallAfter(self.overlay.hide)

    def _start_upload_job(self, file_paths, job_desc: str = "파일 업로드"):
        """선택한(또는 수집한) 파일을 백그라운드 스레드에서 업로드한다."""
        if not file_paths:
            wx.MessageBox("업로드할 파일이 없습니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            return

        # UI 잠금
        self.disable_action_buttons()

        def _task():
            try:
                result = self._upload_files_to_queue(file_paths)
                success_cnt = result.get('added_count', 0)
                failed_files = result.get('failed_files', [])
                failed_cnt = len(failed_files)
                
                message = f"파일 업로드 요청 완료: {success_cnt}건 대기열 추가"
                if failed_cnt > 0:
                    message += f", {failed_cnt}건 실패"
                
                # 안내 문구 표시
                info_message = f"{message}\n\n선택된 파일들은 백그라운드로 파일을 추가하며, 파일 업로드시마다 메시지로 알려드립니다."
                
                wx.CallAfter(wx.MessageBox, info_message, "작업 완료", wx.OK | wx.ICON_INFORMATION)
                
            except Exception as e:
                ui_logger.exception(f"[DocManagementPanel] 파일 업로드 실패: {e}")
                wx.CallAfter(wx.MessageBox, f"파일 업로드 실패: {e}", "오류", wx.OK | wx.ICON_ERROR)
            finally:
                # UI 및 상태 갱신
                wx.CallAfter(self.on_refresh_status, None)
                wx.CallAfter(self.enable_action_buttons)

        threading.Thread(target=_task, daemon=True).start()

    def _get_queue_remaining_capacity(self) -> int:
        """서버에서 업로드 큐의 남은 용량을 조회합니다."""
        try:
            result = self.api_client._make_request('GET', 'upload_queue_status')
            
            if isinstance(result, dict) and 'error' in result:
                raise Exception(f"서버 오류: {result.get('details', result.get('error'))}")
            
            if result is None:
                ui_logger.warning("서버에서 빈 응답을 받았습니다.")
                return 0
                
            if isinstance(result, dict):
                return result.get('remaining_capacity', 0)
            else:
                ui_logger.warning(f"예상치 못한 응답 형식: {type(result)}")
                return 0
                
        except Exception as e:
            ui_logger.error(f"큐 상태 조회 실패: {e}")
            raise

    def _upload_files_to_queue(self, file_paths: list) -> dict:
        """여러 파일을 서버 업로드 큐에 추가합니다."""
        try:
            result = self.api_client._make_request(
                'POST',
                'upload_file_paths',
                json_data=file_paths
            )
            
            if isinstance(result, dict) and 'error' in result:
                raise Exception(f"서버 오류: {result.get('details', result.get('error'))}")
                
            return result if result else {"success": False, "message": "서버 응답 없음"}
            
        except Exception as e:
            ui_logger.error(f"파일 업로드 큐 추가 실패: {e}")
            raise

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
        """새 문서 저장소 그룹(RAG)을 추가합니다."""
        existing_names = [self.rag_choice.GetString(i) for i in range(self.rag_choice.GetCount())]
        dlg = RagNameDialog(self, existing_names)
        if dlg.ShowModal() == wx.ID_OK:
            rag_name = dlg.get_name()
            # RagNameDialog가 유효성 및 중복 검증을 보장
            self.rag_choice.Append(rag_name)
            self.rag_choice.SetStringSelection(rag_name)
            self.on_rag_changed(None)

            # Public DevBot 레지스트리에 신규 RAG 등록
            try:
                registerOrUpdateToPublicDevbot(rag_name)
            except Exception as e:
                ui_logger.exception(f"[DocManagementPanel] RAG '{rag_name}' 등록 실패: {e}")
        dlg.Destroy()

    def on_backup_store(self, event):
        """벡터 스토어 폴더를 선택한 경로에 백업합니다."""
        store_dir = os.path.join(os.getcwd(), 'store')
        if not os.path.isdir(store_dir):
            wx.MessageBox("벡터 스토어 폴더를 찾을 수 없습니다.", "오류", wx.OK | wx.ICON_ERROR)
            return

        # 기본 백업 경로: 이전에 사용한 경로 또는 내 문서
        default_path = self.backup_base_path if self.backup_base_path else os.path.expanduser("~\\Documents")

        with wx.DirDialog(self, "백업 위치 선택", defaultPath=default_path,
                          style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dir_dlg:
            if dir_dlg.ShowModal() == wx.ID_CANCEL:
                return
            dest_base = dir_dlg.GetPath()

        # 현재 store 폴더를 백업 위치로 지정한 경우 방지
        if os.path.abspath(dest_base) == os.path.abspath(store_dir):
            wx.MessageBox("현재 스토어 폴더와 동일한 위치는 백업 대상이 될 수 없습니다.", "오류", wx.OK | wx.ICON_ERROR)
            return

        backup_root = os.path.join(dest_base, 'private_devbot_backup')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_dir = os.path.join(backup_root, timestamp)

        def _task():
            try:
                os.makedirs(backup_root, exist_ok=True)
                shutil.copytree(store_dir, dest_dir)
                wx.CallAfter(wx.MessageBox, f"백업이 완료되었습니다:\n{dest_dir}", "백업 완료", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                ui_logger.exception("벡터 스토어 백업 실패")
                wx.CallAfter(wx.MessageBox, f"백업 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
            finally:
                # 백업 경로 저장 및 UI 복구
                self.backup_base_path = dest_base
                self._config['backup_base_path'] = dest_base
                save_json_config(self._config)
                wx.CallAfter(self.enable_action_buttons)

        self.disable_action_buttons()
        threading.Thread(target=_task, daemon=True).start()

    def on_restore_store(self, event):
        """선택한 백업으로 벡터 스토어를 복원합니다."""
        # 백업 기본 경로 확인
        base_path = self.backup_base_path
        if not base_path or not os.path.isdir(base_path):
            with wx.DirDialog(self, "백업 위치 선택", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dir_dlg:
                if dir_dlg.ShowModal() == wx.ID_CANCEL:
                    return
                base_path = dir_dlg.GetPath()
                self.backup_base_path = base_path
                self._config['backup_base_path'] = base_path
                save_json_config(self._config)

        backup_root = os.path.join(base_path, 'private_devbot_backup')
        if not os.path.isdir(backup_root):
            wx.MessageBox("백업 폴더를 찾을 수 없습니다.", "오류", wx.OK | wx.ICON_ERROR)
            return

        subfolders = sorted([d for d in os.listdir(backup_root) if os.path.isdir(os.path.join(backup_root, d))])
        if not subfolders:
            wx.MessageBox("사용 가능한 백업이 없습니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            return

        with wx.SingleChoiceDialog(self, "복원할 백업을 선택하세요", "백업 선택", subfolders, style=wx.CHOICEDLG_STYLE) as choice_dlg:
            if choice_dlg.ShowModal() == wx.ID_CANCEL:
                return
            selected = choice_dlg.GetStringSelection()

        restore_src = os.path.join(backup_root, selected)
        store_dir = os.path.join(os.getcwd(), 'store')

        if wx.MessageBox(f"선택된 백업으로 복원하시겠습니까?\n{restore_src}", "최종 확인", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return

        def _task():
            try:
                # 모니터링 중지
                if self.monitoring_daemon:
                    self.monitoring_daemon.pause_monitoring()

                # 서버 중지 (메인 스레드에서 실행)
                if hasattr(self.main_frame_ref, 'admin_panel'):
                    wx.CallAfter(self.main_frame_ref.admin_panel.on_stop_server, None)
                    # 서버가 완전히 중지될 때까지 대기 (최대 60초)
                    for _ in range(60):
                        if not self.main_frame_ref.admin_panel.is_datastore_running:
                            break
                        time.sleep(1)

                # 기존 store 폴더 삭제
                if os.path.isdir(store_dir):
                    shutil.rmtree(store_dir)

                # 백업 폴더 복사
                shutil.copytree(restore_src, store_dir)

                # 서버 재시작 (메인 스레드에서 실행)
                if hasattr(self.main_frame_ref, 'admin_panel'):
                    wx.CallAfter(self.main_frame_ref.admin_panel.on_start_server, None)
                    # 서버가 완전히 시작될 때까지 대기 (최대 60초)
                    for _ in range(60):
                        if self.main_frame_ref.admin_panel.is_datastore_running:
                            break
                        time.sleep(1)

                # 모니터링 재개
                if self.monitoring_daemon:
                    self.monitoring_daemon.resume_monitoring()

                wx.CallAfter(wx.MessageBox, "복원이 완료되었습니다.", "복원 완료", wx.OK | wx.ICON_INFORMATION)
                wx.CallAfter(self.on_refresh_status, None)
            except Exception as e:
                ui_logger.exception("벡터 스토어 복원 실패")
                wx.CallAfter(wx.MessageBox, f"복원 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
            finally:
                wx.CallAfter(self.enable_action_buttons)

        # UI 비활성화 후 백그라운드에서 복원 실행
        self.disable_action_buttons()
        threading.Thread(target=_task, daemon=True).start()

    def disable_action_buttons(self):
        """모든 주요 액션 버튼을 비활성화합니다."""
        for btn in [self.btn_upload_file, self.btn_upload_folder, self.btn_delete_selected, 
                    self.btn_delete_all, self.btn_refresh_status, self.btn_filter, 
                    self.btn_prev_page, self.btn_next_page, self.btn_add_rag,
                    self.btn_backup_store, self.btn_restore_store]:
            btn.Disable()
        self.rag_choice.Disable()

    def enable_action_buttons(self):
        """모든 주요 액션 버튼을 활성화합니다."""
        for btn in [self.btn_upload_file, self.btn_upload_folder, self.btn_delete_selected, 
                    self.btn_delete_all, self.btn_refresh_status, self.btn_filter, 
                    self.btn_prev_page, self.btn_next_page, self.btn_add_rag,
                    self.btn_backup_store, self.btn_restore_store]:
            btn.Enable()
        self.rag_choice.Enable()
        self.update_page_info() # 페이지 버튼 상태는 페이징 정보에 따라 다시 결정