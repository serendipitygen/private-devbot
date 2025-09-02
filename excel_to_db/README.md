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

### POST /analyze-excel
Excel 파일 데이터를 받아서 첫 10개 행을 반환합니다.

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
2. HTTP Request 노드를 사용해서 이 서버의 `/analyze-excel` 엔드포인트로 데이터를 전송합니다
3. n8n에서 바이너리 데이터를 base64로 인코딩해서 전송해야 합니다