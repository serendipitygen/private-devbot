import json

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Body, Depends
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Dict, Any
import sys
import os
import logging

import config
import logger_util

import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from document_reader import DocumentReader
import platform
from ip_middleware import IPRestrictionMiddleware
from rag_manager import rag_manager


# VectorStore 인스턴스는 rag_manager에서 필요 시 가져온다.
default_vector_store = rag_manager.get_store(None)
document_reader = DocumentReader()

logger = logger_util.get_logger()

os_name = platform.system() # Windows | Linux | Darwin

# FastAPI 앱 초기화
app = FastAPI()

# IP 제한 미들웨어 추가
private_devbot_version = config.private_devbot_version
ip_middleware = None

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
    rag_name: str | None = None

class FileContentsRequest(BaseModel):
    file_path: str
    file_name: str
    file_size: int
    content: str
    extraction_time: str
    rag_name: str | None = None

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_path: str = Form(...),
    rag_name: str | None = Form(None)
):
    vector_store = rag_manager.get_store(rag_name)

    try:
        logger.debug(f"[DEBUG] Upload request - Path: {file_path}")

        success, file_name = await _process_file(file, file_path, vector_store)

        result = {
            "status": "success" if success else "failed",
            "message": f"Processed {file_name}",
        }
    except Exception as e:
        logger.exception(f"[ERROR] Upload failed: {str(e)}")
        raise HTTPException(500, detail=f"Upload failed: {str(e)}")
    finally:
        vector_store.save_indexed_files_and_vector_db()
        return JSONResponse(content=result)

@app.post("/upload_file_contents")
async def upload_file_contents(request: FileContentsRequest):
    vector_store = rag_manager.get_store(request.rag_name)

    try:
        logger.debug(f"[DEBUG] Upload file contents request - Path: {request.file_path}")
        
        # Create a dictionary with the expected format for vector_store.upload
        # The content from the client is already a string, but vector_store expects a dict with 'contents' key
        file_contents = {
            "contents_type": "TEXT",  # Default to TEXT type
            "contents": request.content
        }
        
        # Upload to vector store
        result = await vector_store.upload(
            file_path=request.file_path, 
            file_name=request.file_name,
            contents=file_contents
        )

        if result['status'] != 'success':
            return JSONResponse(
                content={
                    "status": "failed",
                    "message": f"Failed to process {request.file_name}",
                    "details": result.get('message', 'Unknown error')
                },
                status_code=400
            )
    except Exception as e:
        logger.exception(f"[ERROR] Upload file contents failed: {str(e)}")
        raise HTTPException(500, detail=f"Upload file contents failed: {str(e)}")
    finally:
        vector_store.save_indexed_files_and_vector_db()
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Processed {request.file_name}",
                "details": result.get('message', '')
            }
        )

@app.post("/upload_file_path")
async def upload_file_path(
    file_path: str = Form(...),
    rag_name: str | None = Form(None)
):
    vector_store = rag_manager.get_store(rag_name)
    try:
        logger.debug(f"[DEBUG] Upload by file path request - Path: {file_path}")
        if not os.path.exists(file_path):
            return JSONResponse(content={"status": "failed", "message": f"File not found: {file_path}"}, status_code=400)
        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".eml"]:
            file_contents = document_reader.get_eml_contents(filepath=file_path, type="EML")
        elif ext in [".mht"]:
            file_contents = document_reader.get_eml_contents(filepath=file_path, type="MHT")
        elif ext in [".doc", ".docx"]:
            file_contents = document_reader.get_msoffice_contents(filepath=file_path, contents_type="MSWORD")
        elif ext in [".ppt", ".pptx"]:
            file_contents = document_reader.get_msoffice_contents(filepath=file_path, contents_type="MSPOWERPOINT")
        elif ext in [".xls", ".xlsx"]:
            file_contents = document_reader.get_excel_contents(filepath=file_path, contents_type="MSEXCEL")
        elif ext in [".pdf"]:
            file_contents = document_reader.get_pdf_contents(filepath=file_path, contents_type="PDF")
        else:
            with open(file_path, "rb") as f:
                contents = f.read()
            import chardet
            detection = chardet.detect(contents)
            encoding = detection.get('encoding') or 'utf-8'
            text_contents = contents.decode(encoding, errors='replace')
            file_contents = {
                "contents_type": "TEXT",
                "contents": text_contents
            }
        result = await vector_store.upload(file_path=file_path, file_name=os.path.basename(file_path), contents=file_contents)
        status = "success" if result.get("status") == "success" else "failed"
        vector_store.save_indexed_files_and_vector_db()
        return JSONResponse(content={"status": status, "message": result.get("message", ""), "details": result}, status_code=200 if status=="success" else 500)
    except Exception as e:
        logger.error(f"[ERROR] Upload by file path failed: {e}")
        return JSONResponse(content={"status": "failed", "message": str(e)}, status_code=500)

