import asyncio
import json

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List

import config
import logger_util

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from vector_store import VectorStore

# 벡터 저장소 및 관련 변수 초기화
vector_store = VectorStore()

logger = logger_util.get_logger()



# FastAPI 앱 초기화
app = FastAPI()

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
):
    global vector_store

    try:
        logger.debug(f"**********[DEBUG] Upload request - Path: {file_path}")
        
        file_contents = await file.read()
        content = await vector_store.upload(file_path=file_path, file_name=file.filename,
                            content=file_contents)
        return JSONResponse(content=content)

    except Exception as e:
        logger.exception(f"[ERROR] Upload failed: {str(e)}")
        raise HTTPException(500, detail=f"Upload failed: {str(e)}")

@app.post("/upload/batch")
async def upload_files(
    files: List[UploadFile] = File(...),
    file_paths: str = Form(...)  # JSON 문자열로 전달된 파일 경로 정보
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

        async def process_file(file: UploadFile):
            try:
                file_contents = await file.read()
                file_path = path_mapping.get(file.filename)
                content = await vector_store.upload(file_path=file_path, file_name=file.filename,
                            content=file_contents)
                if content['status'] != 'success':
                    failed_files.append(file.filename)
                    return False
                
                return True
            except Exception as e:
                print(f"Error processing {file.filename}: {str(e)}")
                failed_files.append(file.filename)
                return False

        # 모든 파일 동시 처리
        tasks = [process_file(file) for file in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for result in results if result is True)

        return {
            "status": "success",
            "message": f"Processed {len(files)} files",
            "success_count": success_count,
            "failed_files": failed_files
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
async def get_documents():
    global vector_store

    try:
        documents = vector_store.get_documents()
        
        result = {"documents": sorted(documents, key=lambda x: x["file_name"])}
        return result
    except Exception as e:
        logger.exception(str(e))
        raise HTTPException(500, detail=str(e))

class DeleteRequest(BaseModel):
    file_paths: List[str]

@app.delete("/documents")
async def delete_documents(request: DeleteRequest):
    try:
        vector_store.delete_documents(request.file_paths)
        return {"message": "Documents deleted successfully."}
    except Exception as e:
        logger.exception(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/documents/all")
async def delete_all_documents():
    try:
        vector_store.delete_all_documents()
        return {"message": "All documents deleted successfully."}
    except Exception as e:
        logger.exception(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    try:
        document_count = vector_store.get_indexed_file_count()
        index_size = vector_store.get_db_size() / (1024 * 1024)  # MB로 변환
        return {
            "document_count": document_count,
            "index_size_mb": round(index_size, 2),
            "index_path": vector_store.get_vector_db_path()
        }
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(500, detail=str(e))

@app.post("/reset")
async def reset_storage():
    global vector_store

    try:
        vector_store.empty_vector_store()

        return JSONResponse(content={
            "status": "success", 
            "message": "Vector store and indexed files have been reset."
        }, status_code=200) # 상태 코드 200으로 변경
    except Exception as e:
        logger.exception(f"[ERROR] Reset failed: {str(e)}")
        raise HTTPException(500, detail=f"Reset failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.server_port)