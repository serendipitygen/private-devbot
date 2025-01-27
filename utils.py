from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    PythonLoader
)
from langchain.schema import Document
import tempfile
import os
from pptx import Presentation  # 추가
import time

# PPTX 커스텀 로더 추가
class PPTXLoader:
    def __init__(self, file_path):
        self.file_path = file_path

    def load(self):
        prs = Presentation(self.file_path)
        text = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text.append(shape.text)
        return [Document(page_content="\n".join(text), metadata={"source": self.file_path})]

def process_file(file_content, filename):
    # 임시 파일 생성 및 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=filename) as tmp:
        try:
            tmp.write(file_content)
            tmp.flush()  # 버퍼 내용을 즉시 디스크에 쓰기
            print(f"[DEBUG] Created temp file: {tmp.name}")

            file_ext = os.path.splitext(filename)[1].lower()
            print(f"[DEBUG] Processing file type: {file_ext}")

            # 파일 유형별 처리
            if file_ext == ".pdf":
                loader = PyPDFLoader(tmp.name)
            elif file_ext == ".docx":
                loader = Docx2txtLoader(tmp.name)
            elif file_ext == ".pptx":
                loader = PPTXLoader(tmp.name)
            elif file_ext in [".txt", ".md"]:
                loader = TextLoader(tmp.name, encoding='utf-8')
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")

            # 문서 로드
            docs = loader.load()
            print(f"[DEBUG] Loaded {len(docs)} documents from {filename}")

            # 메타데이터 추가
            for doc in docs:
                doc.metadata.update({
                    "source": filename,
                    "file_type": file_ext[1:],
                    "timestamp": time.time()
                })

            return docs

        except Exception as e:
            print(f"[ERROR] Failed to process {filename}: {str(e)}")
            raise

        finally:
            # 임시 파일 정리
            try:
                os.unlink(tmp.name)
                print(f"[DEBUG] Cleaned up temp file: {tmp.name}")
            except Exception as e:
                print(f"[WARNING] Failed to cleanup temp file: {str(e)}")
