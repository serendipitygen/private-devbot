## TODO

[] UI에서 다중 파일 등록 처리
[] 재인덱싱 기능 제공 : 청크, overlap 크기 조절 가능
[] 파일 등록 시, 키값을 클라이언트 IP + 파일 경로로 해야 함.
[] Fast API startup/shutdown 이벤트 처리 방식 변경경
[] 모듈화를 위한 리팩토링
[] 랭체인 기반으로 변경
[] 벡터 저장소 저장 로직 개선 (성능)
[] FLUX UI에 로그파일 처리
[] 문서 목록에 파일명, 폴더명 검색 기능 추가
[] 문서 목록은 파일, 폴더의 Tree 형태로 표시
[] 문서 목록에 글꼴 작게 해서 많은 정보 표시
[] 서버 실행 시, 서버 실행 포트를 사용자가 지정할 수 있게 변경
[] 서버 로딩 전 클라이언트 실행 문제
[] 새로운 임베딩 모델 업데이트 기능
[] 국제화 처리
[] DevBOT API를 통해 Private RAG 등록 기능
[] DevBOT API를 통해 등록된 Private RAG 이름 목록 조회
[] exe 파일 생성
[] 멀티턴 지원
[] 개인 PC 독립 실행형 개발(파일 업로드 없이 파일 위치만 모니터링)
[] 키워드 검색 지원 여부
[] API 토큰 사용
[] 릴리즈 노트 적용
[완료] LangChainDeprecationWarning 경고 처리
[완료] 벡터 저장소 초기화 오류 수정
[완료] POST 방식 작동 안함
[완료] 동일 문서 첨부 시, 기존 벡터 저장소에서 해당 문서 청크 삭제 후에 다시 벡터화 후 입력
[완료] 한국어 형태소 기반에 키워드 추출 로직
[완료] 다운로드 받은 임베딩 모델을 사용하도록 수정
[완료] 벡터 저장소 메타 정보에 File Path 추가
[완료] 로그 파일 처리
[완료] filename, file_path를 분리해서 사용
[완료] /search 시 파일 경로 등의 출처도 포함해서 리턴
[완료] 문서 목록을 보여줄 때, 정렬 기준 적용
[완료] 문서 목록에 파일, 폴더 경로를 추가로 표시
[완료] 파일, 폴더 단위로 삭제 지원
[완료] Streamlit 기반 테스트 UI에서 Flutter 기반 UI로 전환
[완료] 유사도 점수 계산 방법 개선
[완료] 폴더 단위 등록

---

## 2025.02.09
### NUITKA로 EXE 파일 생성
python -m nuitka --follow-imports --include-package=fastapi --include-package=uvicorn --include-package=langchain --include-package=faiss --include-package=numpy --include-package=cv2 --include-package=easyocr --include-package=sentence_transformers --include-package=pydantic --include-package=pptx --include-package=PIL --include-package=torch --include-package=transformers --include-package=tokenizers --include-package=tqdm --include-package=yaml --include-package=packaging --include-package=filelock --include-package=regex --include-package=requests --include-package=charset_normalizer --include-package=certifi --include-package=idna --include-package=urllib3 --include-package=typing_extensions --include-package=starlette --include-package=anyio --include-package=sniffio --include-package=click --include-package=h11 --include-package=websockets --include-package=httptools --include-package=watchfiles --include-package=python-multipart --enable-plugin=numpy --enable-plugin=torch --standalone --onefile --windows-icon-from-ico=app_icon.ico --output-dir=build main.py


websockets

---

## 2025.02.08
### 이미지 OCR 적용
- 문서의 의미 없는 내용도 다 추출하여 유사도 검색에 안 좋은 영향을 끼침
- 
### 폴더 선택 후 하위 모든 폴더와 파일을 등록

### kss 제거 및 kiepiepy 기반 구조로 변경 완료

$uri = "http://localhost:8123/documents"
$headers = @{"Content-Type" = "application/json"}

### 파일 경로를 원래 문자열로 사용하고 백슬래시 이스케이프

$filePath = "D:/docs/google_drive_serencode_bak/노트/obsidian/임시 기록.md"

# 요청 본문 생성 (백슬래시 이스케이프)

$body = '{"file_paths": ["' + $filePath + '"]}'

# DELETE 요청 보내기

Invoke-WebRequest -Uri $uri -Method DELETE -Headers $headers -Body $body

## 2025.02.07

### vector_store, faiss_vector_store 분리 완료

### kiwi 사용 태그 종류

{"NNG", "NNP", "NNB", "NP", "VV", "VA", "MAG", "SL", "SH", "SN"}

