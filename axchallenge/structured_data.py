from pathlib import Path
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
import uuid
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
from fastapi import FastAPI, APIRouter, HTTPException, Query
from pydantic import BaseModel
import sqlite3
from typing import List, Optional, Union

# /workspaces/private-devbot (main) $ uvicorn axchallenge.structured_data:app --host 0.0.0.0 --port 8000 --reload

app = FastAPI()

# router = APIRouter()

DATABASE_PATH = "resources/data.db"  # DB 경로 (상황에 맞게 수정 가능)


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
            elif sql.lower().startswith("delete"):
                return {"type": "delete", "message": "DELETE is not allowed."}
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
            cursor.execute("SELECT * FROM table_comments;")
            schemas = []
            for row in cursor.fetchall():
                schemas.append({
                    "table_name": row[0],
                    "table_comment": row[1]
                })

            for table in schemas:
                # 컬럼 정보 조회
                table_name = table["table_name"]
                cursor.execute(
                    f"SELECT * FROM column_comments where table_name=\"{table_name}\";")
                columns_info = cursor.fetchall()

                # table_info 결과: cid, name, type, notnull, dflt_value, pk
                columns = [
                    {
                        "column_name": col[1],
                        "column_comment": col[2]
                    }
                    for col in columns_info
                ]
                table["columns"] = columns

            return {"type": "schema", "message": schemas}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app.mount("/resources", StaticFiles(directory="resources"), name="resources")


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
            for idx, y_column in enumerate(y_column_names):

                sns.lineplot(x=request.x_column_name,
                             y=y_column,
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

            return {"type": "chart", "message": f"https://fantastic-space-potato-r4r4qqjq976fjjp-8000.app.github.dev/{file_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
