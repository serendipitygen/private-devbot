import json

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Body, Depends
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Dict, Any

import config
import logger_util

from fastapi.middleware.cors import CORSMiddleware
from vector_store import VectorStore
from document_reader import DocumentReader
import platform
from ip_middleware import IPRestrictionMiddleware


# 벡터 저장소 및 관련 변수 초기화
vector_store = VectorStore()
document_reader = DocumentReader()

logger = logger_util.get_logger()

os_name = platform.system() # Windows | Linux | Darwin

# FastAPI 앱 초기화
app = FastAPI()

# IP 제한 미들웨어 추가
ip_middleware = IPRestrictionMiddleware(app)
app.add_middleware(IPRestrictionMiddleware, config_path="devbot_config.yaml")

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

class FileContentsRequest(BaseModel):
    file_path: str
    file_name: str
    file_size: int
    content: str
    extraction_time: str

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_path: str = Form(...),
):
    global vector_store

    try:
        logger.debug(f"[DEBUG] Upload request - Path: {file_path}")

        success, file_name = await _process_file(file, file_path)

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
    global vector_store

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


@app.post("/upload/batch")
async def upload_files(
    files: List[UploadFile] = File(...),
    file_paths: str = Form(...)
):
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
            result, failed_file = await _process_file(file, file_path)
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
    
async def _process_file(file: UploadFile, file_path:str):
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
    global vector_store

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
async def get_documents(response: Response):
    global vector_store

    try:
        documents = vector_store.get_documents()

        # FastAPI 응답 헤더에 캐시 제어 설정
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"  # HTTP/1.0 호환용
        response.headers["Expires"] = "0"       # 프록시 서버 등에서 캐시하지 않도록
        
        result = {"documents": sorted(documents, key=lambda x: x["file_name"])}
        return result
    except Exception as e:
        logger.exception(str(e))
        raise HTTPException(500, detail=str(e))

@app.get("/document")
async def get_document(file_path: str):
    global vector_store

    try:
        chunks = vector_store.get_document_chunks(file_path)

        return {"status": "success", "file_path": file_path, "chunks": chunks}
    except Exception as e:
        logger.exception(str(e))
        raise HTTPException(status_code=500, detail=str(e))

class DeleteRequest(BaseModel):
    file_paths: List[str]

@app.delete("/documents")
async def delete_documents(request: DeleteRequest):
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
async def delete_all_documents():
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

@app.get("/status")
async def get_status():
    try:
        document_count = vector_store.get_indexed_file_count()
        index_size = vector_store.get_db_size() / (1024 * 1024)  # MB로 변환
        return {
            "status": "success",
            "document_count": document_count,
            "index_size_mb": round(index_size, 2),
            "index_path": vector_store.get_vector_db_path(),
            "os_name": os_name
        }
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(500, detail=str(e))

@app.post("/reset")
async def reset_storage():
    global vector_store

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
        logger.exception(f"[ERROR] IP 등록 실패: {str(e)}")
        raise HTTPException(500, detail=f"IP 등록 실패: {str(e)}")

@app.get("/get_allowed_ips")
async def get_allowed_ips():
    """
    현재 허용된 IP 목록을 반환합니다.
    """
    try:
        allowed_ips = ip_middleware.get_allowed_ips()
        print(f"허용된 IP 목록: {allowed_ips}")
        return JSONResponse(content={
            "status": "success",
            "allowed_ips": allowed_ips,
            "message": "현재 허용된 IP 목록입니다."
        })
    except Exception as e:
        logger.exception(f"[ERROR] IP 목록 조회 실패: {str(e)}")
        raise HTTPException(500, detail=f"IP 목록 조회 실패: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    import argparse
    
    # 명령줄 인자 파서 생성
    parser = argparse.ArgumentParser(description='DevBot 서버 실행')
    parser.add_argument('--port', type=int, default=config.server_port,
                        help=f'서버 실행 포트 (기본값: {config.server_port})')
    
    # 명령줄 인자 파싱
    args = parser.parse_args()
    
    # 포트 설정
    port = args.port
    print(f"서버가 포트 {port}에서 실행됩니다...")
    
    # 서버 실행
    uvicorn.run(app, host="0.0.0.0", port=port)