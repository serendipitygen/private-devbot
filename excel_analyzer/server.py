from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import pandas as pd
import io
import base64
import logging
import json

app = FastAPI()
logging.basicConfig(level=logging.INFO)

@app.post('/analyze-excel')
async def analyze_excel(request: Request, excel: UploadFile = File(None)):
    try:
        file_content = None
        filename = 'unknown.xlsx'
        
        # multipart/form-data로 전송되는 경우 (UploadFile)
        if excel:
            file_content = await excel.read()
            filename = excel.filename or 'uploaded.xlsx'
            logging.info(f"File loaded from multipart upload, size: {len(file_content)} bytes")
        
        else:
            # JSON 형태로 전송되는 경우
            content_type = request.headers.get('content-type', '')
            logging.info(f"Request Content-Type: {content_type}")
            
            # n8n에서 직접 바이너리 데이터로 전송하는 경우
            if 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in content_type:
                file_content = await request.body()
                logging.info(f"Received direct binary data, size: {len(file_content)} bytes")
                # 파일명은 헤더에서 추출 시도
                filename = request.headers.get('X-Filename', 'uploaded.xlsx')
            
            # JSON 형태로 전송되는 경우
            elif 'application/json' in content_type:
                try:
                    data = await request.json()
                    logging.info(f"Received JSON data keys: {list(data.keys()) if data else 'None'}")
                    
                    # n8n Buffer 형태 처리 - 최상위에 data가 있는 경우
                    if 'data' in data and isinstance(data['data'], list):
                        # Buffer 형태: {"type": "Buffer", "data": [80, 75, 3, 4, ...]}
                        buffer_data = data['data']
                        file_content = bytes(buffer_data)
                        logging.info(f"File loaded from top-level Buffer array, size: {len(file_content)} bytes")
                        filename = data.get('filename', 'uploaded.xlsx')
                    
                    elif 'excel' in data:
                        excel_data = data['excel']
                        filename = excel_data.get('filename', 'unknown.xlsx')
                        
                        # Buffer 형태 처리
                        if 'data' in excel_data and isinstance(excel_data['data'], list):
                            file_content = bytes(excel_data['data'])
                            logging.info("File loaded from Buffer in excel.data field")
                        # base64 형태 처리
                        elif 'data' in excel_data:
                            try:
                                file_content = base64.b64decode(excel_data['data'])
                                logging.info("File loaded from base64 in excel.data field")
                            except Exception as e:
                                logging.error(f"Failed to decode from 'data' field: {e}")
                        elif 'content' in excel_data:
                            try:
                                file_content = base64.b64decode(excel_data['content'])
                                logging.info("File loaded from 'content' field")
                            except Exception as e:
                                logging.error(f"Failed to decode from 'content' field: {e}")
                    else:
                        # 전체 데이터가 배열인 경우 (최상위 레벨)
                        if isinstance(data, list):
                            file_content = bytes(data)
                            logging.info(f"File loaded from top-level array, size: {len(file_content)} bytes")
                    
                except Exception as e:
                    logging.error(f"Error parsing JSON: {e}")
                    return JSONResponse(content={'error': f'Error parsing JSON: {str(e)}'}, status_code=400)
            
            else:
                logging.error(f"Unsupported content type: {content_type}")
                return JSONResponse(content={'error': f'Unsupported content type: {content_type}'}, status_code=415)
        
        if file_content is None or len(file_content) == 0:
            return JSONResponse(content={'error': 'No file content received'}, status_code=400)
        
        # Excel 파일을 pandas DataFrame으로 로드
        df = pd.read_excel(io.BytesIO(file_content))
        
        # 첫 10개 행 추출
        first_10_rows = df.head(10)
        
        # NaN 값을 처리하여 JSON 직렬화 가능하게 만들기
        import numpy as np
        first_10_rows = first_10_rows.where(pd.notna(first_10_rows), None)
        result_data = first_10_rows.to_dict('records')
        
        # 컬럼 정보도 함께 반환
        columns = df.columns.tolist()
        total_rows = len(df)
        
        response = {
            'status': 'success',
            'columns': columns,
            'first_10_rows': result_data
        }
        
        logging.info(f"Successfully processed Excel file: {filename}")
        logging.info(f"Total rows: {total_rows}, Columns: {len(columns)}")
        logging.info(json.dumps(response, ensure_ascii=False))
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logging.exception("Error processing Excel file")
        return JSONResponse(content={'error': str(e)}, status_code=500)

@app.get('/health')
async def health_check():
    return JSONResponse(content={'status': 'healthy'})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)