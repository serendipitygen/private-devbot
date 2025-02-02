import shutil
import stat
import asyncio
import time
import re
import os
import pickle
import datetime
import numpy as np

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
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

from sentence_transformers import SentenceTransformer

from pptx import Presentation

import hashlib

import config

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

os.makedirs(config.FAISS_INDEX, exist_ok=True)

# 벡터 저장소 및 관련 변수 초기화
vector_store = None
vector_store_lock = asyncio.Lock()

# 문서 기록 저장
indexed_file_list = None

# 임베딩 모델 초기화
if not os.path.exists(config.EMBEDDING_MODEL_PATH):
    embeddings = HuggingFaceEmbeddings(model_name=config.MODEL_NAME)

    os.makedirs(config.EMBEDDING_MODEL_PATH, exist_ok=True)
    model = SentenceTransformer(config.MODEL_NAME)
    model.save(config.EMBEDDING_MODEL_PATH)
else:
    print(f"[DEBUG] 저장된 임베딩 모델을 로딩: {config.EMBEDDING_MODEL_PATH}")
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_PATH)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 실행
    print("[INFO] Starting up FastAPI application...")
    try:
        global vector_store, indexed_file_list
        
        # FAISS 벡터 스토어 초기화
        try:
            print(f"[INFO] Loading FAISS index from: {config.FAISS_INDEX}")
            vector_store = FAISS.load_local(
                config.FAISS_INDEX,
                embeddings,
                allow_dangerous_deserialization=True
            )
            if vector_store:
                doc_count = len(vector_store.docstore._dict)
                print(f"[INFO] Successfully loaded FAISS index with {doc_count} documents")
            else:
                print("[INFO] Creating new Vector Store")
                initialize_empty_vector_store()
        except Exception as e:
            print(f"[ERROR] Failed to initialize vector store: {e}")
            print("[INFO] Creating new empty vector store")
            initialize_empty_vector_store()

        # 인덱스된 파일 목록 초기화
        try:
            if os.path.exists(config.INDEXED_FILE_LIST):
                with open(config.INDEXED_FILE_LIST, 'rb') as f:
                    indexed_file_list = pickle.load(f)  # loads() 대신 load() 사용
                print(f"[INFO] Loaded {len(indexed_file_list)} indexed files")
            else:
                indexed_file_list = {}
                print("[INFO] Created new indexed file list")
        except Exception as e:
            print(f"[ERROR] Failed to load indexed file list: {e}")
            indexed_file_list = {}
    
    except Exception as e:
        print(f"[ERROR] Startup error: {e}")
        # 기본값으로 초기화
        vector_store = None
        indexed_file_list = {}
    
    yield  # FastAPI 애플리케이션 실행
    
    # 종료 시 실행
    try:
        if vector_store:
            vector_store.save_local(config.FAISS_INDEX)
            print("[INFO] Saved vector store before shutdown")
        
        if indexed_file_list:
            with open(config.INDEXED_FILE_LIST, 'wb') as f:
                pickle.dump(indexed_file_list, f)
            print("[INFO] Saved indexed file list")

    except Exception as e:
        print(f"[ERROR] Shutdown error: {e}")

# FastAPI 앱 초기화
app = FastAPI(lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    k: int = 5

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_path: str = Form(...),
    last_modified: float = Form(...)
):
    global vector_store, indexed_file_list
    async with vector_store_lock:
        try:
            print(f"[DEBUG] Upload request - Path: {file_path}, Modified: {time.ctime(last_modified)}")
            
            # 파일 존재 여부 및 수정 시간 체크
            is_update_needed = True
            if file_path in indexed_file_list:
                existing_last_modified = indexed_file_list[file_path]
                print(f"[DEBUG] Last modified comparison:")
                print(f"  - Existing: {time.ctime(existing_last_modified)} ({existing_last_modified})")
                print(f"  - New     : {time.ctime(last_modified)} ({last_modified})")
                
                # 수정 시간이 같거나 더 오래된 파일은 스킵
                if last_modified <= existing_last_modified:
                    print(f"[INFO] Skip indexing - File is up to date: {file_path}")
                    return JSONResponse(
                        status_code=200,
                        content={
                            "message": "File already exists and is up to date",
                            "filename": file_path,
                            "duplicate": True,
                            "existing_time": existing_last_modified,
                            "new_time": last_modified
                        }
                    )

            content = await file.read()
            
            # 기존 문서 삭제 (업데이트가 필요한 경우만)
            if file_path in indexed_file_list:
                print(f"[INFO] Updating existing file: {file_path}")
                await remove_existing_documents(file_path)

            # 새 문서 처리 및 추가
            texts = await process_and_add_documents(content, file, file_path)
            
            # 성공적으로 처리된 경우에만 indexed_file_list 업데이트
            indexed_file_list[file_path] = last_modified
            print(f"[INFO] Updated index timestamp for {file_path}: {time.ctime(last_modified)}")
            
            return JSONResponse(content={
                "message": "File uploaded successfully",
                "filename": file_path,
                "chunks": len(texts) if texts else 0
            })

        except Exception as e:
            print(f"[ERROR] Upload failed: {str(e)}")
            raise HTTPException(500, detail=f"Upload failed: {str(e)}")

