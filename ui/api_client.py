import os
import json
import requests

# --- API Client ---
class ApiClient:
    def __init__(self, get_config_func, get_upload_config_func):
        self.get_config = get_config_func
        self.get_upload_config = get_upload_config_func
        self.session = self._create_session()

    def _create_session(self):
        return None 

    def _get_base_url(self):
        config = self.get_config()
        return config.get('api_base_url', 'http://localhost:8125').rstrip('/')

    def _make_request(self, method, endpoint, params=None, data=None, files=None, json_data=None, headers=None, timeout=10):
        """모든 API 요청을 처리하는 공통 메서드"""
        base_url = self._get_base_url()
        url = f"{base_url}/{endpoint.lstrip('/')}"
        
        print(f'[ApiClient] {method.upper()} 요청: {url}')
        if params:
            print(f'[ApiClient] 파라미터: {params}')
        if json_data:
            print(f'[ApiClient] JSON 데이터: {json_data}')
        if headers:
            print(f'[ApiClient] 헤더: {headers}')
        
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                data=data,
                files=files,
                json=json_data,
                headers=headers,
                timeout=timeout
            )
            print(f'[ApiClient] 응답 상태 코드: {response.status_code}')
            
            response.raise_for_status()
            
            # JSON 응답인 경우 파싱
            if response.text and response.headers.get('content-type', '').startswith('application/json'):
                return response.json()
            return response.text or None
            
        except requests.exceptions.HTTPError as e:
            print(f'[ApiClient] HTTP 오류: {e}')
            error_text = e.response.text[:200] if e.response and e.response.text else "N/A"
            return {"error": "http_error", "status_code": e.response.status_code if e.response else 0, "details": error_text}
            
        except requests.exceptions.RequestException as e:
            print(f'[ApiClient] 요청 오류: {e}')
            return {"error": "request_exception", "details": str(e)}
            
        except json.JSONDecodeError as e:
            print(f'[ApiClient] JSON 파싱 오류: {e}')
            return {"error": "json_decode_error", "details": str(e)}
            
        except Exception as e:
            print(f'[ApiClient] 예상치 못한 오류: {type(e).__name__} - {e}')
            return {"error": "unexpected_error", "details": str(e)}

    def get_documents(self, params=None):
        """문서 목록을 가져옵니다."""
        return self._make_request('get', '/documents', params=params)

    def get_store_info(self):
        """문서 저장소 정보를 가져옵니다."""
        response = self._make_request('get', '/status')
        
        # status API의 응답에서 필요한 값만 추출하여 변환
        if isinstance(response, dict):
            document_count = response.get("document_count", 0)
            
            # index_size_mb를 db_size_mb로 사용
            db_size_mb = response.get("index_size_mb", 0)
            
            # index_path를 vector_store_path로 사용
            vector_store_path = response.get("index_path", "N/A")
            
            print(f"[ApiClient] status 응답 받음: 문서 {document_count}개, DB 크기 {db_size_mb}MB, 경로 {vector_store_path}")
            
            return {
                "document_count": document_count,
                "db_size_mb": db_size_mb,
                "vector_store_path": vector_store_path
            }
        
        print(f"[ApiClient] status 응답이 유효하지 않음: {response}")
        
        return {
            "document_count": 0,
            "db_size_mb": 0,
            "vector_store_path": "N/A"
        }
    
    def upload_file(self, file_path):
        """파일을 업로드합니다."""
        if not os.path.exists(file_path):
            return {"error": "file_not_found", "details": f"파일을 찾을 수 없습니다: {file_path}"}
            
        try:
            # 파일과 파일 경로를 모두 폼 데이터로 전송
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
                data = {'file_path': file_path}  # 서버에서 요구하는 file_path 매개변수 추가
                
                result = self._make_request('post', '/upload', files=files, data=data, timeout=60)
                
                # 파일 업로드 성공 시 monitoring_files_ip_port.yaml 파일 업데이트
                if result and not (isinstance(result, dict) and "error" in result):
                    try:
                        from ip_middleware import append_monitoring_file
                        append_monitoring_file(file_path)
                        print(f"[ApiClient] {os.path.basename(file_path)} yaml 파일에 추가됨")
                    except Exception as e:
                        print(f"[ApiClient] yaml 파일 업데이트 오류: {e}")
                
                return result
        except Exception as e:
            print(f"[ApiClient] 파일 업로드 오류: {e}")
            return {"error": "file_upload_error", "details": str(e)}
    
    def upload_folder(self, folder_path):
        """폴더 내 모든 파일을 업로드합니다."""
        if not os.path.isdir(folder_path):
            return {"error": "folder_not_found", "details": f"폴더를 찾을 수 없습니다: {folder_path}"}
        
        try:
            # 폴더에서 파일 목록 가져오기
            files_to_upload = []
            file_paths = []
            
            for root, _, filenames in os.walk(folder_path):
                for filename in filenames:
                    # 숨김 파일 및 시스템 파일 제외
                    if filename.startswith('.') or filename.startswith('~$'):
                        continue
                        
                    full_path = os.path.join(root, filename)
                    files_to_upload.append(full_path)
                    file_paths.append({
                        'filename': filename,
                        'file_path': full_path
                    })
            
            if not files_to_upload:
                return {"status": "warning", "message": "업로드할 파일이 없습니다."}
                
            # 각 파일을 개별적으로 업로드
            results = []
            success_count = 0
            
            for file_path in files_to_upload:
                result = self.upload_file(file_path)
                results.append(result)
                if not isinstance(result, dict) or "error" not in result:
                    success_count += 1
            
            # 폴더 업로드 완료 후 monitoring_files_ip_port.yaml 파일 업데이트
            # (개별 파일은 upload_file에서 처리되지만, 여기서도 확인)
            if success_count > 0:
                try:
                    from ip_middleware import append_monitoring_files
                    # 성공한 파일만 yaml에 추가
                    successful_files = []
                    for i, result in enumerate(results):
                        if not isinstance(result, dict) or "error" not in result:
                            successful_files.append(files_to_upload[i])
                    if successful_files:
                        append_monitoring_files(successful_files)
                        print(f"[ApiClient] {len(successful_files)}개 파일 yaml에 추가됨")
                except Exception as e:
                    print(f"[ApiClient] yaml 파일 업데이트 오류: {e}")
            
            return {
                "status": "success" if success_count == len(files_to_upload) else "partial",
                "message": f"{len(files_to_upload)}개 파일 중 {success_count}개 업로드 성공",
                "success_count": success_count,
                "total_count": len(files_to_upload),
                "results": results
            }
            
        except Exception as e:
            print(f"[ApiClient] 폴더 업로드 오류: {e}")
            return {"error": "folder_upload_error", "details": str(e)}
    
    def delete_documents(self, file_paths):
        """하나 이상의 문서를 삭제합니다."""
        # private_devbot_admin과 유사하게 구현
        # JSON 본문으로 file_paths 배열을 전송
        headers = {
            'Content-Type': 'application/json',
            'X-Real-IP': '127.0.0.1'  # 로카 IP 주소를 기본으로 사용
        }
        
        data = {
            "file_paths": file_paths
        }
        
        print(f"[ApiClient] 문서 삭제 요청: {file_paths}")
        result = self._make_request('delete', '/documents', json_data=data, headers=headers)
        
        # 문서 삭제 성공 시 monitoring_files_ip_port.yaml 파일 업데이트
        if result and not (isinstance(result, dict) and "error" in result):
            try:
                from ip_middleware import delete_monitoring_files
                delete_monitoring_files(file_paths)
            except Exception as e:
                print(f"[ApiClient] yaml 파일 업데이트 오류: {e}")
                
        return result
    
    def delete_document(self, file_path):
        """하나의 문서를 삭제합니다."""
        # delete_documents 함수를 통해 단일 문서 삭제
        result = self.delete_documents([file_path])
        
        # yaml 파일 업데이트는 delete_documents에서 처리되므로 여기서는 필요 없음
        return result
    
    def delete_all_documents(self):
        """모든 문서를 삭제합니다."""
        headers = {
            'X-Real-IP': '127.0.0.1'  # 로카 IP 주소를 기본으로 사용
        }
        
        print(f"[ApiClient] 모든 문서 삭제 요청")
        result = self._make_request('delete', '/documents/all', headers=headers)
        
        # 모든 문서 삭제 시 monitoring_files_ip_port.yaml 파일도 초기화
        try:
            from ip_middleware import clear_monitoring_files
            clear_monitoring_files()
        except Exception as e:
            print(f"[ApiClient] yaml 파일 초기화 오류: {e}")
            
        return result
    
    def check_server_status(self):
        """서버 상태를 확인합니다."""
        try:
            result = self._make_request('get', '/health', timeout=2)
            if isinstance(result, dict) and 'error' in result:
                return False
            return True
        except Exception:
            return False