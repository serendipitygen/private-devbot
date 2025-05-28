# 필요한 패키지 Import
import wx
import datetime
import wx.grid
import wx.html2
import os
import threading
from datetime import datetime

from ui.transparent_overlay import TransparentOverlay
from ui.config_util import load_json_config, save_json_config, get_config_file

class DocManagementPanel(wx.Panel):
    def __init__(self, parent, api_client, main_frame_ref, monitoring_daemon=None):
        wx.Panel.__init__(self, parent)
        self.api_client = api_client
        self.main_frame_ref = main_frame_ref # MainFrame 참조 저장
        self.monitoring_daemon = monitoring_daemon
        
        # config에서 page_size 불러오기
        config = load_json_config(get_config_file())
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
        
        # 문서 저장소 상태 정보와 새로고침 버튼을 포함한 패널
        status_info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.status_text = wx.StaticText(self, label="문서: 0건, DB 크기: 0MB, 벡터 스토어 경로: N/A")
        self.btn_refresh_status = wx.Button(self, label="새로고침")
        self.btn_refresh_status.Bind(wx.EVT_BUTTON, self.on_refresh_status)
        
        status_info_sizer.Add(self.status_text, 1, wx.ALIGN_CENTER_VERTICAL)
        status_info_sizer.Add(self.btn_refresh_status, 0, wx.LEFT, 10)
        
        status_sizer.Add(status_info_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # 액션 버튼 행
        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_upload_file = wx.Button(self, label="파일 등록")
        self.btn_upload_folder = wx.Button(self, label="폴더 기준 모든 파일 등록")
        self.btn_delete_selected = wx.Button(self, label="선택된 파일 삭제")
        self.btn_delete_all = wx.Button(self, label="전체 삭제")
        
        action_sizer.Add(self.btn_upload_file, 1, wx.RIGHT, 5)
        action_sizer.Add(self.btn_upload_folder, 1, wx.RIGHT, 5)
        action_sizer.Add(self.btn_delete_selected, 1, wx.RIGHT, 5)
        action_sizer.Add(self.btn_delete_all, 1)
        
        status_sizer.Add(action_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(status_sizer, 0, wx.ALL | wx.EXPAND, 10)
        
        # 필터링 섹션
        filter_box = wx.StaticBox(self, label="필터링")
        filter_sizer = wx.StaticBoxSizer(filter_box, wx.VERTICAL)
        
        filter_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # RAG 선택 필터
        rag_sizer = wx.BoxSizer(wx.VERTICAL)
        rag_label = wx.StaticText(self, label="RAG")
        # 기존 store 하위 폴더명을 읽어 RAG 목록 생성
        store_root = os.path.join(os.getcwd(), 'store')
        rag_choices = ['default']
        if os.path.isdir(store_root):
            rag_choices += [d for d in os.listdir(store_root) if os.path.isdir(os.path.join(store_root, d)) and d not in rag_choices]
        self.rag_choice = wx.Choice(self, choices=rag_choices)
        self.rag_choice.SetSelection(0)
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
        filename_sizer.Add(filename_label, 0, wx.BOTTOM, 3)
        filename_sizer.Add(self.filename_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(filename_sizer, 1, wx.RIGHT, 5)
        
        # 파일 경로 필터
        filepath_sizer = wx.BoxSizer(wx.VERTICAL)
        filepath_label = wx.StaticText(self, label="파일 경로")
        self.filepath_ctrl = wx.TextCtrl(self)
        filepath_sizer.Add(filepath_label, 0, wx.BOTTOM, 3)
        filepath_sizer.Add(self.filepath_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(filepath_sizer, 1, wx.RIGHT, 5)
        
        # 파일 유형 필터
        filetype_sizer = wx.BoxSizer(wx.VERTICAL)
        filetype_label = wx.StaticText(self, label="파일 유형")
        file_types = ['전체', '.md', '.txt', '.pdf', '.docx']
        self.filetype_ctrl = wx.Choice(self, choices=file_types)
        self.filetype_ctrl.SetSelection(0)
        filetype_sizer.Add(filetype_label, 0, wx.BOTTOM, 3)
        filetype_sizer.Add(self.filetype_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(filetype_sizer, 1, wx.RIGHT, 5)
        
        # 최소 청크 필터
        min_chunk_sizer = wx.BoxSizer(wx.VERTICAL)
        min_chunk_label = wx.StaticText(self, label="최소 청크")
        self.min_chunk_ctrl = wx.TextCtrl(self)
        min_chunk_sizer.Add(min_chunk_label, 0, wx.BOTTOM, 3)
        min_chunk_sizer.Add(self.min_chunk_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(min_chunk_sizer, 1, wx.RIGHT, 5)
        
        # 최대 청크 필터
        max_chunk_sizer = wx.BoxSizer(wx.VERTICAL)
        max_chunk_label = wx.StaticText(self, label="최대 청크")
        self.max_chunk_ctrl = wx.TextCtrl(self)
        max_chunk_sizer.Add(max_chunk_label, 0, wx.BOTTOM, 3)
        max_chunk_sizer.Add(self.max_chunk_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(max_chunk_sizer, 1, wx.RIGHT, 5)
        
        # 조회 개수 입력 박스 (제목 포함)
        page_size_sizer = wx.BoxSizer(wx.VERTICAL)
        page_size_label = wx.StaticText(self, label="조회 개수")
        page_size_sizer.Add(page_size_label, 0, wx.BOTTOM, 3)
        self.page_size_ctrl = wx.TextCtrl(self, value=str(self.page_size), size=(50, -1), style=wx.TE_PROCESS_ENTER)
        page_size_sizer.Add(self.page_size_ctrl, 0, wx.EXPAND)
        filter_controls_sizer.Add(page_size_sizer, 0, wx.RIGHT, 5)
        
        # 필터링 버튼
        self.btn_filter = wx.Button(self, label="필터링")
        filter_controls_sizer.Add(self.btn_filter, 0, wx.ALIGN_BOTTOM)
        
        filter_sizer.Add(filter_controls_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(filter_sizer, 0, wx.ALL | wx.EXPAND, 10)
        
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
        list_sizer.Add(self.list_ctrl_docs, 1, wx.EXPAND | wx.ALL, 5)
        
        # 페이징 컨트롤
        paging_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_prev_page = wx.Button(self, label="<")
        self.page_info = wx.StaticText(self, label="1 / 1 페이지 (총 0개 문서)")
        self.btn_next_page = wx.Button(self, label=">")
        
        paging_sizer.Add(self.btn_prev_page, 0, wx.RIGHT, 5)
        paging_sizer.Add(self.page_info, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        paging_sizer.Add(self.btn_next_page, 0)
        
        list_sizer.Add(paging_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        main_sizer.Add(list_sizer, 1, wx.EXPAND | wx.ALL, 10)
        
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
        
        # 문서 목록 항목 클릭 이벤트
        self.list_ctrl_docs.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_item_activated)
        
        self.SetSizer(main_sizer)
        self.Layout()

        # API 클라이언트에 초기 RAG 설정
        self.api_client.set_rag('default')

    def set_monitoring_daemon(self, monitoring_daemon):
        if monitoring_daemon is None:
            raise ValueError("monitoring_daemon이 None입니다.")
        self.monitoring_daemon = monitoring_daemon

    def fetch_documents(self, page=1, page_size=10, file_name=None, file_path=None, file_type=None, min_chunks=None, max_chunks=None):
        """API에서 문서 목록을 가져옵니다."""
        params = {
            'page': page,
            'page_size': page_size,
            'rag_name': self.api_client.get_rag()
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
            return [], 0, 0
    
    def update_document_list(self):
        """문서 목록을 가져오고 UI를 업데이트합니다."""
        # self.overlay.show("문서 목록을 가져오는 중...")  # 오버레이 제거
        
        # 필터 정보 처리
        file_name = self.filename_ctrl.GetValue().strip() if self.filename_ctrl.GetValue() else None
        file_path = self.filepath_ctrl.GetValue().strip() if self.filepath_ctrl.GetValue() else None
        
        file_type = None
        selected_type = self.filetype_ctrl.GetStringSelection()
        if selected_type and selected_type != '전체':
            file_type = selected_type
        
        min_chunks = self.min_chunk_ctrl.GetValue().strip() if self.min_chunk_ctrl.GetValue() else None
        max_chunks = self.max_chunk_ctrl.GetValue().strip() if self.max_chunk_ctrl.GetValue() else None
        
        try:
            # API에서 문서 목록 가져오기
            self.documents, self.total_documents, self.total_pages = self.fetch_documents(
                page=self.current_page,
                page_size=self.page_size,
                file_name=file_name,
                file_path=file_path,
                file_type=file_type,
                min_chunks=min_chunks,
                max_chunks=max_chunks
            )
            
            # 필터링된 문서 업데이트
            self.filtered_documents = self.documents
            
            # 페이징 정보 업데이트
            self.update_page_info()
            
            # 문서 목록 표시
            self.populate_document_list()
            
            # 문서 저장소 정보 업데이트
            self.update_status_info()
            
        finally:
            pass  # self.overlay.hide()  # 오버레이 제거
        self.update_page_info()
        self.populate_document_list()
        
    def update_status_info(self):
        """문서 저장소 상태 정보를 업데이트합니다."""
        try:
            response = self.api_client.get_store_info()
            if isinstance(response, dict):
                doc_count = response.get("document_count", self.total_documents)
                db_size = response.get("db_size_mb", 0)
                vector_store_path = response.get("vector_store_path", "N/A")
                
                self.status_text.SetLabel(f"문서: {doc_count}건, DB 크기: {db_size:.2f}MB, 벡터 스토어 경로: {vector_store_path}")
            else:
                self.status_text.SetLabel(f"문서: {self.total_documents}건, DB 크기: N/A, 벡터 스토어 경로: N/A")
        except Exception as e:
            print(f"[문서 저장소 정보] 오류 발생: {e}")
            self.status_text.SetLabel(f"문서: {self.total_documents}건, DB 크기: N/A, 벡터 스토어 경로: N/A")
    
    def update_page_info(self):
        """페이징 정보를 업데이트합니다."""
        self.page_info.SetLabel(f"{self.current_page} / {self.total_pages} 페이지 (총 {self.total_documents}개 문서)")
        
        # 페이지 버튼 활성화/비활성화
        self.btn_prev_page.Enable(self.current_page > 1)
        self.btn_next_page.Enable(self.current_page < self.total_pages)
    
    def populate_document_list(self):
        """문서 목록을 UI에 표시합니다."""
        self.list_ctrl_docs.DeleteAllItems()
        
        for idx, doc in enumerate(self.filtered_documents):
            if not isinstance(doc, dict):
                continue
                
            # 체크박스 칼럼(빈 문자열)
            index = self.list_ctrl_docs.InsertItem(idx, "")
            
            # 나머지 칼럼 데이터
            file_name = doc.get("file_name", "N/A")
            file_path = doc.get("file_path", "N/A")
            file_type = doc.get("file_type", "N/A")
            chunk_count = str(doc.get("chunk_count", 0))
            
            # 타임스탬프를 날짜로 변환
            last_updated = doc.get("last_updated", 0)
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
            self.list_ctrl_docs.SetItem(index, 6, "👁️")  # 액션 아이콘 
            
            # 데이터 저장
            self.list_ctrl_docs.SetItemData(index, idx)  # 원본 인덱스 저장
        
        # 열 너비 자동 조정
        for i in range(self.list_ctrl_docs.GetColumnCount()):
            self.list_ctrl_docs.SetColumnWidth(i, wx.LIST_AUTOSIZE_USEHEADER)
    
    def on_refresh_documents(self, event):
        """문서 목록을 새로고침합니다."""
        # self.overlay.show("문서 목록 새로고침 중...")  # 오버레이 제거
        
        if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
            self.GetTopLevelParent().SetStatusText("문서 목록을 불러오는 중입니다...")
        
        # 현재 페이지 초기화
        self.current_page = 1
        
        try:
            # 문서 목록 업데이트
            self.update_document_list()
            
            if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                self.GetTopLevelParent().SetStatusText(f"{self.total_documents}개 문서를 불러왔습니다.")
        finally:
            pass  # 오버레이 관련 코드 제거
            # if self.overlay.IsShown():
            #     self.overlay.hide()
    
    def on_prev_page(self, event):
        """이전 페이지로 이동합니다."""
        if self.current_page > 1:
            self.current_page -= 1
            self.update_document_list()
    
    def on_next_page(self, event):
        """다음 페이지로 이동합니다."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_document_list()
    
    def on_filter(self, event):
        """필터링을 적용합니다."""
        # 페이지 초기화
        self.current_page = 1
        
        # 문서 목록 업데이트
        self.update_document_list()
    
    def on_refresh_status(self, event):
        """새로고침 버튼을 눌렀을 때 문서 목록과 저장소 정보를 새로고칩니다."""
        # self.overlay.show("문서 목록과 저장소 정보 새로고침 중...")  # 오버레이 제거
        
        if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
            self.GetTopLevelParent().SetStatusText("문서 목록과 저장소 정보를 새로고침 중...")
        
        try:
            # 저장소 정보 및 문서 목록 업데이트
            self.on_refresh_documents(None)
        finally:
            pass  # 오버레이 관련 코드 제거
            # if self.overlay.IsShown():
            #     self.overlay.hide()
    
    def on_upload_file(self, event):
        """파일 업로드 다이얼로그를 열고 선택한 파일을 업로드합니다."""
        # TODO: monitoring_daemon 전달 필요
        self.monitoring_daemon.pause_monitoring()
        with wx.FileDialog(
            self, "업로드할 파일 선택", wildcard="모든 파일 (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE
        ) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            file_paths = file_dialog.GetPaths()
            if not file_paths:
                return
            # 업로드 중 오버레이 및 버튼 비활성화
            self.disable_action_buttons()
            progress = wx.ProgressDialog(
                "파일 업로드 진행", "업로드 준비 중...", maximum=len(file_paths), parent=self,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME
            )
            def upload_files_task():
                try:
                    total = len(file_paths)
                    for idx, file_path in enumerate(file_paths):
                        file_name = os.path.basename(file_path)
                        msg = f"[{idx+1}/{total}] 업로드 중: {file_name}"
                        wx.CallAfter(progress.Update, idx, msg)
                        self.upload_file_blocking(file_path)
                    wx.CallAfter(progress.Update, total, "서버 인덱스 저장 중... (최대 수십초 소요)")
                finally:
                    wx.CallAfter(progress.Destroy)
                    wx.CallAfter(self.enable_action_buttons)
                    self.monitoring_daemon.resume_monitoring(10)
            threading.Thread(target=upload_files_task, daemon=True).start()

    def upload_file_blocking(self, file_path):
        # upload_file과 동일하지만 동기적으로 동작
        file_name = os.path.basename(file_path)
        if hasattr(self.main_frame_ref, 'SetStatusText'):
            self.main_frame_ref.SetStatusText(f"파일 업로드 중: {file_name}")
        result = self.api_client.upload_file(file_path)
        self.process_upload_result(result, file_name, None)

    def disable_action_buttons(self):
        self.btn_upload_file.Disable()
        self.btn_upload_folder.Disable()
        self.btn_delete_selected.Disable()
        self.btn_delete_all.Disable()
        self.btn_refresh_status.Disable()
        self.btn_filter.Disable()
        self.btn_prev_page.Disable()
        self.btn_next_page.Disable()
        self.rag_choice.Disable()
        self.btn_add_rag.Disable()

    def enable_action_buttons(self):
        self.btn_upload_file.Enable()
        self.btn_upload_folder.Enable()
        self.btn_delete_selected.Enable()
        self.btn_delete_all.Enable()
        self.btn_refresh_status.Enable()
        self.btn_filter.Enable()
        self.btn_prev_page.Enable()
        self.btn_next_page.Enable()
        self.rag_choice.Enable()
        self.btn_add_rag.Enable()

    def on_upload_folder(self, event):
        """폴더를 선택하고 모든 파일을 업로드합니다."""
        with wx.DirDialog(
            self, "업로드할 폴더 선택", "",
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST
        ) as dir_dialog:
            
            if dir_dialog.ShowModal() == wx.ID_CANCEL:
                return  # 사용자가 취소함
                
            # 선택한 폴더 경로 가져오기
            folder_path = dir_dialog.GetPath()
            
            # 폴더 업로드
            self.upload_folder(folder_path)
    
    def on_item_activated(self, event):
        """리스트에서 항목을 더블 클릭(activate)했을 때 처리합니다."""
        idx = event.GetIndex()
        col = event.GetColumn()  # 클릭한 칼럼

        # 인덱스가 유효한지 확인
        if idx < 0 or idx >= self.list_ctrl_docs.GetItemCount():
            return

        # 클릭한 행의 원본 데이터 인덱스 가져오기
        data_idx = self.list_ctrl_docs.GetItemData(idx)
        if data_idx >= len(self.filtered_documents):
            return

        # 해당 문서 정보 추출
        doc = self.filtered_documents[data_idx]
        file_path = doc.get("file_path")
        if not file_path or not os.path.exists(file_path):
            wx.MessageBox("파일 경로를 찾을 수 없거나 파일이 존재하지 않습니다.", "오류", wx.OK | wx.ICON_ERROR)
            return

        # 파일을 기본 편집기로 엽니다 (Windows 기준)
        try:
            os.startfile(file_path)
        except Exception as e:
            wx.MessageBox(f"파일을 여는 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
        
        # 기존 액션 칼럼(6번) 클릭 시 삭제 기능은 그대로 유지
        if col == 6:  # 액션 칼럼
            # ... 기존 삭제 코드 ...
            pass
    
    def on_delete_selected(self, event):
        """선택한 문서를 삭제합니다."""
        selected_items = []
        item = self.list_ctrl_docs.GetFirstSelected()
        
        # 선택한 모든 항목 찾기
        while item != -1:
            idx = self.list_ctrl_docs.GetItemData(item)
            if idx < len(self.filtered_documents):
                selected_items.append(self.filtered_documents[idx])
            item = self.list_ctrl_docs.GetNextSelected(item)
        
        if not selected_items:
            wx.MessageBox("선택한 문서가 없습니다.", "알림", wx.OK | wx.ICON_INFORMATION)
            return
        
        # 확인 다이얼로그
        count = len(selected_items)
        if wx.MessageBox(
            f"선택한 {count}개 문서를 삭제하시겠습니까? 이 작업은 취소할 수 없습니다.",
            "확인", wx.YES_NO | wx.ICON_QUESTION
        ) != wx.YES:
            return
        
        # 오버레이 표시
        # self.overlay.show(f"선택한 {count}개 문서 삭제 중...")
        
        # 상태 표시 반영
        if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
            self.GetTopLevelParent().SetStatusText(f"선택한 {count}개 문서 삭제 중...")
        
        # 삭제할 파일 경로 목록 추출
        file_paths = [doc.get("file_path") for doc in selected_items if "file_path" in doc]
        
        if not file_paths:
            # self.overlay.hide()  # 오버레이 숨김
            wx.MessageBox("삭제할 문서의 경로를 찾을 수 없습니다.", "오류", wx.OK | wx.ICON_ERROR)
            return
        
        try:
            # 모든 파일을 한 번에 삭제하기 위해 delete_documents 호출
            result = self.api_client.delete_documents(file_paths)
            
            if isinstance(result, dict) and "error" in result:
                error_details = result.get("details", "알 수 없는 오류")
                wx.MessageBox(f"문서 삭제 실패: {error_details}", "오류", wx.OK | wx.ICON_ERROR)
                if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                    self.GetTopLevelParent().SetStatusText("문서 삭제 실패")
            else:
                if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                    self.GetTopLevelParent().SetStatusText(f"{count}개 문서 삭제 완료")
                    
        except Exception as e:
            wx.LogError(f"문서 삭제 실패: {e}")
            wx.MessageBox(f"문서 삭제 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
            if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                self.GetTopLevelParent().SetStatusText("문서 삭제 실패")
        finally:
            self.on_refresh_documents(None)
    
    def on_delete_all(self, event):
        """모든 문서를 삭제합니다."""
        # 확인 다이얼로그
        if wx.MessageBox(
            "모든 문서를 삭제하시겠습니까? 이 작업은 취소할 수 없으며 모든 문서가 영구적으로 삭제됩니다.",
            "확인", wx.YES_NO | wx.ICON_WARNING
        ) != wx.YES:
            return
        
        # 한 번 더 확인
        if wx.MessageBox(
            "정말로 모든 문서를 삭제하시겠습니까? 이 작업은 완전히 취소할 수 없습니다!",
            "최종 확인", wx.YES_NO | wx.ICON_WARNING
        ) != wx.YES:
            return
        
        # 오버레이 표시
        # self.overlay.show("모든 문서 삭제 중...")
        
        # 상태 표시 반영
        if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
            self.GetTopLevelParent().SetStatusText("모든 문서 삭제 중...")
            
        try:
            # 모든 문서 삭제 API 호출
            result = self.api_client.delete_all_documents()
            
            if isinstance(result, dict) and "error" in result:
                error_details = result.get("details", "알 수 없는 오류")
                wx.MessageBox(f"모든 문서 삭제 실패: {error_details}", "오류", wx.OK | wx.ICON_ERROR)
                if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                    self.GetTopLevelParent().SetStatusText("문서 삭제 실패")
            else:
                if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                    self.GetTopLevelParent().SetStatusText("모든 문서 삭제 완료")
                wx.MessageBox("모든 문서가 삭제되었습니다.", "성공", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.LogError(f"모든 문서 삭제 실패: {e}")
            wx.MessageBox(f"모든 문서 삭제 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
            if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                self.GetTopLevelParent().SetStatusText("문서 삭제 실패")
        finally:
            self.on_refresh_documents(None)    
    def on_page_size_changed(self, event):
        """조회 개수를 변경합니다."""
        new_page_size = self.page_size_ctrl.GetValue().strip()
        if new_page_size.isdigit():
            self.page_size = int(new_page_size)
            self._config['page_size'] = self.page_size
            save_json_config(get_config_file(), self._config)
            self.update_document_list()

    # ----------------------------- RAG 이벤트 ---------------------------
    def on_rag_changed(self, event):
        rag_name = self.rag_choice.GetStringSelection()
        self.api_client.set_rag(rag_name)
        # 문서 목록 및 상태 새로고침
        self.on_refresh_status(None)

    def on_add_rag(self, event):
        dlg = wx.TextEntryDialog(self, "새 RAG 이름 입력", "RAG 추가")
        if dlg.ShowModal() == wx.ID_OK:
            rag_name = dlg.GetValue().strip()
            if rag_name:
                # store/<rag_name> 디렉터리 생성
                if rag_name not in [self.rag_choice.GetString(i) for i in range(self.rag_choice.GetCount())]:
                    self.rag_choice.Append(rag_name)
                self.rag_choice.SetStringSelection(rag_name)
                self.on_rag_changed(None)
        dlg.Destroy()

    def process_upload_result(self, result, name, progress_dialog):
        """개별 파일 업로드 결과를 처리합니다. (대화 상자 대신 상태 표시줄 사용)"""
        # progress_dialog는 사용하지 않으므로 제거
        # progress_dialog.Update(100) # 완료
        # if progress_dialog:
        #     progress_dialog.Destroy()
        
        if isinstance(result, dict) and "error" in result:
            error_details = result.get("details", "알 수 없는 오류")
            # wx.MessageBox(f"{name} 업로드 실패: {error_details}", "오류", wx.OK | wx.ICON_ERROR)
            if hasattr(self.main_frame_ref, 'SetStatusText'):
                wx.CallAfter(self.main_frame_ref.SetStatusText, f"파일 업로드 실패: {name} - {error_details}")
        else:
            # wx.MessageBox(f"{name} 업로드 완료", "성공", wx.OK | wx.ICON_INFORMATION)
            if hasattr(self.main_frame_ref, 'SetStatusText'):
                wx.CallAfter(self.main_frame_ref.SetStatusText, f"파일 업로드 완료: {name}")
            
            # 문서 목록 새로고침 (업로드 성공 시에만)
            self.on_refresh_documents(None)

    def process_folder_upload_result(self, result, name, progress_dialog):
        """폴더 업로드 결과를 처리합니다. (개별 파일 결과와 분리)"""
        # progress_dialog는 사용하지 않으므로 제거
        # progress_dialog.Update(100) # 완료
        # if progress_dialog:
        #     progress_dialog.Destroy()

        if isinstance(result, dict):
            status = result.get("status", "error")
            message = result.get("message", "알 수 없는 오류")
            success_count = result.get("success_count", 0)
            total_count = result.get("total_count", 0)
            
            if status == "success":
                # wx.MessageBox(f"폴더 업로드 완료: {name} - {message}", "성공", wx.OK | wx.ICON_INFORMATION)
                if hasattr(self.main_frame_ref, 'SetStatusText'):
                     wx.CallAfter(self.main_frame_ref.SetStatusText, f"폴더 업로드 완료: {name} ({success_count}/{total_count} 파일 성공)")
            elif status == "partial":
                 # wx.MessageBox(f"폴더 업로드 부분 성공: {name} - {message}", "경고", wx.OK | wx.ICON_WARNING)
                 if hasattr(self.main_frame_ref, 'SetStatusText'):
                     wx.CallAfter(self.main_frame_ref.SetStatusText, f"폴더 업로드 부분 성공: {name} ({success_count}/{total_count} 파일 성공)")
            else:
                # wx.MessageBox(f"폴더 업로드 실패: {name} - {message}", "오류", wx.OK | wx.ICON_ERROR)
                if hasattr(self.main_frame_ref, 'SetStatusText'):
                     wx.CallAfter(self.main_frame_ref.SetStatusText, f"폴더 업로드 실패: {name} - {message}")
        else:
             # wx.MessageBox(f"폴더 업로드 결과 처리 오류: {name}", "오류", wx.OK | wx.ICON_ERROR)
             if hasattr(self.main_frame_ref, 'SetStatusText'):
                  wx.CallAfter(self.main_frame_ref.SetStatusText, f"폴더 업로드 결과 처리 오류: {name}")
                  
        # 폴더 업로드 완료 후 문서 목록 새로고침
        self.on_refresh_documents(None)
    
    def delete_document(self, file_path):
        """문서를 삭제합니다."""
        if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
            self.GetTopLevelParent().SetStatusText(f"문서 삭제 중: {os.path.basename(file_path)}")
        
        try:
            result = self.api_client.delete_document(file_path)
            
            if isinstance(result, dict) and "error" in result:
                error_details = result.get("details", "알 수 없는 오류")
                wx.MessageBox(f"문서 삭제 실패: {error_details}", "오류", wx.OK | wx.ICON_ERROR)
                if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                    self.GetTopLevelParent().SetStatusText("문서 삭제 실패")
            else:
                if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                    self.GetTopLevelParent().SetStatusText("문서 삭제 완료")
                    
        except Exception as e:
            wx.LogError(f"문서 삭제 실패: {e}")
            wx.MessageBox(f"문서 삭제 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
    
    def delete_all_documents(self):
        """모든 문서를 삭제합니다."""
        if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
            self.GetTopLevelParent().SetStatusText("모든 문서 삭제 중...")
        
        try:
            result = self.api_client.delete_all_documents()
            
            if isinstance(result, dict) and "error" in result:
                error_details = result.get("details", "알 수 없는 오류")
                wx.MessageBox(f"모든 문서 삭제 실패: {error_details}", "오류", wx.OK | wx.ICON_ERROR)
                if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                    self.GetTopLevelParent().SetStatusText("문서 삭제 실패")
            else:
                if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                    self.GetTopLevelParent().SetStatusText("모든 문서 삭제 완료")
                    
        except Exception as e:
            wx.LogError(f"모든 문서 삭제 실패: {e}")
            wx.MessageBox(f"모든 문서 삭제 중 오류 발생: {e}", "오류", wx.OK | wx.ICON_ERROR)
            if hasattr(self.GetTopLevelParent(), 'SetStatusText'):
                self.GetTopLevelParent().SetStatusText("문서 삭제 실패")
        finally:
            self.on_refresh_documents(None)