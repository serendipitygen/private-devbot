from datetime import datetime
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional

import base64
import io
import logging
import matplotlib.pyplot as plt
import os
import pandas as pd
import seaborn as sns
import sqlite3
import tempfile
import uuid

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

app.mount("/resources", StaticFiles(directory="resources"), name="resources")


# --- Paths & DB --------------------------------------------------------------
# 프로젝트 루트와 DB 경로를 한 곳에서만 정의/사용하도록 통일
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DATABASE_PATH = str((PROJECT_ROOT / "resources" / "data.db").resolve())


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


@app.post("/read_excel_description")
async def read_excel_description(request: ExcelDescriptionRequest) -> JSONResponse:
    """
    docs/excel/ 디렉토리의 마크다운 파일을 읽어 내용 반환
    파일명만 제공하면 docs/excel/ 아래에서 찾고, 전체 경로 제공도 가능
    """
    try:
        # 현재 프로젝트 루트 경로
        excel_docs_dir = PROJECT_ROOT / "docs" / "excel"

        # 파일명만 제공된 경우 기본 경로(docs/excel/) 사용
        if "/" not in request.description_file_path and "\\" not in request.description_file_path:
            target_file = excel_docs_dir / request.description_file_path
        else:
            # 전체 경로 제공된 경우
            target_file = PROJECT_ROOT / request.description_file_path

        # 경로 정규화 및 보안 검증
        target_file = target_file.resolve()
        PROJECT_ROOT = PROJECT_ROOT.resolve()

        # 현재 프로젝트 디렉토리 내부인지 확인
        if not str(target_file).startswith(str(PROJECT_ROOT)):
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
        logging.error(
            f"Failed to read file {request.description_file_path}: {str(e)}")
        return JSONResponse(status_code=500, content={"error": f"Failed to read file: {str(e)}"})

    return JSONResponse(content={"type": "read-excel-description", "message": text})


@app.post("/insert_excel")
async def insert_excel(request: InsertExcelRequest) -> JSONResponse:
    """
    Excel 파일을 읽어서 SQLite 데이터베이스에 각 행의 데이터를 삽입
    첫 번째 행은 헤더로 간주하고 두 번째 행부터 데이터로 처리
    """
    try:
        # Excel 파일 경로 처리
        excel_file = PROJECT_ROOT / request.excel_file_path
        excel_file = excel_file.resolve()
        print(excel_file)
        # excel_file = request.excel_file_path

        # 데이터베이스 파일 경로 처리
        db_file = PROJECT_ROOT / request.db_path
        db_file = db_file.resolve()

        # 보안 검증: 프로젝트 디렉토리 내부인지 확인
        # if not str(excel_file).startswith(str(project_root.resolve())):
        #    return JSONResponse(status_code=403, content={"error": "Access denied: Excel file must be within project directory"})

        if not str(db_file).startswith(str(PROJECT_ROOT.resolve())):
            return JSONResponse(status_code=403, content={"error": "Access denied: Database file must be within project directory"})

        # Excel 파일 존재 확인
        # if not excel_file.exists():
        #    return JSONResponse(status_code=404, content={"error": f"Excel file not found: {request.excel_file_path}"})

        # if not excel_file.is_file():
        #    return JSONResponse(status_code=400, content={"error": f"Not a file: {request.excel_file_path}"})

        # Excel 파일 확장자 확인
        # if excel_file.suffix.lower() not in ['.xlsx', '.xls']:
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
                row_data = tuple(None if pd.isna(
                    value) else value for value in row)
                cursor.execute(request.insert_sql, row_data)
                inserted_count += 1
            except Exception as row_error:
                logging.warning(
                    f"Failed to insert row {index + 2}: {str(row_error)}")
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
        db_file = PROJECT_ROOT / "resources" / "data.db"

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


