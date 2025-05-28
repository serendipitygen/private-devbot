import os
import json
import requests
from urllib.parse import urlparse

# --- API Client ---
class ApiClient:
    def __init__(self, get_config_func, get_upload_config_func, monitoring_daemon=None):
        self.get_config = get_config_func
        self.get_upload_config = get_upload_config_func
        self.session = self._create_session()
        self.current_rag = 'default'
        self.monitoring_daemon = monitoring_daemon

    def _create_session(self):
        return None 

    def _get_base_url(self):
        config = self.get_config()
        return config.get('api_base_url')

    def _make_request_without_proxy(self, method, endpoint, params=None, data=None, files=None, json_data=None, headers=None, timeout=600):
        """모든 API 요청을 처리하는 공통 메서드"""
        base_url = self._get_base_url()
        url = f"{base_url}/{endpoint.lstrip('/')}"
        
        # URL 파싱
        parsed_url = urlparse(url)
        host = parsed_url.hostname

        config = self.get_config()
        ip = config.get('client_ip')

        # 프록시 적용 여부 결정
        bypass_proxy = False
        if host and (host.endswith(ip) or host.endswith('localhost') or host.endswith('127.0.0.1') or host.endswith('portal.vd.sec.samsung.net')):
            bypass_proxy = True

        # 프록시 설정
        proxies = {
            'http': 'http://168.219.61.252:8080',
            'https': 'http://168.219.61.252:8080',
        } if not bypass_proxy else {}

        # SSL 인증 건너뛰기 (Flutter의 badCertificateCallback과 동일)
        verify = False  # 실제 환경에서는 보안을 위해 False 대신 인증서 파일 경로를 사용해야 합니다.

        print(f'[ApiClient] {method.upper()} 요청: {url}')
        if params:
            print(f'[ApiClient] 파라미터: {params}')
        if json_data:
            print(f'[ApiClient] JSON 데이터: {json_data}')
        if headers:
            print(f'[ApiClient] 헤더: {headers}')
        
        try:
            # rag_name 처리 (기존 로직 유지)
            rag_name = self.current_rag
            if rag_name and rag_name != 'default':
                if params is not None:
                    params = dict(params)
                    params['rag_name'] = rag_name
                if json_data is not None:
                    json_data = dict(json_data)
                    json_data['rag_name'] = rag_name
                if data is not None:
                    data = dict(data)
                    if 'rag_name' not in data:
                        data['rag_name'] = rag_name

            # 요청 실행
            response = requests.request(
                method=method,
                url=url,
                params=params,
                data=data,
                files=files,
                json=json_data,
                headers=headers,
                timeout=timeout,
                proxies=proxies,
                verify=verify  # SSL 인증 건너뜀
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

    def _make_request(self, method, endpoint, params=None, data=None, files=None, json_data=None, headers=None, timeout=600):
        """모든 API 요청을 처리하는 공통 메서드"""
        base_url = self._get_base_url()
        url = f"{base_url}/{endpoint.lstrip('/')}"
        
        # TODO: 168.219.61.252 Proxy 에러 대처 필요
        config = self.get_config()
        ip = config.get('client_ip')
        url = url.replace(ip, '127.0.0.1')

        print(f'[ApiClient] {method.upper()} 요청: {url}')
        if params:
            print(f'[ApiClient] 파라미터: {params}')
        if json_data:
            print(f'[ApiClient] JSON 데이터: {json_data}')
        if headers:
            print(f'[ApiClient] 헤더: {headers}')
        
        try:
            # rag_name은 쿼리나 form/json에 함께 보낸다 (우선순위: params -> data -> json)
            rag_name = self.current_rag
            if rag_name and rag_name != 'default':
                # GET 방식 등 URL 파라미터
                if params is not None:
                    params = dict(params)  # copy
                    params['rag_name'] = rag_name
                # POST JSON
                if json_data is not None:
                    json_data = dict(json_data)
                    json_data['rag_name'] = rag_name
                # multipart/form-data
                if data is not None:
                    data = dict(data)
                    if 'rag_name' not in data:
                        data['rag_name'] = rag_name
            
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
        if params is None:
            params = {}
        if 'rag_name' not in params:
            params['rag_name'] = self.current_rag
        print("########################################")
        return self._make_request('get', '/documents', params=params)

    def get_store_info(self):
        """문서 저장소 정보를 가져옵니다."""
        response = self._make_request('get', '/status', params={'rag_name': self.current_rag})
        
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
            # 모니터링 일시 중지
            try:
                self.monitoring_daemon.pause_monitoring()
            except Exception as e:
                print(f"[ApiClient] 모니터링 일시중지 실패: {e}")
            
            # 파일과 파일 경로를 모두 폼 데이터로 전송
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
                data = {'file_path': file_path, 'rag_name': self.current_rag}
                
                result = self._make_request('post', '/upload', files=files, data=data, timeout=600)
                
                # 파일 업로드 성공 시 monitoring_files_ip_port.yaml 파일 업데이트
                if result and not (isinstance(result, dict) and "error" in result):
                    try:
                        from ip_middleware import append_monitoring_file
                        append_monitoring_file(file_path, self.current_rag)
                        print(f"[ApiClient] {os.path.basename(file_path)} yaml 파일에 추가됨")
                    except Exception as e:
                        print(f"[ApiClient] yaml 파일 업데이트 오류: {e}")
                
                return result
        except Exception as e:
            print(f"[ApiClient] 파일 업로드 오류: {e}")
            return {"error": "file_upload_error", "details": str(e)}
        finally:
            # 업로드 완료 후 10초 뒤 모니터링 재개
            try:
                self.monitoring_daemon.resume_monitoring(10)
            except Exception as e:
                print(f"[ApiClient] 모니터링 재개 실패: {e}")

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
                        append_monitoring_files(successful_files, self.current_rag)
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
        result = self._make_request('delete', '/documents', json_data=data, headers=headers, params={'rag_name': self.current_rag})
        
        # 문서 삭제 성공 시 monitoring_files_ip_port.yaml 파일 업데이트
        if result and not (isinstance(result, dict) and "error" in result):
            try:
                from ip_middleware import delete_monitoring_files
                delete_monitoring_files(file_paths, self.current_rag)
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
        result = self._make_request('delete', '/documents/all', headers=headers, params={'rag_name': self.current_rag})
        
        # 모든 문서 삭제 시 monitoring_files_ip_port.yaml 파일도 초기화
        try:
            from ip_middleware import clear_monitoring_files
            clear_monitoring_files(self.current_rag)
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

    # --------------------------------------------------
    # RAG 관리
    def set_rag(self, rag_name: str | None):
        self.current_rag = rag_name or 'default'

    def get_rag(self) -> str:
        return self.current_rag

    # ----------------------------- SEARCH -----------------------------
    def search(self, query: str, k: int = 5):
        """질문(query)으로 검색 결과 반환"""
        json_data = {
            "query": query,
            "k": k,
            "rag_name": self.current_rag
        }
        return self._make_request('post', '/search', json_data=json_data)