# PRIVATE DEVBOT (RAG) Backend

## 개요
- Public DevBOT과 연계하여 사용자 또는 조직 단위의 Private RAG 서비스를 제공하는 Backend
- Fast API 기반의 문서 업로드, 삭제, 검색 등의 API를 제공함

## 개발 환경
- vs code
- python 3.11.11
- no GPU

## 설치 방법
`pip install requirements.txt`
또는
```bash
# torch 설치 (CPU 버전)
pip install torch torchvision torchaudio

# 기본 필요 패키지
pip install fastapi uvicorn python-multipart pydantic langchain langchain-community langchain-huggingface PyPDF2 docx2txt pandas openpyxl python-pptx faiss-cpu sentence-transformers transformers==4.47.1 fastapi watchdog requests chardet kiwipiepy easyocr opencv-python

## exe 파일 생성에 필요한 패키지
pip install nuitka ordered-set websockets httptools watchfiles
```

### 임베딩 모델 다운로드
#### huggingface-remote(ocean) 관련 환경 변수 설정 필요 
windows powershell 환경 
```posh
$env:HF_HUB_ETAG_TIMEOUT=1500000
$env:HF_ENDPOINT="https://bart.sec.samsung.net/artifactory/api/huggingfaceml/huggingface-remote"
```
linux shell 환경
```bash
export HF_HUB_ETAG_TIMEOUT=1500000
export HF_ENDPOINT="https://bart.sec.samsung.net/artifactory/api/huggingfaceml/huggingface-remote"
```
#### 임베딩 모델 다운로드가 안될 경우
207 Storage 서버에 올려둔 파일을 다운로드 받아야 함.
168.219.24.207 서버에 aibgo 계정으로 로그인 후 , 
/aib/home/aibgo/private_devbot_data/embedding_model.egg  파일을 다운로드 받아서
백엔드 프로젝트 폴더에 embedding_model이라는 폴더로 압축 해제 하면 됨

## 실행 방법
- command prompt : `uvicorn main:app --host 0.0.0.0 --port 8123 --reload --log-level debug`
- 또는 vs code에는 F5로 디버그 실행

## API DOC
- http://localhost:8123/docs  (기본 실행 시, 8123 포트로 실행됨)

## 파일 설명
- main.py : FastAPI 서버 구동
- vector_store.py : FAISS 벡터 저장소로 FAISS DB와 임베딩 관리
- faiss_vector_store.py : FAISS 벡터 저장소 구현
- document_splitter.py : 문서를 토큰 단위로 분할
- config.py : 설정 파일 (임베딩 모델 설정 정보가 있는데, 추후 실행 시 파라메터로 분리 예정)
- utils.py : 유틸리티 함수 모음
- search_utils.py : 검색 관련 유틸리티 함수 모음 (키워드 추출 등)
- logger_util.py : 로그 객체 생성 함수(현재 main.py, vector_store.py에만 적용되어 있음 -> 확장 예정)
- file_path_converter.py : 파일 경로 변환 유틸리티 (현재 사용 안함)
- file_monitor.py : 파일 변경 감시 (추후, 파일 업로드 방식이 아닌 개인 PC에 위치 기반 모니터링 시 사용 예정)
- build.bat : nuitka로 exe 파일 생성용 (윈도우즈만 지원 -> 보완 중)
- private_rag_ui : Streamlit을 이용한 관리자 UI (최초 테스트 프로토타입용이었고 현재 사용 안함)

# API 호출 시 localhost:8123으로만 접속 가능

uvicorn main:app --port 8123 --reload --log-level debug

# API 호출 시 외부에서도 접속 가능 (0.0.0.0)

uvicorn main:app --host 0.0.0.0 --port 8123 --reload --log-level debug
uvicorn main:app --port 8123 --log-level debug
관리자 UI 실행

cd private_rag_ui
streamlit run app.py
streamlit run .\private_rag_ui\app.py
챗봇 서비스 실행 (별도 터미널)

## 테스트 용 프론트엔드 (사용 안함)
`pip install streamlit requests kss kiwipiepy streamlit_js_eval`

## 기타 참고 사항
- 프론트엔드는 Flutter로 개발되어 있고 프로젝트 이름은 `private_devbot_admin`
- 진행 중 또는 진행해야 하는 Task는 `DEV_DIARY.md` 파일 참고