체언(N)
NNG: 일반 명사
NNP: 고유 명사
NNB: 의존 명사
NR: 수사
NP: 대명사
용언(V)
VV: 동사
VA: 형용사
VX: 보조 용언
VCP: 긍정 지시사(이다)
VCN: 부정 지시사(아니다)
수식언
MM: 관형사
MAG: 일반 부사
MAJ: 접속 부사
독립언
IC: 감탄사
관계언(J)
JKS: 주격 조사
JKC: 보격 조사
JKG: 관형격 조사
JKO: 목적격 조사
JKB: 부사격 조사
JKV: 호격 조사
JKQ: 인용격 조사
JX: 보조사
JC: 접속 조사
의존형태
EP: 선어말 어미
EF: 종결 어미
EC: 연결 어미
ETN: 명사형 전성 어미
ETM: 관형형 전성 어미
기호
SF: 마침표, 물음표, 느낌표
SP: 쉼표, 가운뎃점, 콜론, 빗금
SS: 따옴표, 괄호, 줄표
SE: 줄임표
SO: 붙임표(물결, 숨김, 빠짐)
SW: 기타 기호
분석 불능
SL: 외국어
SH: 한자
SN: 숫자
기타
XPN: 체언 접두사
XSN: 명사 파생 접미사
XSV: 동사 파생 접미사
XSA: 형용사 파생 접미사
XR: 어근
특수
W_EMOJI: 이모지

## 2025.02.05

### startup/shutdown

```
@app.on_event("startup")
async def startup_event():
    # 서버 시작 시 필요한 초기화 작업
    pass

@app.on_event("shutdown")
async def shutdown_event():
    # 서버 종료 시 벡터 저장소 안전하게 저장
```

### 재인덱싱

### 등록 문서가 없을 때 검색 시 에러처리