async def remove_existing_documents(file_path: str):
    """기존 문서 삭제 함수"""
    global vector_store
    if not vector_store:
        return
        
    try:
        # 삭제할 문서 수집
        docs_with_id = {
            idx: doc for idx, doc in vector_store.docstore._dict.items()
            if doc.metadata.get("source", "") == file_path
        }
        
        if docs_with_id:
            print(f"[DEBUG] Removing {len(docs_with_id)} documents for: {file_path}")
            
            # 문서 삭제
            for doc_id in docs_with_id.keys():
                vector_store.docstore._dict.pop(doc_id)
            
            # 남은 문서로 벡터 저장소 재구축
            remaining_docs = list(vector_store.docstore._dict.values())
            
            if remaining_docs:
                # 기존 문서의 docstore ID를 보존하면서 재구축
                temp_store = FAISS.from_documents(remaining_docs, embeddings)
                vector_store = temp_store
            else:
                initialize_empty_vector_store()
                
            print(f"[INFO] Successfully rebuilt vector store with {len(remaining_docs)} documents")
            
            # 벡터 저장소 저장
            vector_store.save_local(config.FAISS_INDEX)
            
    except Exception as e:
        print(f"[ERROR] Failed to remove documents: {str(e)}")
        raise

async def process_and_add_documents(content: bytes, file: UploadFile, file_path: str):
    """문서 처리 및 추가 함수"""
    global vector_store
    
    try:
        from utils import process_file
        texts = process_file(content, file.filename, file_path)
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
            # 기존 문서의 docstore ID를 보존하면서 추가
            existing_docs = list(vector_store.docstore._dict.values())
            all_docs = existing_docs + chunks
            
            # 전체 문서로 새로운 벡터 저장소 생성
            temp_store = FAISS.from_documents(all_docs, embeddings)
            vector_store = temp_store

        # 저장
        vector_store.save_local(config.FAISS_INDEX)
        print(f"[DEBUG] Saved vector store with {len(vector_store.docstore._dict)} total documents")
        
        return texts

    except Exception as e:
        print(f"[ERROR] Document processing failed: {str(e)}")
        raise

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
        doc_paths = {}  # 파일 경로별 청크 수 집계
        
        # 먼저 벡터 스토어에서 문서 정보 수집
        if vector_store:
            for doc in vector_store.docstore._dict.values():
                path = doc.metadata.get("source")
                if path:
                    if path not in doc_paths:
                        doc_paths[path] = {
                            "filename": doc.metadata.get("filename", os.path.basename(path)),
                            "file_type": doc.metadata.get("file_type", "unknown"),
                            "last_updated": doc.metadata.get("timestamp", 0),
                            "chunk_count": 1
                        }
                    else:
                        doc_paths[path]["chunk_count"] += 1

        # 문서 목록 생성
        documents = [
            {
                "filename": info["filename"],
                "file_type": info["file_type"],
                "last_updated": info["last_updated"],
                "chunk_count": info["chunk_count"],
                "file_path": path
            }
            for path, info in doc_paths.items()
        ]
        
        return {"documents": sorted(documents, key=lambda x: x["filename"])}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.get("/status")
async def get_status():
    try:
        document_count = len(indexed_file_list)
        index_size = get_directory_size(config.FAISS_INDEX) / (1024 * 1024)  # MB로 변환
        return {
            "document_count": document_count,
            "index_size_mb": round(index_size, 2),
            "index_path": os.path.abspath(config.FAISS_INDEX)
        }
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@app.post("/reset")
async def reset_storage():
    global vector_store, indexed_file_list
    async with vector_store_lock:
        try:
            # FAISS 인덱스 디렉토리 삭제
            if os.path.exists(config.FAISS_INDEX):
                shutil.rmtree(config.FAISS_INDEX, onerror=remove_readonly)
            os.makedirs(config.FAISS_INDEX, exist_ok=True)

            # indexed_file_list 초기화
            indexed_file_list = {}
            if os.path.exists(config.INDEXED_FILE_LIST):
                os.remove(config.INDEXED_FILE_LIST)

            # 새로운 빈 벡터 스토어 생성
            initialize_empty_vector_store()

            return JSONResponse(content={
                "status": "success", 
                "message": "Vector store and indexed files have been reset."
            })
        except Exception as e:
            print(f"[ERROR] Reset failed: {str(e)}")
            raise HTTPException(500, detail=f"Reset failed: {str(e)}")

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
def get_chunk_count(file_path):  # filename 대신 file_path 사용
    if vector_store is None:
        return 0
    return len([doc for doc in vector_store.docstore._dict.values() 
                if doc.metadata.get("source") == file_path])

def initialize_empty_vector_store():
    """빈 FAISS 벡터 스토어 생성"""
    global vector_store
    try:
        print("[INFO] Creating new empty vector store")
        
        # 디렉토리 생성
        os.makedirs(config.FAISS_INDEX, exist_ok=True)
        
        # 빈 텍스트로 벡터 스토어 초기화
        empty_text = [""]  # 최소한 하나의 문서 필요
        vector_store = FAISS.from_texts(
            texts=empty_text,
            embedding=embeddings
        )
        
        # 초기 문서 제거
        vector_store.docstore._dict.clear()
        
        # 저장
        vector_store.save_local(config.FAISS_INDEX)
        print(f"[INFO] Created and saved empty vector store at {config.FAISS_INDEX}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to create empty vector store: {str(e)}")
        vector_store = None
        return False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.server_port)