@app.post('/excel-modification')
async def excel_modification(request: Request):
    try:
        # JSON 데이터 파싱
        data = await request.json()
        logging.info(f"Received JSON data: {data}")

        # 필수 파라미터 추출
        file_path = data.get('file_path')
        start_value_row = data.get('start_value_row')
        column_names = data.get('column_names')

        if not file_path or start_value_row is None or not column_names:
            return JSONResponse(content={'error': 'Missing required parameters: file_path, start_value_row, column_names'}, status_code=400)

        # 파일 존재 확인
        if not os.path.exists(file_path):
            return JSONResponse(content={'error': f'File not found: {file_path}'}, status_code=404)

        # Excel 파일 로드
        df = pd.read_excel(file_path, header=None)
        logging.info(
            f"Loaded Excel file with {len(df)} rows and {len(df.columns)} columns")

        # start_value_row가 n이면 0~n-1번 row를 삭제
        if start_value_row > 0:
            df = df.iloc[start_value_row:].reset_index(drop=True)
            logging.info(f"Removed first {start_value_row} rows")

        # column_names 배열을 0번 row로 추가
        column_df = pd.DataFrame([column_names])

        # 기존 데이터와 결합 (column_names가 0번 row, 기존 데이터가 1번 row부터)
        modified_df = pd.concat([column_df, df], ignore_index=True)
        logging.info(
            f"Added column names as header row, final DataFrame has {len(modified_df)} rows")

        # 처리 확인용: 첫 3개 row 출력
        first_3_rows = modified_df.head(3).to_dict('records')
        logging.info(f"First 3 rows of modified DataFrame: {first_3_rows}")

        excel_path = PROJECT_ROOT / "docs" / "excel"
        print(excel_path)

        # 임시 위치에 수정된 Excel 파일 저장
        # temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = os.path.splitext(os.path.basename(file_path))[0]
        modified_filename = f"{original_name}_modified_{timestamp}.xlsx"
        # modified_file_path = os.path.join(temp_dir, modified_filename)
        modified_file_path = os.path.join(excel_path, modified_filename)

        # Excel 파일로 저장 (헤더 없이)
        modified_df.to_excel(modified_file_path, index=False, header=False)
        logging.info(f"Modified Excel file saved to: {modified_file_path}")

        # 첫 10개 행을 리턴용으로 준비
        first_10_rows = modified_df.head(10).where(
            pd.notna(modified_df.head(10)), None).to_dict('records')

        return JSONResponse(content={
            'status': 'success',
            'original_file_path': file_path,
            'modified_file_path': modified_file_path,
            'removed_rows': start_value_row,
            'added_column_names': column_names,
            'final_row_count': len(modified_df),
            'first_10_rows': first_10_rows
        })

    except Exception as e:
        logging.exception("Error processing Excel modification")
        return JSONResponse(content={'error': str(e)}, status_code=500)


