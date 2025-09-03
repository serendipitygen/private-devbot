from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import io
import base64
import logging
import json
import sqlite3
from pathlib import Path
from typing import Optional

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


class InsertExcelRequest(BaseModel):
    excel_file_path: str
    insert_sql: str
    db_path: Optional[str] = "resources/data.db"

class SaveSystemPromptRequest(BaseModel):
    filename: str
    prompt: str

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


@app.post("/insert_excel")
async def insert_excel(request: InsertExcelRequest) -> JSONResponse:
    """
    Excel 파일을 읽어서 SQLite 데이터베이스에 각 행의 데이터를 삽입
    첫 번째 행은 헤더로 간주하고 두 번째 행부터 데이터로 처리
    """
    try:
        # 현재 프로젝트 루트 경로
        project_root = Path(__file__).parent.parent
        
        # Excel 파일 경로 처리
        excel_file = project_root / request.excel_file_path
        excel_file = excel_file.resolve()
        print(excel_file)
        #excel_file = request.excel_file_path
        
        # 데이터베이스 파일 경로 처리
        db_file = project_root / request.db_path
        db_file = db_file.resolve()
        
        # 보안 검증: 프로젝트 디렉토리 내부인지 확인
        #if not str(excel_file).startswith(str(project_root.resolve())):
        #    return JSONResponse(status_code=403, content={"error": "Access denied: Excel file must be within project directory"})
        
        if not str(db_file).startswith(str(project_root.resolve())):
            return JSONResponse(status_code=403, content={"error": "Access denied: Database file must be within project directory"})
        
        # Excel 파일 존재 확인
        #if not excel_file.exists():
        #    return JSONResponse(status_code=404, content={"error": f"Excel file not found: {request.excel_file_path}"})
        
        #if not excel_file.is_file():
        #    return JSONResponse(status_code=400, content={"error": f"Not a file: {request.excel_file_path}"})
        
        # Excel 파일 확장자 확인
        #if excel_file.suffix.lower() not in ['.xlsx', '.xls']:
        #    return JSONResponse(status_code=400, content={"error": f"Not an Excel file: {request.excel_file_path}"})
        
        # 데이터베이스 디렉토리 생성 (필요한 경우)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Excel 파일 읽기 (첫 번째 행은 헤더)
        print(excel_file)
        df = pd.read_excel(excel_file)
        
        if df.empty:
            return JSONResponse(status_code=400, content={"error": "Excel file is empty"})
        
        # SQLite 데이터베이스 연결 및 데이터 삽입
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        inserted_count = 0
        failed_count = 0
        
        # 각 행의 데이터를 데이터베이스에 삽입
        for index, row in df.iterrows():
            try:
                # NaN 값을 None으로 변환
                row_data = tuple(None if pd.isna(value) else value for value in row)
                cursor.execute(request.insert_sql, row_data)
                inserted_count += 1
            except Exception as row_error:
                logging.warning(f"Failed to insert row {index + 2}: {str(row_error)}")
                failed_count += 1
        
        # 트랜잭션 커밋
        conn.commit()
        conn.close()
        
        return JSONResponse(content={
            "type": "insert-excel",
            "message": f"Excel data insertion completed. Inserted: {inserted_count}, Failed: {failed_count}",
            "inserted_count": inserted_count,
            "failed_count": failed_count,
            "total_rows": len(df)
        })
        
    except Exception as e:
        logging.error(f"Failed to insert Excel data: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Failed to insert Excel data: {str(e)}"})

@app.post("/save_system_prompt")
async def save_system_prompt(request: SaveSystemPromptRequest) -> JSONResponse:
    """
    시스템 프롬프트를 데이터베이스에 저장
    filename이 이미 존재하면 업데이트, 없으면 새로 삽입
    """
    try:
        # 현재 프로젝트 루트 경로
        project_root = Path(__file__).parent.parent
        db_file = project_root / "resources" / "data.db"
        
        # 데이터베이스 디렉토리 생성 (필요한 경우)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # SQLite 데이터베이스 연결
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        
        # SYSTEM_PROMPT 테이블 생성 (존재하지 않으면)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SYSTEM_PROMPT (
                filename TEXT PRIMARY KEY,
                prompt TEXT NOT NULL
            )
        """)
        
        # UPSERT 로직: INSERT OR REPLACE 사용
        cursor.execute("""
            INSERT OR REPLACE INTO SYSTEM_PROMPT (filename, prompt)
            VALUES (?, ?)
        """, (request.filename, request.prompt))
        
        # 변경 사항 확인
        is_update = cursor.rowcount > 0 and cursor.lastrowid is None
        operation = "updated" if is_update else "inserted"
        
        # 트랜잭션 커밋
        conn.commit()
        conn.close()
        
        return JSONResponse(content={
            "type": "save-system-prompt",
            "message": f"System prompt {operation} successfully for filename: {request.filename}",
            "filename": request.filename,
            "operation": operation
        })
        
    except Exception as e:
        logging.error(f"Failed to save system prompt: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Failed to save system prompt: {str(e)}"})


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080)