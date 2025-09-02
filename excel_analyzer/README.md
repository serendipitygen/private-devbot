# Excel Analyzer Server

n8n form 노드로부터 Excel 파일을 받아서 분석하는 Python Flask 서버입니다.

## 설치 및 실행

```bash
cd excel_analyzer
pip install -r requirements.txt
python server.py
```

서버는 `http://localhost:5000`에서 실행됩니다.

## API 엔드포인트

### POST /excel-head
Excel 파일 데이터를 받아서 첫 10개 행을 반환합니다.

### POST /excel-modification
Excel 파일의 헤더 행을 수정하고 불필요한 상단 행들을 제거합니다.

**기능:**
- 지정한 행 수만큼 상단 행들을 삭제
- 새로운 컬럼명들을 0번 행으로 추가
- 수정된 파일을 임시 디렉토리에 저장
- 수정된 파일의 첫 10개 행을 반환

**요청 파라미터:**
- `file_path`: 수정할 Excel 파일의 경로
- `start_value_row`: 삭제할 상단 행의 개수 (예: 3이면 0~2행 삭제)
- `column_names`: 새로운 컬럼명 배열

**요청 예시:**
```json
{
  "file_path": "/path/to/excel/file.xlsx",
  "start_value_row": 3,
  "column_names": ["날짜", "목표", "실적", "달성률"]
}
```

**응답 예시:**
```json
{
  "status": "success",
  "original_file_path": "/path/to/excel/file.xlsx",
  "modified_file_path": "/tmp/file_modified_20240902_143022.xlsx",
  "removed_rows": 3,
  "added_column_names": ["날짜", "목표", "실적", "달성률"],
  "final_row_count": 97,
  "first_10_rows": [
    {"날짜": "2024-01", "목표": 100, "실적": 95, "달성률": 95},
    ...
  ]
}
```

**요청 예시:**
```json
{
  "excel": {
    "filename": "example.xlsx",
    "data": "base64_encoded_file_content"
  }
}
```

**응답 예시:**
```json
{
  "status": "success",
  "filename": "example.xlsx",
  "total_rows": 100,
  "columns": ["Column1", "Column2", "Column3"],
  "first_10_rows": [
    {"Column1": "value1", "Column2": "value2"},
    ...
  ]
}
```

### GET /health
서버 상태 확인

## n8n 설정

1. Form 노드에서 Excel 파일을 업로드 받습니다
2. HTTP Request 노드를 사용해서 이 서버의 `/excel-head` 엔드포인트로 데이터를 전송합니다
3. n8n에서 바이너리 데이터를 base64로 인코딩해서 전송해야 합니다