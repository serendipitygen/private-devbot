from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import pandas as pd
import io
import base64
import logging
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

app = FastAPI()
logging.basicConfig(level=logging.INFO)

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
        logging.info(f"Loaded Excel file with {len(df)} rows and {len(df.columns)} columns")
        
        # start_value_row가 n이면 0~n-1번 row를 삭제
        if start_value_row > 0:
            df = df.iloc[start_value_row:].reset_index(drop=True)
            logging.info(f"Removed first {start_value_row} rows")
        
        # column_names 배열을 0번 row로 추가
        column_df = pd.DataFrame([column_names])
        
        # 기존 데이터와 결합 (column_names가 0번 row, 기존 데이터가 1번 row부터)
        modified_df = pd.concat([column_df, df], ignore_index=True)
        logging.info(f"Added column names as header row, final DataFrame has {len(modified_df)} rows")
        
        # 처리 확인용: 첫 3개 row 출력
        first_3_rows = modified_df.head(3).to_dict('records')
        logging.info(f"First 3 rows of modified DataFrame: {first_3_rows}")
        
        
        project_root = Path(__file__).parent.parent / "docs" / "excel"
        print(project_root)

        # 임시 위치에 수정된 Excel 파일 저장
        #temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = os.path.splitext(os.path.basename(file_path))[0]
        modified_filename = f"{original_name}_modified_{timestamp}.xlsx"
        #modified_file_path = os.path.join(temp_dir, modified_filename)
        modified_file_path = os.path.join(project_root, modified_filename)
        
        # Excel 파일로 저장 (헤더 없이)
        modified_df.to_excel(modified_file_path, index=False, header=False)
        logging.info(f"Modified Excel file saved to: {modified_file_path}")
        
        # 첫 10개 행을 리턴용으로 준비
        first_10_rows = modified_df.head(10).where(pd.notna(modified_df.head(10)), None).to_dict('records')
        
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

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)