import streamlit as st
import requests
import re
import time
from typing import List
import hashlib

# CSS 스타일 수정
HIGHLIGHT_CSS = """
<style>
.highlight {
    background-color: yellow;
    font-weight: bold;
}
</style>
"""
st.markdown(HIGHLIGHT_CSS, unsafe_allow_html=True)

def extract_keywords(query: str) -> List[str]:
    return [word for word in re.findall(r'\b\w{2,}\b', query.lower())]

def highlight_keywords(text: str, keywords: List[str]) -> str:
    for keyword in keywords:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        text = pattern.sub(r'<span class="highlight">\g<0></span>', text)
    return text

def compute_file_hash(file_content: bytes) -> str:
    return hashlib.md5(file_content).hexdigest()

st.title("Private RAG 관리자 패널")

# 검색 섹션 수정
with st.form("search_form"):
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input("검색 질문 입력", placeholder="예: 파이썬에서 리스트 정렬 방법")
    with col2:
        k = st.number_input("검색 수", min_value=1, max_value=10, value=5)
    submitted = st.form_submit_button("문서 검색")

if submitted:
    if not query:
        st.warning("검색어를 입력해주세요!")
    else:
        with st.spinner("관련 문서를 검색 중입니다..."):
            try:
                search_data = {
                    "query": query,
                    "k": k
                }
                
                response = requests.post(
                    "http://localhost:8123/search",
                    json=search_data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    results = response.json().get("results", [])
                    if results:
                        st.session_state.results = results
                        st.session_state.keywords = extract_keywords(query)
                    else:
                        st.info("검색 결과가 없습니다.")
                else:
                    st.error(f"검색 실패: {response.text}")
            except Exception as e:
                st.error(f"서버 연결 오류: {str(e)}")

# 검색 결과 표시 부분 수정
if 'results' in st.session_state and st.session_state.results:
    st.subheader(f"📚 검색 결과 ({len(st.session_state.results)}건)")
    
    for i, doc in enumerate(st.session_state.results, 1):
        score_percentage = doc['score'] * 100
        with st.expander(f"문서 {i} (유사도: {score_percentage:.1f}%)", expanded=True):
            try:
                highlighted = highlight_keywords(doc["content"], st.session_state.keywords)
                st.markdown(f"""
                <div style='border-left: 3px solid #4CAF50; padding: 0.5em 1em; margin: 1em 0;'>
                    {highlighted}
                </div>
                """, unsafe_allow_html=True)
                st.caption(f"출처: {doc['metadata']['source']}")
                
            except KeyError as e:
                st.error(f"문서 형식 오류: {str(e)}")

# 문서 목록 로드 함수
def load_document_list():
    try:
        response = requests.get("http://localhost:8123/documents", timeout=5)
        if response.status_code == 200:
            return response.json().get("documents", [])
        else:
            st.error(f"문서 목록 로드 실패: {response.text}")
            return []
    except Exception as e:
        st.error(f"서버 연결 오류: {str(e)}")
        return []

# 앱 시작시 문서 목록 로드
if 'documents' not in st.session_state:
    st.session_state.documents = load_document_list()

# 문서 관리 섹션
with st.expander("📂 문서 관리", expanded=True):
    # 초기화 버튼과 확인 로직 재구성
    if st.button("🗑 전체 초기화 실행", 
                help="모든 문서와 벡터 저장소를 초기화합니다",
                type="secondary",
                key="reset_btn"):
        st.session_state.show_reset_confirmation = True
    
    # 확인 대화상자 표시
    if st.session_state.get('show_reset_confirmation', False):
        st.warning("⚠️ 정말로 모든 문서와 벡터 저장소를 초기화하시겠습니까?")
        col1, col2 = st.columns([1,2])
        with col1:
            if st.button("✅ 예", key="confirm_reset"):
                try:
                    response = requests.post(
                        "http://localhost:8123/reset",
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )
                    if response.status_code == 200:
                        st.session_state.documents = []
                        st.success("초기화 성공")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"초기화 실패: {response.text}")
                except Exception as e:
                    st.error(f"초기화 중 오류 발생: {str(e)}")
                finally:
                    st.session_state.show_reset_confirmation = False
    
        with col2:
            if st.button("❌ 아니오", key="cancel_reset"):
                st.session_state.show_reset_confirmation = False
    
    st.divider()

    # 파일 업로드 섹션
    st.subheader("파일 업로드")
    uploaded_file = st.file_uploader("파일 선택", type=[
        "pdf", "docx", "pptx", 
        "txt", "md", 
        "c", "cpp", "h", "hpp", "py", "cs"
    ])
    
    if uploaded_file:
        file_content = uploaded_file.getvalue()
        file_hash = compute_file_hash(file_content)
        files = {"file": (uploaded_file.name, file_content)}
        try:
            response = requests.post(
                "http://localhost:8123/upload",
                files=files,
                data={"file_hash": file_hash}
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("duplicate"):
                    st.warning(f"문서 '{uploaded_file.name}'는 이미 존재합니다. 중복 인덱싱을 건너뛰었습니다.")
                else:
                    st.success(f"문서 업로드 완료: {uploaded_file.name}")
                # 문서 목록 갱신
                st.session_state.documents = load_document_list()
            else:
                st.error(f"업로드 실패: {response.text}")
        except Exception as e:
            st.error(f"업로드 오류: {str(e)}")

    # 문서 목록 표시
    if st.session_state.documents:
        st.divider()
        st.subheader("📑 등록된 문서 목록")
        for doc in st.session_state.documents:
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**📄 {doc['filename']}** ({doc['file_type'].upper()})")
                with col2:
                    st.text(f"청크 수: {doc['chunk_count']}")
                with col3:
                    st.text(f"수정: {time.strftime('%Y-%m-%d %H:%M', time.localtime(doc['last_updated']))}")
                st.markdown("---")

# 시스템 상태 모니터링
with st.expander("📊 시스템 상태"):
    try:
        response = requests.get("http://localhost:8123/status")
        if response.status_code == 200:
            status = response.json()
            col1, col2 = st.columns(2)
            with col1:
                st.metric("저장 문서 수", f"{status['document_count']}건")
            with col2:
                st.metric("벡터 저장소 크기", f"{status['index_size_mb']}MB")
            st.caption(f"인덱스 경로: {status['index_path']}")
    except Exception as e:
        st.error(f"상태 확인 실패: {str(e)}")