@app.post("/upload/batch")
async def upload_files(
    files: List[UploadFile] = File(...),
    file_paths: str = Form(...),
    rag_name: str | None = Form(None)
):
    vector_store = rag_manager.get_store(rag_name)

    try:
        file_paths_data = json.loads(file_paths)
        success_count = 0
        failed_files = []
        
        # 파일 경로 매핑 생성
        path_mapping = {
            fp['filename']: fp['file_path'] 
            for fp in file_paths_data
        }

        for file in files:
            file_path = path_mapping.get(file.filename)
            result, failed_file = await _process_file(file, file_path, vector_store)
            if result:
                success_count += 1
            else:
                failed_files.append(failed_file)
   
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        vector_store.save_indexed_files_and_vector_db()
        return {
            "status": "success" if len(failed_files) == 0 else "failed",
            "message": f"Processed {len(files)} files",
            "success_count": success_count,
            "failed_files": failed_files
        }  
    
async def _process_file(file: UploadFile, file_path:str, vector_store):
    try:
        file_contents = await document_reader.get_contents(file, file_path)

        result = await vector_store.upload(file_path=file_path, file_name=file.filename,
                    contents=file_contents)
        if result['status'] != 'success':
            return False, file.filename
        
        return True, file.filename
    except Exception as e:
        print(f"Error processing {file.filename}: {str(e)}")
        return False, file.filename

@app.post("/search")
async def search_documents(request: SearchRequest):
    vector_store = rag_manager.get_store(request.rag_name)

    try:
        print(f"[DEBUG] Searching with query: {request.query}, {request.k}")
        
        result = vector_store.search(request.query, request.k)
    
        # json.dumps를 사용하여 ensure_ascii=False로 한글이 깨지지 않도록 함.
        json_data = json.dumps(result, ensure_ascii=False)
        return Response(
            content=json_data,
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        logger.exception(f"[ERROR] Search failed: {str(e)}")
        raise HTTPException(500, detail=str(e))

@app.get("/documents")
async def get_documents(
    response: Response, 
    page: int = 1, 
    page_size: int = 50, 
    sort_by: str = "file_name", 
    sort_desc: bool = False, 
    file_type: str = None,
    file_name: str = None,
    file_path: str = None,
    min_chunks: int = None,
    max_chunks: int = None,
    rag_name: str | None = None
):
    vector_store = rag_manager.get_store(rag_name)

    try:
        # 요청 필터링 매개변수 로깅
        logger.debug(f"[DEBUG] Document filter request - page: {page}, size: {page_size}, "
                    f"file_type: {file_type}, file_name: {file_name}, file_path: {file_path}, "
                    f"min_chunks: {min_chunks}, max_chunks: {max_chunks}")
        
        # 전체 문서 가져오기
        all_documents = vector_store.get_documents()
        
        # 필터링 적용 - 변경된 부분
        filtered_documents = all_documents
        
        # 1. 파일 타입 필터링
        if file_type:
            logger.debug(f"[DEBUG] Applying file_type filter: {file_type}")
            filtered_documents = [doc for doc in filtered_documents 
                              if doc.get("file_type", "").lower() == file_type.lower()]
        
        # 2. 파일명 필터링 (부분 일치)
        if file_name:
            logger.debug(f"[DEBUG] Applying file_name filter: {file_name}")
            filtered_documents = [doc for doc in filtered_documents 
                              if file_name.lower() in doc.get("file_name", "").lower()]
        
        # 3. 파일 경로 필터링 (부분 일치)
        if file_path:
            logger.debug(f"[DEBUG] Applying file_path filter: {file_path}")
            filtered_documents = [doc for doc in filtered_documents 
                              if file_path.lower() in doc.get("file_path", "").lower()]
        
        # 4. 최소 청크 수 필터링
        if min_chunks is not None:
            logger.debug(f"[DEBUG] Applying min_chunks filter: {min_chunks}")
            filtered_documents = [doc for doc in filtered_documents 
                              if doc.get("chunk_count", 0) >= min_chunks]
        
        # 5. 최대 청크 수 필터링
        if max_chunks is not None:
            logger.debug(f"[DEBUG] Applying max_chunks filter: {max_chunks}")
            filtered_documents = [doc for doc in filtered_documents 
                              if doc.get("chunk_count", 0) <= max_chunks]

        # 필터링 결과 로그
        logger.debug(f"[DEBUG] Filtering result: {len(filtered_documents)} documents (from {len(all_documents)})")
        
        # 정렬 방향 결정
        reverse = sort_desc
        
        # 정렬 적용
        if sort_by in ["file_name", "file_type", "last_updated", "chunk_count"]:
            sorted_documents = sorted(filtered_documents, key=lambda x: x.get(sort_by, ""), reverse=reverse)
        else:
            # 기본 정렬은 파일명
            sorted_documents = sorted(filtered_documents, key=lambda x: x.get("file_name", ""), reverse=reverse)

        # 페이지네이션 적용
        total_count = len(sorted_documents)
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_count)
        paginated_documents = sorted_documents[start_idx:end_idx]
        
        # FastAPI 응답 헤더에 캐시 제어 설정
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"  # HTTP/1.0 호환용
        response.headers["Expires"] = "0"       # 프록시 서버 등에서 캐시하지 않도록
        
        result = {
            "documents": paginated_documents,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size
        }
        return result
    except Exception as e:
        logger.exception(f"[ERROR] Failed to get documents: {str(e)}")
        raise HTTPException(500, detail=str(e))

