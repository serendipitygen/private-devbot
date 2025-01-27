from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
import stat
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,  # 추가
    CSVLoader,  # 추가
    PythonLoader,
)

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
import asyncio
import time
import hashlib
import os
import re


# PPTX 커스텀 로더 추가
from pptx import Presentation

class PPTXLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path
    
    def load(self) -> list:
        prs = Presentation(self.file_path)
        text_content = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text_content.append(shape.text)
        return [Document(page_content="\n".join(text_content), metadata={"source": self.file_path})]

# 상수 정의
FAISS_INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faiss_index")
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

# FAISS 디렉토리 생성 (디렉토리 자체가 없을 경우)
if not os.path.exists(FAISS_INDEX):
    os.makedirs(FAISS_INDEX)
    print(f"Created FAISS directory: {FAISS_INDEX}")

# 업로드 디렉토리 생성
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created uploads directory: {UPLOAD_FOLDER}")

ALLOWED_EXTENSIONS = {
    "txt", "pdf", "png", "jpg", "jpeg", "gif", "csv", "md", 
    "html", "pptx", "docx", "epub", "odt"
}

app = FastAPI()
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FAISS_INDEX, exist_ok=True)

# 벡터 저장소 및 관련 변수 초기화
vector_store = None
vector_store_lock = asyncio.Lock()
document_hashes = {}

# 서버 시작 시 FAISS 저장소 초기화
def initialize_vector_store():
    global vector_store
    if os.path.exists(FAISS_INDEX):
        try:
            print("[INFO] Loading existing FAISS index...")
            vector_store = FAISS.load_local(
                FAISS_INDEX, 
                embeddings, 
                allow_dangerous_deserialization=True  # 옵션 재추가
            )
        except Exception as e:
            print(f"[ERROR] Failed to load FAISS index: {e}")
            vector_store = None

# FastAPI 앱 초기화 시 실행
@app.on_event("startup")
async def startup_event():
    initialize_vector_store()

# 임베딩 모델 초기화
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

class SearchRequest(BaseModel):
    query: str
    k: int = 5

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compute_file_hash(file_content: bytes) -> str:
    return hashlib.md5(file_content).hexdigest()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), file_hash: str = Form(...)):
    global vector_store
    async with vector_store_lock:
        try:
            # 파일 저장
            safe_filename = re.sub(r'[^\w가-힣-_.]', '_', file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, safe_filename)
            
            # 파일 저장
            content = await file.read()
            with open(file_path, "wb") as buffer:
                buffer.write(content)
            
            print(f"[DEBUG] Saved file: {os.path.abspath(file_path)}")

            # 문서 처리를 위해 utils.process_file 사용
            from utils import process_file
            try:
                texts = process_file(content, safe_filename)
                print(f"[DEBUG] Processed {len(texts)} documents")

                # 청크 생성
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200,
                    separators=["\n\n", "\n", " ", ""]
                )
                chunks = text_splitter.split_documents(texts)
                print(f"[DEBUG] Created {len(chunks)} chunks")

                # 벡터 저장소에 추가
                if vector_store is None:
                    print("[DEBUG] Creating new vector store")
                    vector_store = FAISS.from_documents(chunks, embeddings)
                else:
                    print("[DEBUG] Adding to existing vector store")
                    vector_store.add_documents(chunks)

                # 저장
                vector_store.save_local(FAISS_INDEX)
                print(f"[DEBUG] Saved vector store to {FAISS_INDEX}")

                return JSONResponse(content={
                    "message": "File uploaded successfully",
                    "filename": safe_filename,
                    "chunks": len(chunks)
                })

            except Exception as e:
                print(f"[ERROR] Document processing failed: {str(e)}")
                raise HTTPException(500, detail=f"Document processing failed: {str(e)}")

        except Exception as e:
            print(f"[ERROR] File upload failed: {str(e)}")
            raise HTTPException(500, detail=f"File upload failed: {str(e)}")

@app.post("/search")
async def search_documents(request: SearchRequest):
    global vector_store
    if not vector_store:
        return {"results": []}

    try:
        print(f"[DEBUG] Searching with query: {request.query}")
        
        # FAISS 검색 실행
        docs = vector_store.similarity_search_with_score(
            request.query, 
            k=request.k
        )
        print(f"[DEBUG] Found {len(docs)} documents")
        
        # FAISS의 score는 거리(distance)이므로 값이 작을수록 유사도가 높음
        # L2 거리를 0-1 사이의 유사도 점수로 변환
        results = []
        for doc, score in docs:
            # 거리를 유사도로 변환 (1 / (1 + distance))
            similarity = 1 / (1 + float(score))
            print(f"[DEBUG] Doc: {doc.metadata['source']}, Distance: {score}, Similarity: {similarity}")
            
            results.append({
                "content": doc.page_content,
                "score": similarity,  # 0에 가까울수록 유사하지 않음, 1에 가까울수록 유사함
                "metadata": doc.metadata
            })
        
        # 유사도 점수로 정렬
        results.sort(key=lambda x: x["score"], reverse=True)
        print(f"[DEBUG] Returning {len(results)} sorted results")
        
        return {"results": results}
        
    except Exception as e:
        print(f"[ERROR] Search failed: {str(e)}")
        raise HTTPException(500, detail=str(e))

@app.get("/documents")
async def get_documents():
    global vector_store
    if vector_store is None:
        return {"documents": [], "message": "No documents have been indexed yet."}

    try:
        documents = []
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                file_type = filename.rsplit('.', 1)[1].lower()
                last_modified = os.path.getmtime(file_path)
                chunk_count = get_chunk_count(filename)
                documents.append({
                    "filename": filename,
                    "file_type": file_type,
                    "last_updated": last_modified,
                    "chunk_count": chunk_count
                })
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/status")
async def get_status():
    try:
        document_count = len(os.listdir(UPLOAD_FOLDER))
        index_size = get_directory_size(FAISS_INDEX) / (1024 * 1024)  # MB로 변환
        return {
            "document_count": document_count,
            "index_size_mb": round(index_size, 2),
            "index_path": os.path.abspath(FAISS_INDEX)
        }
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/reset")
async def reset_storage():
    global vector_store
    async with vector_store_lock:
        try:
            # FAISS 인덱스 삭제
            if os.path.exists(FAISS_INDEX):
                shutil.rmtree(FAISS_INDEX, onerror=remove_readonly)

            # 업로드된 파일 삭제
            for filename in os.listdir(UPLOAD_FOLDER):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)

            # 벡터 저장소 및 문서 해시 초기화
            vector_store = None
            document_hashes.clear()

            return JSONResponse(content={
                "status": "success", 
                "message": "Vector store and uploaded files have been reset."
            })
        except Exception as e:
            raise HTTPException(500, detail=str(e))

def remove_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def get_loader_class(file_name):
    extension = file_name.split(".")[-1].lower()
    loader_map = {
        "tsv": CSVLoader,
        "csv": CSVLoader,
        "pdf": PyPDFLoader,
        "txt": TextLoader,
        "md": TextLoader,
        "pptx": PPTXLoader,
        "docx": Docx2txtLoader,
        "py": PythonLoader,
        "html": TextLoader,
    }
    if extension not in loader_map:
        raise ValueError(f"Unsupported file extension: {extension}")
    return loader_map.get(extension)


def get_directory_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

from langchain_community.vectorstores import FAISS
def get_chunk_count(filename):
    if vector_store is None:
        return 0
    return len([doc for doc in vector_store.docstore._dict.values() 
                if doc.metadata.get("source") == filename])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8123)