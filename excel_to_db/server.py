from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import io
import base64
import logging
import json
from pathlib import Path

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# CORS 설정 (Railway에서 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Railway 도메인에서 접근 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request Body 모델
class ExcelDescriptionRequest(BaseModel):
    description_file_path: str



@app.get('/health')
async def health_check():
    return JSONResponse(content={'status': 'healthy'})


@app.post("/read_excel_description")
async def read_excel_description(request: ExcelDescriptionRequest) -> JSONResponse:
    """
    docs/excel/ 디렉토리의 마크다운 파일을 읽어 내용 반환
    파일명만 제공하면 docs/excel/ 아래에서 찾고, 전체 경로 제공도 가능
    """
    try:
        # 현재 프로젝트 루트 경로
        project_root = Path(__file__).parent.parent
        excel_docs_dir = project_root / "docs" / "excel"
        
        # 파일명만 제공된 경우 기본 경로(docs/excel/) 사용
        if "/" not in request.description_file_path and "\\" not in request.description_file_path:
            target_file = excel_docs_dir / request.description_file_path
        else:
            # 전체 경로 제공된 경우
            target_file = project_root / request.description_file_path
        
        # 경로 정규화 및 보안 검증
        target_file = target_file.resolve()
        project_root = project_root.resolve()
        
        # 현재 프로젝트 디렉토리 내부인지 확인
        if not str(target_file).startswith(str(project_root)):
            return JSONResponse(status_code=403, content={"error": "Access denied: File must be within project directory"})
        
        # 파일 존재 확인
        if not target_file.exists():
            return JSONResponse(status_code=404, content={"error": f"File not found: {request.description_file_path}"})
        
        # 파일인지 확인
        if not target_file.is_file():
            return JSONResponse(status_code=400, content={"error": f"Not a file: {request.description_file_path}"})
        
        # 마크다운 파일인지 확인
        if target_file.suffix.lower() not in ['.md', '.markdown']:
            return JSONResponse(status_code=400, content={"error": f"Not a markdown file: {request.description_file_path}"})
        
        # 파일 읽기
        text = target_file.read_text(encoding="utf-8")
        
    except Exception as e:
        logging.error(f"Failed to read file {request.description_file_path}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Failed to read file: {str(e)}"})

    return JSONResponse(content={"type": "read-excel-description", "message": text})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080)