@app.get("/document")
async def get_document(file_path: str, rag_name: str | None = None):
    vector_store = rag_manager.get_store(rag_name)

    try:
        chunks = vector_store.get_document_chunks(file_path)

        return {"status": "success", "file_path": file_path, "chunks": chunks}
    except Exception as e:
        logger.exception(str(e))
        raise HTTPException(status_code=500, detail=str(e))

class DeleteRequest(BaseModel):
    file_paths: List[str]

@app.delete("/documents")
async def delete_documents(request: DeleteRequest, rag_name: str | None = None):
    vector_store = rag_manager.get_store(rag_name)

    try:
        vector_store.delete_documents(request.file_paths)
    except Exception as e:
        logger.exception(str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        vector_store.save_indexed_files_and_vector_db()
        return JSONResponse(content={
                "status": "success", 
                "message": "Documents deleted successfully."
            }, status_code=200)


@app.delete("/documents/all")
async def delete_all_documents(rag_name: str | None = None):
    vector_store = rag_manager.get_store(rag_name)

    try:
        vector_store.delete_all_documents()
    except Exception as e:
        logger.exception(str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        vector_store.save_indexed_files_and_vector_db()
        return JSONResponse(content={
            "status": "success", 
            "message": "All documents deleted successfully."
        }, status_code=200)

import datetime  # 추가된 import 구문



@app.get("/health")
async def health_check():
    """
    간단한 헬스 체크 API - 서버가 실행 중인지만 확인합니다.
    클라이언트는 이 API를 통해 서버 연결 상태를 확인할 수 있습니다.
    """
    try:
        # datetime을 사용하여 현재 시간을 가져오도록 수정
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 응답 객체 생성
        response = {
            "status": "success",
            "message": "server is working successfully",
            "timestamp": current_time
        }
        
        # FastAPI의 JSONResponse를 반환하여 헤더 설정
        from fastapi.responses import JSONResponse
        resp = JSONResponse(content=response)
        
        # 캐시 방지 헤더 추가
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"  # HTTP/1.0 호환용
        resp.headers["Expires"] = "0"        # 추가적인 캐시 방지
        
        return resp
    except Exception as e:
        logger.error(f"[ERROR] Fail to check Server Health: {str(e)}")
        raise HTTPException(500, detail=f"Server Error: {str(e)}")

@app.get("/status")
async def get_status(rag_name: str | None = None):
    vector_store = rag_manager.get_store(rag_name)

    try:
        document_count = vector_store.get_indexed_file_count()
        index_size = vector_store.get_db_size() / (1024 * 1024)  # MB로 변환
        # 응답 데이터 준비
        response_data = {
            "status": "success",
            "document_count": document_count,
            "index_size_mb": round(index_size, 2),
            "index_path": vector_store.get_vector_db_path(),
            "os_name": os_name
        }
        
        # FastAPI의 JSONResponse를 반환하여 헤더 설정
        from fastapi.responses import JSONResponse
        resp = JSONResponse(content=response_data)
        
        # 캐시 방지 헤더 추가
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"  # HTTP/1.0 호환용
        resp.headers["Expires"] = "0"        # 추가적인 캐시 방지
        
        return resp
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(500, detail=str(e))

@app.post("/reset")
async def reset_storage(rag_name: str | None = None):
    vector_store = rag_manager.get_store(rag_name)

    try:
        vector_store.empty_vector_store()
    except Exception as e:
        logger.exception(f"[ERROR] Reset failed: {str(e)}")
        raise HTTPException(500, detail=f"Reset failed: {str(e)}")
    finally:
        vector_store.save_indexed_files_and_vector_db()
        return JSONResponse(content={
            "status": "success", 
            "message": "Vector store and indexed files have been reset."
        }, status_code=200)

@app.post("/register_ips")
async def register_ips(ips: List[str] = Body(...)):
    """
    허용된 IP 목록을 등록합니다.
    빈 목록을 전달하면 모든 IP가 허용됩니다.
    """
    try:
        result = ip_middleware.update_allowed_ips(ips)
        return JSONResponse(content=result)
    except Exception as e:
        logger.exception(f"[ERROR] Fail to register IP: {str(e)}")
        raise HTTPException(500, detail=f"Fail to register IP: {str(e)}")

@app.get("/get_allowed_ips")
async def get_allowed_ips():
    """
    현재 허용된 IP 목록을 반환합니다.
    """
    try:
        allowed_ips = ip_middleware.get_allowed_ips()
        print(f"Allowed IP List: {allowed_ips}")
        return JSONResponse(content={
            "status": "success",
            "allowed_ips": allowed_ips,
            "message": "Allowed IP list"
        })
    except Exception as e:
        logger.exception(f"[ERROR] IP Searching failed: {str(e)}")
        raise HTTPException(500, detail=f"IP Searching Failure: {str(e)}")

# 로그 핸들러 정의
class CustomLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []

    def emit(self, record):
        self.logs.append(self.format(record))


import argparse

def _get_port_from_cmd():
    parser = argparse.ArgumentParser(description="Data Store Port Argument")

    parser.add_argument(
        "--port", type=int, required=False, help="Dart Store running port setting : 1025 ~ 65535"
    )

    args = parser.parse_args()

    return args.port

def _get_port_from_config_file():
    import os
    config_file_path = os.path.join(os.path.dirname(__file__), 'devbot_config.json') 
    try:
        with open(config_file_path, 'r', encoding='utf-8') as f:
            app_config = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Configuration file devbot_config.json not found at {config_file_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"[ERROR] Error decoding JSON from devbot_config.json")
        sys.exit(1)
    
    return int(app_config.get('port'))

def _run_on_cmd(port: int):
    assert port is not None
    
    default_vector_store.initialize_embedding_model_and_vectorstore()

    ip_middleware = IPRestrictionMiddleware(app)
    app.add_middleware(IPRestrictionMiddleware, config_path=f"./store/devbot_config_{private_devbot_version}.yaml")

    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    # 명령 프롬프트에서 실행 시 port가 포함되어 있는지 확인
    port = _get_port_from_cmd()

    # devbot_config.json 파일에서 포트 번호를 가져옵니다.
    if port is None:
        port = _get_port_from_config_file()

    if port is None:
        print(f"[ERROR] Port not specified in devbot_config.json. Defaulting to 8123 or exiting.")
        sys.exit(1)

    _run_on_cmd(port=port)