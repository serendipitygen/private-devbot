## TODO

[] LangChainDeprecationWarning 경고 처리
[] 백엔드-프론트엔드 통합해서 하나로 둘다 실행
[] 문서 목록은 파일, 폴더의 Tree 형태로 표시
[] 문서 목록에 파일, 폴더 경로를 추가로 표시
[] 문서 목록에 글꼴 작게 해서 많은 정보 표시
[] 파일, 폴더 단위로 삭제 지원
[] 청크, Temperature, overlap 크기 조절 가능
[완료] 벡터 저장소 초기화 오류 수정
[완료] POST 방식 작동 안함
[완료] 동일 문서 첨부 시, 기존 벡터 저장소에서 해당 문서 청크 삭제 후에 다시 벡터화 후 입력
[] 한국어 형태소 기반에 키워드 추출 로직
[] 서버 실행 포트를 사용자가 지정할 수 있게 변경
[] 서버 로딩 전 클라이언트 실행 문제
[] 최신 패키지 로딩 문제
[] 랭체인 기반으로 변경
[] 다운로드 받은 임베딩 모델을 사용하도록 수정

---

## 2025.02.02
### 동일 문서 첨부 시 청크가 추가되는 문제 해결

---

## 2025.01.27

### 벡터 저장소 초기화 오류 수정

원인1: 빈 리스트(texts=[])로 FAISS 인덱스를 생성하려 시도 → IndexError 발생.
해결: 초기화 시 FAISS 인덱스 생성 로직을 제거하고, 첫 파일 업로드 시 자연스럽게 인덱스가 생성되도록 수정

원인2: 초기화 후 file_monitor.py가 기존 폴더를 계속 모니터링 → 파일 재업로드 발생.

### 서버 로딩 전 클라이언트 실행 문제

서버 연결 오류: HTTPConnectionPool(host='localhost', port=8123): Max retries exceeded with url: /documents (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x000001676EFDE910>: Failed to establish a new connection: [WinError 10061] 대상 컴퓨터에서 연결을 거부했으므로 연결하지 못했습니다'))

### 최신 패키지 로딩 문제
WARNING:  StatReload detected changes in 'main.py'. Reloading...
D:\dev\work\private-devbot\main.py:50: LangChainDeprecationWarning: The class `HuggingFaceEmbeddings` was deprecated in LangChain 0.2.2 and will be removed in 1.0. An updated version of the class exists in the :class:`~langchain-huggingface package and should be used instead. To use it run `pip install -U :class:`~langchain-huggingface` and import as `from :class:`~langchain_huggingface import HuggingFaceEmbeddings``.
  embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
