import wx
import os
from typing import List, Dict

class SearchPanel(wx.Panel):
    """RAG 선택 + 검색어 입력 후 결과를 보여주는 패널"""

    def __init__(self, parent, api_client):
        super().__init__(parent)
        self.api_client = api_client

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # ------------------ 입력 영역 ------------------
        input_box = wx.StaticBox(self, label="검색 조건")
        input_sizer = wx.StaticBoxSizer(input_box, wx.VERTICAL)

        row = wx.BoxSizer(wx.HORIZONTAL)

        # RAG 선택
        rag_label = wx.StaticText(self, label="RAG")
        store_root = os.path.join(os.getcwd(), 'store')
        rag_choices = ['default']
        if os.path.isdir(store_root):
            rag_choices += [d for d in os.listdir(store_root) if os.path.isdir(os.path.join(store_root, d)) and d not in rag_choices]
        self.choice_rag = wx.Choice(self, choices=rag_choices)
        self.choice_rag.SetSelection(0)
        row.Add(rag_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        row.Add(self.choice_rag, 0, wx.RIGHT, 15)

        # 검색어
        query_label = wx.StaticText(self, label="검색어")
        self.text_query = wx.TextCtrl(self, size=(300, -1), style=wx.TE_PROCESS_ENTER)
        row.Add(query_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        row.Add(self.text_query, 1, wx.RIGHT, 15)

        # 개수
        k_label = wx.StaticText(self, label="개수")
        self.text_k = wx.TextCtrl(self, value="5", size=(50, -1))
        row.Add(k_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        row.Add(self.text_k, 0, wx.RIGHT, 15)

        # 검색 버튼
        self.btn_search = wx.Button(self, label="검색")
        row.Add(self.btn_search, 0)

        input_sizer.Add(row, 0, wx.ALL, 5)
        main_sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # ------------------ 결과 영역 ------------------
        result_box = wx.StaticBox(self, label="검색 결과")
        result_sizer = wx.StaticBoxSizer(result_box, wx.VERTICAL)

        # 결과 리스트 (Score, 파일명, 파일 경로)
        self.list_results = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 120))
        self.list_results.InsertColumn(0, "Score", width=70)
        self.list_results.InsertColumn(1, "파일명", width=200)
        self.list_results.InsertColumn(2, "파일 경로", width=350)
        result_sizer.Add(self.list_results, 0, wx.EXPAND | wx.ALL, 5)

        # 미리보기 멀티라인 텍스트 박스 (15줄)
        preview_label = wx.StaticText(self, label="미리보기")
        self.text_preview = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.VSCROLL, size=(-1, 240))
        result_sizer.Add(preview_label, 0, wx.LEFT | wx.TOP, 5)
        result_sizer.Add(self.text_preview, 1, wx.EXPAND | wx.ALL, 5)

        main_sizer.Add(result_sizer, 1, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)

        # 이벤트
        self.btn_search.Bind(wx.EVT_BUTTON, self.on_search)
        self.list_results.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_item_selected)
        self.list_results.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_item_activated)
        self.choice_rag.Bind(wx.EVT_CHOICE, self.on_rag_changed)
        self.text_query.Bind(wx.EVT_TEXT_ENTER, self.on_search)

        # 상태
        self.api_client.set_rag('default')

        # 리스트 선택 이벤트 바인딩
        self._bind_events()

    # ------------------ 이벤트 핸들러 ------------------
    def on_rag_changed(self, event):
        rag = self.choice_rag.GetStringSelection()
        self.api_client.set_rag(rag)

    def on_search(self, event):
        query = self.text_query.GetValue().strip()
        try:
            k = int(self.text_k.GetValue().strip())
        except ValueError:
            k = 5
        if not query:
            wx.MessageBox("검색어를 입력하세요", "알림")
            return

        wx.BeginBusyCursor()
        try:
            response = self.api_client.search(query, k)
            if isinstance(response, dict) and 'error' in response:
                wx.MessageBox(f"검색 실패: {response.get('details','')}\n", "오류")
                return
            self._populate_results(response)
        finally:
            wx.EndBusyCursor()

    def _populate_results(self, results: List[Dict]):
        self.list_results.DeleteAllItems()
        self.text_preview.SetValue("")
        if not results:
            return
        for idx, item in enumerate(results):
            score = f"{item.get('score',0):.3f}"
            file_path = item.get('file_path', '')
            file_name = os.path.basename(file_path)
            self.list_results.InsertItem(idx, score)
            self.list_results.SetItem(idx, 1, file_name)
            self.list_results.SetItem(idx, 2, file_path)
            # store full path in item data
            self.list_results.SetItemData(idx, idx)
            if 'file_path' not in item:
                item['file_path'] = file_path
        self.current_results = results

    def on_item_selected(self, event):
        idx = event.GetIndex()
        if idx < 0 or idx >= len(self.current_results):
            self.text_preview.SetValue("")
            return
        content = self.current_results[idx].get('content', '')
        # 15줄까지만 표시, 이후는 스크롤
        preview_lines = content.splitlines()
        preview_text = '\n'.join(preview_lines[:15])
        if len(preview_lines) > 15:
            preview_text += '\n...'
        self.text_preview.SetValue(preview_text)

    def on_item_activated(self, event):
        idx = event.GetIndex()
        if idx < 0 or idx >= len(self.current_results):
            return
        file_path = self.current_results[idx].get('file_path')
        if file_path and os.path.exists(file_path):
            try:
                os.startfile(file_path)
            except Exception as e:
                wx.MessageBox(f"파일 열기 실패: {e}", "오류")
        else:
            wx.MessageBox("파일을 찾을 수 없습니다", "오류")

    # 리스트 선택 이벤트 바인딩
    def _bind_events(self):
        self.list_results.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_item_selected)
        self.list_results.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_item_activated) 