@app.post('/excel-head')
async def excel_head(request: Request, excel: UploadFile = File(None)):
    try:
        file_content = None
        filename = 'unknown.xlsx'

        # multipart/form-data로 전송되는 경우 (UploadFile)
        if excel:
            file_content = await excel.read()
            filename = excel.filename or 'uploaded.xlsx'
            print(f"Received filename: {filename}")
            logging.info(
                f"File loaded from multipart upload, size: {len(file_content)} bytes")

        else:
            # JSON 형태로 전송되는 경우
            content_type = request.headers.get('content-type', '')
            logging.info(f"Request Content-Type: {content_type}")

            # n8n에서 직접 바이너리 데이터로 전송하는 경우
            if 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in content_type:
                file_content = await request.body()
                logging.info(
                    f"Received direct binary data, size: {len(file_content)} bytes")
                # 파일명은 헤더에서 추출 시도
                filename = request.headers.get('X-Filename', 'uploaded.xlsx')

            # JSON 형태로 전송되는 경우
            elif 'application/json' in content_type:
                try:
                    data = await request.json()
                    logging.info(
                        f"Received JSON data keys: {list(data.keys()) if data else 'None'}")

                    # n8n Buffer 형태 처리 - 최상위에 data가 있는 경우
                    if 'data' in data and isinstance(data['data'], list):
                        # Buffer 형태: {"type": "Buffer", "data": [80, 75, 3, 4, ...]}
                        buffer_data = data['data']
                        file_content = bytes(buffer_data)
                        logging.info(
                            f"File loaded from top-level Buffer array, size: {len(file_content)} bytes")
                        filename = data.get('filename', 'uploaded.xlsx')

                    elif 'excel' in data:
                        excel_data = data['excel']
                        filename = excel_data.get('filename', 'unknown.xlsx')

                        # Buffer 형태 처리
                        if 'data' in excel_data and isinstance(excel_data['data'], list):
                            file_content = bytes(excel_data['data'])
                            logging.info(
                                "File loaded from Buffer in excel.data field")
                        # base64 형태 처리
                        elif 'data' in excel_data:
                            try:
                                file_content = base64.b64decode(
                                    excel_data['data'])
                                logging.info(
                                    "File loaded from base64 in excel.data field")
                            except Exception as e:
                                logging.error(
                                    f"Failed to decode from 'data' field: {e}")
                        elif 'content' in excel_data:
                            try:
                                file_content = base64.b64decode(
                                    excel_data['content'])
                                logging.info(
                                    "File loaded from 'content' field")
                            except Exception as e:
                                logging.error(
                                    f"Failed to decode from 'content' field: {e}")
                    else:
                        # 전체 데이터가 배열인 경우 (최상위 레벨)
                        if isinstance(data, list):
                            file_content = bytes(data)
                            logging.info(
                                f"File loaded from top-level array, size: {len(file_content)} bytes")

                except Exception as e:
                    logging.error(f"Error parsing JSON: {e}")
                    return JSONResponse(content={'error': f'Error parsing JSON: {str(e)}'}, status_code=400)

            else:
                logging.error(f"Unsupported content type: {content_type}")
                return JSONResponse(content={'error': f'Unsupported content type: {content_type}'}, status_code=415)

        if file_content is None or len(file_content) == 0:
            return JSONResponse(content={'error': 'No file content received'}, status_code=400)

        # 파일을 임시 디렉토리에 저장
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(filename)[0]
        saved_filename = f"{base_name}_{timestamp}.xlsx"
        saved_file_path = os.path.join(temp_dir, saved_filename)

        with open(saved_file_path, 'wb') as f:
            f.write(file_content)

        print(f"File saved to: {saved_file_path}")

        # Excel 파일을 pandas DataFrame으로 로드 (첫 번째 행을 데이터로 유지)
        df = pd.read_excel(io.BytesIO(file_content), header=None)

        # 첫 10개 행 추출
        first_10_rows = df.head(10)

        # NaN 값을 처리하여 JSON 직렬화 가능하게 만들기
        first_10_rows = first_10_rows.where(pd.notna(first_10_rows), None)
        result_data = first_10_rows.to_dict('records')

        # 컬럼 정보도 함께 반환 (0부터 시작하는 인덱스 사용)
        columns = list(range(len(df.columns)))
        total_rows = len(df)

        response = {
            'status': 'success',
            'file_name': filename,
            'file_path': saved_file_path,
            'columns': columns,
            'first_10_rows': result_data
        }

        logging.info(f"Successfully processed Excel file: {filename}")
        logging.info(f"Total rows: {total_rows}, Columns: {len(columns)}")

        return JSONResponse(content=response)

    except Exception as e:
        logging.exception("Error processing Excel file")
        return JSONResponse(content={'error': str(e)}, status_code=500)


@app.get('/health')
async def health_check():
    return JSONResponse(content={'status': 'healthy'})


class SQLRequest(BaseModel):
    sql: str


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


@app.post("/execute-sql")
def execute_sql(request: SQLRequest):
    sql = request.sql.strip()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            if sql.lower().startswith("select"):
                cursor.execute(sql)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]
                return {"type": "select", "message": results}
            #elif sql.lower().startswith("delete"):
            #    return {"type": "delete", "message": "DELETE is not allowed."}
            else:
                cursor.execute(sql)
                conn.commit()
                return {"type": "command", "message": "SQL executed successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/schema")