2025-02-06 11:06:02,337 - private_devbot_logger - ERROR - [ERROR] Search failed: Could not find document for id 27811f15-4dd5-4c42-93e6-8a041c8b943c, got ID 27811f15-4dd5-4c42-93e6-8a041c8b943c not found.
Traceback (most recent call last):
File "D:\dev\work\private-devbot\main.py", line 107, in search_documents
result = vector_db.search(request.query, request.k)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "D:\dev\work\private-devbot\vectorstore.py", line 264, in search
docs = self.vector_store.similarity_search_with_score(
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "C:\Users\min.ho.kim\AppData\Local\miniconda3\envs\pd1\Lib\site-packages\langchain_community\vectorstores\faiss.py", line 516, in similarity_search_with_score
docs = self.similarity_search_with_score_by_vector(
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "C:\Users\min.ho.kim\AppData\Local\miniconda3\envs\pd1\Lib\site-packages\langchain_community\vectorstores\faiss.py", line 430, in similarity_search_with_score_by_vector  
 raise ValueError(f"Could not find document for id {\_id}, got {doc}")
ValueError: Could not find document for id 27811f15-4dd5-4c42-93e6-8a041c8b943c, got ID 27811f15-4dd5-4c42-93e6-8a041c8b943c not found.
[Kss]: [ERROR] Search failed: Could not find document for id 27811f15-4dd5-4c42-93e6-8a041c8b943c, got ID 27811f15-4dd5-4c42-93e6-8a041c8b943c not found.
Traceback (most recent call last):
File "D:\dev\work\private-devbot\main.py", line 107, in search_documents
result = vector_db.search(request.query, request.k)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "D:\dev\work\private-devbot\vectorstore.py", line 264, in search
docs = self.vector_store.similarity_search_with_score(
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "C:\Users\min.ho.kim\AppData\Local\miniconda3\envs\pd1\Lib\site-packages\langchain_community\vectorstores\faiss.py", line 516, in similarity_search_with_score
docs = self.similarity_search_with_score_by_vector(
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "C:\Users\min.ho.kim\AppData\Local\miniconda3\envs\pd1\Lib\site-packages\langchain_community\vectorstores\faiss.py", line 430, in similarity_search_with_score_by_vector  
 raise ValueError(f"Could not find document for id {\_id}, got {doc}")
ValueError: Could not find document for id 27811f15-4dd5-4c42-93e6-8a041c8b943c, got ID 27811f15-4dd5-4c42-93e6-8a041c8b943c not found.
INFO: 168.219.61.213:42313 - "POST /search HTTP/1.1" 500 Internal Server Error

### 유사도 점수 확인

결론 : BGE-M3-KOREAN이 제일 좋은 결과를 보임

임베딩 방식으로 해봤으나 결과가 더 좋지 않음

```
embedded_query = self.embeddings.embed_query(query)
        print(embedded_query)
        docs = self.vector_store.similarity_search_with_score_by_vector(
            embedding=embedded_query,
            k=k
        )
        logger.debug(f"[DEBUG] Found {len(docs)} documents")

        results = []
        print(docs)
        for doc, distance in docs:
            similarity = 1. / (1. + float(distance))
            logger.debug(f"[DEBUG] Doc: {doc.metadata['source']}, Distance: {distance}, Similarity: {similarity}")

            results.append({
                "content": self._decode_text(doc.page_content),
                "score": similarity,
                "keywords": keywords,
                "file_path": doc.metadata['source'],
                "metadata": {
                    key: self._decode_text(value) if isinstance(value, bytes) else value
                    for key, value in doc.metadata.items()
                }
            })

2025-02-06 10:39:41,792 - private_devbot_logger - DEBUG - [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 7.801346302032471, Similarity: 0.11361898119712353
[Kss]: [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 7.801346302032471, Similarity: 0.11361898119712353
2025-02-06 10:39:41,792 - private_devbot_logger - DEBUG - [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 8.395318984985352, Similarity: 0.10643598174772978
[Kss]: [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 8.395318984985352, Similarity: 0.10643598174772978
2025-02-06 10:39:41,792 - private_devbot_logger - DEBUG - [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 8.954057693481445, Similarity: 0.10046154350249185
[Kss]: [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 8.954057693481445, Similarity: 0.10046154350249185
2025-02-06 10:39:41,793 - private_devbot_logger - DEBUG - [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 10.532750129699707, Similarity: 0.08670958693752938
[Kss]: [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 10.532750129699707, Similarity: 0.08670958693752938
2025-02-06 10:39:41,793 - private_devbot_logger - DEBUG - [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 10.637269020080566, Similarity: 0.08593081403157911
[Kss]: [DEBUG] Doc: D:\4.Archive\obsidian\임시노트.md, Distance: 10.637269020080566, Similarity: 0.08593081403157911
2025-02-06 10:39:41,793 - private_devbot_logger - DEBUG - [DEBUG] Returning 5 sorted results

```

### 기본 Flutter 기반 UI 개발 완료

## 2025.02.05

Flutter 기반 UI 개발 시작

---

## 2025.02.04

다중 파일 삭제 처리
POST 방식 처리를 위해서 FastAPI 실행 시 서버 IP를 0.0.0.0으로 셋팅해야 함.

---

## 2025.02.03

키워드 추출 및 Highlight 처리 완료
main -> vectorstore 분리 완료

## 원본 파일의 마지막 수정일자 기준으로 파일 업데이트

문제: streamlit에서는 파일 선택 대화상자를 통해서 파일을 선택 시 원본 파일의 마지막 수정일자를 구할 수 없음.
=> 선택된 파일에 대해 항상 기존 벡터 저장소를 삭제하고, 마지막 수정일자가 아니라, "업로드 일자"로 관리.

---

## 2025.02.02

### 동일 문서 첨부 시 청크가 추가되는 문제 해결

다운로드 받은 임베딩 모델 사용 처리 완료료

---

## 2025.01.27

### 벡터 저장소 초기화 오류 수정

원인1: 빈 리스트(texts=[])로 FAISS 인덱스를 생성하려 시도 → IndexError 발생.
해결: 초기화 시 FAISS 인덱스 생성 로직을 제거하고, 첫 파일 업로드 시 자연스럽게 인덱스가 생성되도록 수정

원인2: 초기화 후 file_monitor.py가 기존 폴더를 계속 모니터링 → 파일 재업로드 발생.

### 서버 로딩 전 클라이언트 실행 문제

서버 연결 오류: HTTPConnectionPool(host='localhost', port=8123): Max retries exceeded with url: /documents (Caused by NewConnectionError('<urllib3.connection.HTTPConnection object at 0x000001676EFDE910>: Failed to establish a new connection: [WinError 10061] 대상 컴퓨터에서 연결을 거부했으므로 연결하지 못했습니다'))

### 최신 패키지 로딩 문제

WARNING: StatReload detected changes in 'main.py'. Reloading...
D:\dev\work\private-devbot\main.py:50: LangChainDeprecationWarning: The class `HuggingFaceEmbeddings` was deprecated in LangChain 0.2.2 and will be removed in 1.0. An updated version of the class exists in the :class:`~langchain-huggingface package and should be used instead. To use it run `pip install -U :class:`~langchain-huggingface` and import as `from :class:`~langchain_huggingface import HuggingFaceEmbeddings``.
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