def get_schema():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # 테이블 코멘트 조회
            cursor.execute("SELECT * FROM system_prompt;")
            schemas = []
            for row in cursor.fetchall():
                schemas.append({
                    "filename": row[0],
                    "prompt": row[1]
                })
            return {"type": "schema", "message": schemas}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ChartRequest(BaseModel):
    sql: str
    x_column_name: str
    y_column_names: str
    title: str


@app.post("/chart")
def make_chart(request: ChartRequest):
    try:
        y_column_names = request.y_column_names.split(",")

        with get_connection() as conn:
            df = pd.read_sql_query(request.sql, conn)
            print(df)

            # 3. 차트 스타일 적용
            # sns.set_theme(style="whitegrid", font="NanumGothic")
            plt.figure(figsize=(8, 5))

            # 4. 라인 차트 그리기
            colors = ["#4EA6E1", "#2EC146", "#AD2EC1", "#C1422E"]
            for idx, y_column in enumerate(y_column_names[:4]):
                print(y_column)
                sns.lineplot(x=request.x_column_name,
                             y=y_column.strip(),
                             data=df, marker="o",
                             linewidth=2.5,
                             label=y_column, color=colors[idx])

            plt.title(request.title, fontsize=16, weight="bold", pad=15)
            plt.xlabel(request.x_column_name, fontsize=12)
            plt.legend(fontsize=11, frameon=True,
                       shadow=True, loc="upper left")
            plt.tight_layout()

            # 5. 이미지 저장
            file_path = f"resources/{uuid.uuid4()}.png"
            plt.savefig(file_path, dpi=300, bbox_inches="tight")
            plt.close()

            return {"type": "chart", "message": f"https://fantastic-space-potato-r4r4qqjq976fjjp-8080.app.github.dev/{file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ReportRequest(BaseModel):
    html: str

@app.post("/report-html")
def save_report_html(request: ReportRequest):
    file_path = f"resources/report/{uuid.uuid4()}.html"
    report_path = PROJECT_ROOT / file_path
    report_path = report_path.resolve()
    with open(report_path, "w") as f:
        f.write(request.html)
    return {"type": "report", "message": f"https://fantastic-space-potato-r4r4qqjq976fjjp-8080.app.github.dev/{file_path}"}

# --- dirty excel 처리용 (이미지, 차트 첨부 시)


@app.get("/list-files")
def list_files(subdir: str = Query("", description="하위 폴더 경로 (BASE_DIR 기준)")) -> JSONResponse:
    """
    BASE_DIR/subdir 밑에 있는 파일들을 JSON으로 리턴합니다.
    """
    target_path = Path("resources/dirty_excel") / subdir

    if not target_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": f"Path not found: {target_path}"}
        )

    if not target_path.is_dir():
        return JSONResponse(
            status_code=400,
            content={"error": f"Not a directory: {target_path}"}
        )

    files: List[dict] = []
    for f in target_path.iterdir():
        files.append({
            "name": f.name,
            "is_dir": f.is_dir(),
            "size": f.stat().st_size if f.is_file() else None,
            "modified": f.stat().st_mtime
        })

    return JSONResponse(content={"type": "list-files", "message": {"path": str(target_path), "files": files}})


@app.get("/read-file")
def read_file(
    filepath: str = Query(...,
                          description="BASE_DIR 기준 상대 경로, 예: subdir/example.txt")
) -> JSONResponse:
    """
    BASE_DIR 밑의 특정 파일을 읽어 내용 반환
    """
    target_file = Path("resources/dirty_excel") / filepath

    if not target_file.exists():
        return JSONResponse(status_code=404, content={"error": f"File not found: {target_file}"})
    if not target_file.is_file():
        return JSONResponse(status_code=400, content={"error": f"Not a file: {target_file}"})

    try:
        text = target_file.read_text(encoding="utf-8")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to read file: {str(e)}"})

    return JSONResponse(content={"type": "read-file", "message": text})


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080)
