import os
import time
import threading
import yaml
from datetime import datetime
import traceback
from typing import Dict, Optional
from ip_middleware import get_local_ips
from collections import defaultdict
from ui.config_util import load_json_config, get_datastore_port, save_json_config
import fnmatch
from logger_util import monitoring_logger

class MonitoringDaemon:
    def __init__(self, main_frame_ref):
        self.running = False
        self.monitor_thread = None
        self.need_stop_monitoring = False
        self.main_frame_ref = main_frame_ref
     
        # 파일 변경 모니터링 결과 저장
        self.monitoring_result = {
            "start_time": None,  # 시작 시간
            "last_check_time": None,  # 마지막 검사 시간
            "run_duration": "0시간 0분 0초",  # 실행 시간
            "added_files": [],
            "modified_files": [],
            "deleted_files": []
        }
        # 파일 모니터링을 위한 상태 저장
        self.previous_file_paths = set()
        self.init_previous_file_paths()
        self.last_check_timestamp = datetime.now()
        # End of initialization block to avoid executing duplicated code below
        return


        """이전 모니터링 주기 대비 변경사항 비교를 위해 초기 파일 경로 집합을 생성합니다.
        폴더 모니터링을 지원하므로, yaml 내 folders 항목까지 재귀 탐색해 포함합니다."""
        # 이전 파일 목록 초기화 (새로 시작할 때만)
        # self.previous_file_paths = set()
        
        # # 모니터링 시작 전 현재 파일 목록 로드
        # try:
        #     files = []
        #     store_path = os.path.join(os.path.dirname(__file__), 'store')
        #     for fname in os.listdir(store_path):
        #         if fnmatch.fnmatch(fname, 'monitoring_files_*_*.yaml'):
        #             try:
        #                 rag_part = fname.split('_')[2] if len(fname.split('_')) > 2 else None
        #                 info = self.load_monitoring_info(rag_part)
        #                 files.extend(info.get('files', []))
        #             except Exception as e:
        #                 monitoring_logger.exception(f"[모니터링] {fname} 로드 오류: {e}")
        #             # 중복 제거 후 집합화
        #     self.previous_file_paths = set(f['path'] for f in files if 'path' in f)
        #         monitoring_logger.info(f"[모니터링] 초기 파일 목록 로드: {len(self.previous_file_paths)}개 파일")
        # except Exception as e:
        #     monitoring_logger.exception(f"[모니터링] 초기 파일 목록 로드 실패: {e}")
        #     traceback.print_exc()  # 상세 오류 정보 출력

    def start(self):
        """모니터링 데몬을 시작합니다."""
        if self.running:
            monitoring_logger.warning("[모니터링] 이미 실행 중이므로 중복 시작 요청 무시")
            return

        monitoring_logger.info(f"[모니터링] 데몬 시작됨: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.running = True
        
        # 결과 초기화
        start_time = datetime.now()
        self.monitoring_result = {
            "start_time": start_time,
            "last_check_time": start_time,
            "run_duration": "0시간 0분 0초",
            "added_files": [],
            "modified_files": [],
            "deleted_files": []
        }
        
        monitoring_logger.info(f"[모니터링] 모니터링 시작됨: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        # 시작 즉시 파일 확인
        self._check_and_upload_files()
        
    def stop(self):
        """모니터링 데몬을 중지합니다."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            
        # 마지막 주기 결과를 유지하고 종료 메시지만 추가
        # 모니터링 결과가 있는 경우에만 종료 메시지 추가
        if self.monitoring_result and self.monitoring_result.get("start_time"):
            monitoring_logger.info(f"[모니터링] 데몬 중지됨: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            monitoring_logger.info("모니터링 데몬이 중지되었습니다.")

    def pause_monitoring(self):
        self.need_stop_monitoring = True
    
    def resume_monitoring(self):
        self.need_stop_monitoring = False

    def _monitor_loop(self):
        """메인 모니터링 루프"""
        check_count = 0

        config = load_json_config()
        interval = config.get('monitoring_interval')
        
        while self.running:
            if self.need_stop_monitoring:
                time.sleep(interval)
                continue

            try:
                check_count += 1
                # 각 모니터링 주기마다 시작 시간 기록
                start_time = datetime.now()
                
                # 각 모니터링 주기마다 결과 초기화
                self.monitoring_result = {
                    "start_time": start_time,
                    "last_check_time": start_time,
                    "run_duration": "0시간 0분 0초",
                    "added_files": [],
                    "modified_files": [],
                    "deleted_files": []
                }
                
                # 일정 간격으로만 로그 출력 (10회마다)
                if check_count % 10 == 1:
                    monitoring_logger.info(f"[모니터링] 주기 #{check_count} 시작: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                self._check_and_upload_files()
                
                # 주기 종료 시간 기록 및 소요 시간 계산
                end_time = datetime.now()
                duration = end_time - start_time
                hours, remainder = divmod(duration.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                # 결과 업데이트
                self.monitoring_result["last_check_time"] = end_time
                self.monitoring_result["run_duration"] = f"{int(hours)}시간 {int(minutes)}분 {int(seconds)}초"
                
                # 변경사항이 있거나 10회마다 로그 출력
                has_changes = len(self.monitoring_result["added_files"]) > 0 or \
                              len(self.monitoring_result["modified_files"]) > 0 or \
                              len(self.monitoring_result["deleted_files"]) > 0
                
                if has_changes or check_count % 10 == 1:
                    monitoring_logger.info(f"[모니터링] 주기 #{check_count} 종료: {end_time.strftime('%H:%M:%S')}, 소요 시간: {int(hours)}시간 {int(minutes)}분 {int(seconds)}초")
                
                # 다음 주기까지 대기
                self.last_check_timestamp = end_time
                time.sleep(interval)
            except Exception as e:
                monitoring_logger.exception(f"[모니터링] 모니터링 루프 오류: {e}")
                traceback.print_exc()
                time.sleep(1)

    def get_monitoring_result(self) -> Dict:
        """모니터링 결과를 반환합니다."""
        return self.monitoring_result

    def _check_and_upload_files(self):
        """파일 변경 감지 및 업로드"""
        try:
            now = datetime.now().isoformat()

            # 모니터링 파일 정보 로드
            files = []
            store_path = os.path.join(os.path.dirname(__file__), 'store')
            for fname in os.listdir(store_path):
                if not fnmatch.fnmatch(fname, 'monitoring_files_*_*.yaml'):
                    continue
                rag_part = fname.split('_')[2] if len(fname.split('_')) > 2 else None
                try:
                    info = self.load_monitoring_info(rag_part)
                    original_files = info.get('files', [])
                    folders = info.get('folders', [])

                    # 폴더 경로에서 파일 검색
                    discovered_paths = []
                    for folder in folders:
                        if os.path.isdir(folder):
                            for root, _, fnames in os.walk(folder):
                                for fn in fnames:
                                    if fn.startswith('.') or fn.startswith('~$'):
                                        continue
                                    discovered_paths.append(os.path.join(root, fn))

                    existing_paths = {f['path'] for f in original_files if 'path' in f}
                    now_iso = datetime.now().isoformat()
                    updated_list = False
                    for p in discovered_paths:
                        if p not in existing_paths:
                            original_files.append({'name': os.path.basename(p), 'path': p, 'registered_at': now_iso})
                            existing_paths.add(p)
                            updated_list = True

                    # YAML에 변경 사항 저장
                    if updated_list:
                        self.save_monitoring_info(info.get('ip'), info.get('port'), original_files, rag_part, folders=folders)

                    files.extend(original_files)
                except Exception as e:
                    monitoring_logger.exception(f"[모니터링] {fname} 로드 오류: {e}")
            
            if not files:
                #print("[모니터링] 모니터링할 파일이 없습니다.")
                return
                
            # 파일 개수가 많을 때만 상세 로그 출력
            if len(files) > 10:
                monitoring_logger.info(f"[모니터링] 모니터링 중인 파일 수: {len(files)}개")
                monitoring_logger.info(f"[모니터링] 이전 파일 목록 크기: {len(self.previous_file_paths)}개")
            
            updated = False
            
            # 현재 모니터링 중인 파일 경로 목록
            # 현재 존재하는 파일 경로만 수집 (삭제된 항목 제외)
            current_file_paths = {file['path'] for file in files if 'path' in file and os.path.exists(file['path'])}
            
            # 새로 추가된 파일 감지 (현재 있지만 이전에 없었던 파일)
            new_files = list(current_file_paths - self.previous_file_paths)
            for path in new_files:
                if path and os.path.exists(path):
                    self.monitoring_result["added_files"].append(path)
                    monitoring_logger.info(f"[모니터링] 새 파일 감지: {path}")
                    
                    # 새 파일을 바로 업로드
                    try:
                        result = self.main_frame_ref.api_client.upload_file(path)
                        if not result.get("error"):
                            # 업로드 성공한 파일의 registered_at 정보 업데이트
                            for file in files:
                                if file.get('path') == path:
                                    file['registered_at'] = datetime.now().isoformat()
                                    updated = True
                                    monitoring_logger.info(f"[모니터링] 새 파일 업로드 성공: {path}")
                        else:
                            monitoring_logger.error(f"[모니터링] 새 파일 업로드 실패: {path}, 오류: {result.get('error')}")
                        time.sleep(0.5)  # 업로드 후 딜레이 추가
                    except Exception as e:
                        monitoring_logger.exception(f"[모니터링] 새 파일 업로드 중 오류: {e}")
            
            # 삭제된 파일 감지 (이전에 있었지만 현재 없는 파일)
            deleted_files = list(self.previous_file_paths - current_file_paths)
            for path in deleted_files:
                if path:
                    self.monitoring_result["deleted_files"].append(path)
                    monitoring_logger.info(f"[모니터링] 삭제된 파일 감지: {path}")
            
            # 각 파일의 변경 확인 및 업로드
            for file in files:
                if 'path' not in file:
                    continue
                    
                path = file['path']
                last_registered = file.get('registered_at')
                
                if not last_registered:
                    monitoring_logger.warning(f"[모니터링] 파일에 등록 시간 정보가 없습니다: {path}")
                    continue
                    
                try:
                    last_registered_dt = datetime.fromisoformat(last_registered)
                except Exception as e:
                    monitoring_logger.exception(f"[모니터링] 등록 시간 파싱 오류({path}): {e}")
                    continue
                    
                if os.path.exists(path):
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(path))
                        
                        # 파일이 변경되었는지 확인
                        if mtime > last_registered_dt:
                            monitoring_logger.info(f"[모니터링] 변경된 파일 감지: {path}")
                            monitoring_logger.info(f"  - 마지막 등록: {last_registered_dt}")
                            monitoring_logger.info(f"  - 수정 시간: {mtime}")
                            
                            # 파일 업로드
                            result = self.main_frame_ref.api_client.upload_file(path)
                            if not result.get("error"):
                                file['registered_at'] = datetime.now().isoformat()
                                updated = True
                                
                                # 변경된 파일 추적
                                self.monitoring_result["modified_files"].append(path)
                                monitoring_logger.info(f"[모니터링] 파일 업로드 성공: {path}")
                            else:
                                monitoring_logger.error(f"[모니터링] 파일 업로드 실패: {path}, 오류: {result.get('error')}")
                            time.sleep(0.5)  # 업로드 후 딜레이 추가
                    except Exception as e:
                        monitoring_logger.exception(f"[모니터링] 파일 변경 확인 중 오류({path}): {e}")
            
            if updated:
                # 변경된 정보 저장
                self.save_monitoring_info(info.get('ip'), info.get('port'), files)
                monitoring_logger.info("[모니터링] 모니터링 정보 업데이트됨")
            
            # 현재 파일 목록을 이전 목록으로 저장 (다음 비교를 위해)
            self.previous_file_paths = current_file_paths
            
            # 변경된 파일이 있을 때만 결과 요약 출력
            total_changed = len(self.monitoring_result['added_files']) + \
                          len(self.monitoring_result['modified_files']) + \
                          len(self.monitoring_result['deleted_files'])
            if total_changed > 0:
                monitoring_logger.info(f"[모니터링] 확인 결과 - 추가: {len(self.monitoring_result['added_files'])}개, " +
                      f"수정: {len(self.monitoring_result['modified_files'])}개, " +
                      f"삭제: {len(self.monitoring_result['deleted_files'])}개")
                self.main_frame_ref.doc_panel.on_refresh_documents(None)
            
        except Exception as e:
            monitoring_logger.exception(f"[모니터링] 파일 변경 확인 중 오류: {e}")
            traceback.print_exc()

    def set_interval(self, seconds: int):
        """모니터링 간격을 설정합니다."""
        if seconds < 1:
            seconds = 1
        
        config = load_json_config()
        config['monitoring_interval'] = seconds
        save_json_config(config)
        monitoring_logger.info(f"[모니터링] 모니터링 간격이 {seconds}초로 변경되었습니다.")


    def get_monitoring_yaml_path(self, rag_name: str | None = None, port: str | None = None):
        """
        현재 사용 중인 IP와 포트를 기반으로 monitoring yaml 파일 경로를 생성합니다.
        형식: monitoring_files_[IP]_[PORT].yaml
        """
        info = {}
        rag_name = rag_name or 'default'
        
        if port is None:
            # config나 환경변수에서 포트 추출 로직 필요시 추가
            raise ValueError("Port is not set.")
        
        # store 폴더 하위에 저장
        store_dir = os.path.join(os.getcwd(), 'store')
        os.makedirs(store_dir, exist_ok=True)
        filename = f'monitoring_files_{rag_name}_{port}.yaml'
        return os.path.join(store_dir, filename)

    # ------------------------------------------------------------------
    # 새롭게 추가된 클래스 메서드 (폴더 모니터링 및 YAML 관리)
    # ------------------------------------------------------------------
    def load_monitoring_info(self, rag_name: str | None = None, port: str | None = None):
        """monitoring yaml 파일을 로드합니다.
        기존 구조와의 호환을 위해 folders / files 키가 없으면 기본값을 채웁니다."""
        if port is None:
            port = str(get_datastore_port())

        path = self.get_monitoring_yaml_path(rag_name, port)
        config = load_json_config()

        # 파일이 없으면 기본 구조 반환
        if not os.path.exists(path):
            return {
                'ip': config['client_ip'],
                'port': config['port'],
                'files': [],
                'folders': []
            }

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        data.setdefault('files', [])
        data.setdefault('folders', [])
        return data

    def save_monitoring_info(self, ip: str, port: str, files: list, rag_name: str | None = None, folders: list | None = None):
        """monitoring yaml 파일을 저장합니다.
        folders 파라미터가 None 이면 기존 값을 유지합니다."""
        path = self.get_monitoring_yaml_path(rag_name, port)
        now = datetime.now().isoformat()

        if folders is None:
            try:
                current = self.load_monitoring_info(rag_name, port)
                folders = current.get('folders', [])
            except Exception:
                folders = []

        data = {
            'ip': ip,
            'port': port,
            'last_check_time': now,
            'files': files,
            'folders': folders,
        }
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True)

    def init_previous_file_paths(self):
        """모니터링 시작 시 기존 파일 경로 집합을 초기화합니다."""
        collected_files: list[dict] = []
        try:
            store_path = os.path.join(os.path.dirname(__file__), 'store')
            os.makedirs(store_path, exist_ok=True)
            for fname in os.listdir(store_path):
                if not fnmatch.fnmatch(fname, 'monitoring_files_*_*.yaml'):
                    continue
                rag_part = fname.split('_')[2] if len(fname.split('_')) > 2 else None
                try:
                    info = self.load_monitoring_info(rag_part)
                    collected_files.extend(info.get('files', []))
                    # 폴더 내부 파일 재귀 수집
                    for folder in info.get('folders', []):
                        if not os.path.isdir(folder):
                            continue
                        for root, _, names in os.walk(folder):
                            for n in names:
                                if n.startswith('.') or n.startswith('~$'):
                                    continue
                                collected_files.append({
                                    'name': n,
                                    'path': os.path.join(root, n),
                                    'registered_at': datetime.now().isoformat(),
                                })
                except Exception as e:
                    monitoring_logger.exception(f"[모니터링] 초기 파일 목록 읽기 오류({fname}): {e}")
            # 중복 제거 후 set 생성
            self.previous_file_paths = {f['path'] for f in collected_files if 'path' in f}
            monitoring_logger.info(f"[모니터링] 초기 로드된 파일 수: {len(self.previous_file_paths)}")
        except Exception as e:
            monitoring_logger.exception(f"[모니터링] 초기 파일 로드 실패: {e}")
            self.previous_file_paths = set()

    def append_monitoring_folder(self, folder_path: str, rag_name: str | None = None):
        """새 폴더를 모니터링 대상으로 등록합니다."""
        folder_path = os.path.abspath(folder_path)

        info = self.load_monitoring_info(rag_name)
        ip   = info.get('ip')
        port = info.get('port')
        if not ip or not port:
            raise ValueError("IP or Port is not set for monitoring files")

        folders = info.get('folders', [])
        if folder_path not in folders:
            folders.append(folder_path)
            self.save_monitoring_info(ip, port, info.get('files', []),
                                      rag_name, folders=folders)
            monitoring_logger.info(f"[monitoring_daemon] 폴더 등록: {folder_path}")
        else:
            monitoring_logger.info(f"[monitoring_daemon] 이미 등록된 폴더: {folder_path}")

    def append_monitoring_file(self, file_path, rag_name: str | None = None):
        if rag_name is None:
            print(f"[Error] can't add monitoring file due to rag_name is None: {file_path}")
            return
        
        info = self.load_monitoring_info(rag_name)
        ip = info.get('ip')
        port = info.get('port')
        if port is None or ip is None:
            raise ValueError("IP or Port is not set for moinotirng files")

        port = info.get('port')
        files = info.get('files', [])
        name = os.path.basename(file_path)
        now = datetime.now().isoformat()

        # 동일 건이 있으면 삭제
        for i, f in enumerate(files):
            if f['path'] == file_path:
                del files[i]
                break
        
        # 여러 건인 경우 처리 방법
        # remove_paths = {file_path1, file_path2}
        # files = [f for f in files if f['path] not in remove_paths]

        files.append({'name': name, 'path': file_path, 'registered_at': now})
        self.save_monitoring_info(ip, port, files, rag_name)


        # 파일이 속한 폴더도 아직 모니터링 대상이 아니라면 함께 등록합니다.
        info = self.load_monitoring_info(rag_name)
        ip = info.get('ip')
        port = info.get('port')
        if port is None or ip is None:
            raise ValueError("IP or Port is not set for monitoring files")

        folders = info.get('folders', [])
        folder_path = os.path.abspath(os.path.dirname(file_path))
        if folder_path not in folders:
            folders.append(folder_path)
            # files 리스트는 위에서 최신 상태로 저장했으므로 그대로 사용
            self.save_monitoring_info(ip, port, info.get('files', []), rag_name, folders=folders)
            monitoring_logger.info(f"[monitoring_daemon] 폴더 등록: {folder_path}")
        # 함수 종료
        return

    def append_monitoring_files(self, file_paths, rag_name: str | None = None):
        info = self.load_monitoring_info(rag_name)
        ip = info.get('ip')
        port = info.get('port')
        if port is None or ip is None:
            raise ValueError("IP or Port is not set for moinotirng files")
        
        files = info.get('files', [])
        now = datetime.now().isoformat()
        for file_path in file_paths:
            name = os.path.basename(file_path)
            files.append({'name': name, 'path': file_path, 'registered_at': now})
        self.save_monitoring_info(ip, port, files, rag_name)

    def clear_monitoring_files(self, rag_name: str | None = None):
        """모든 문서 삭제 시 monitoring_files_ip_port.yaml 파일 초기화"""
        info = self.load_monitoring_info(rag_name)
        ip = info.get('ip')
        port = info.get('port')
        if port is None or ip is None:
            raise ValueError("IP or Port is not set for moinotirng files")
        
        # 파일 목록만 비우고 IP와 포트는 유지
        self.save_monitoring_info(ip, port, [], rag_name)
        monitoring_logger.info(f"[ip_middleware] monitoring_files_ip_port.yaml 파일 초기화 완료")

    def delete_monitoring_file(self, file_path, rag_name: str | None = None):
        """yaml 파일에서 특정 파일을 삭제합니다."""
        info = self.load_monitoring_info(rag_name)
        ip = info.get('ip')
        port = info.get('port')
        if port is None or ip is None:
            raise ValueError("IP or Port is not set for moinotirng files")
        
        files = info.get('files', [])
        
        # 파일 경로가 일치하는 항목 제거
        files = [f for f in files if f.get('path') != file_path]
        self.save_monitoring_info(ip, port, files, rag_name)
        monitoring_logger.info(f"[monitoring_daemon] {file_path} yaml 파일에서 삭제됨")

    def delete_monitoring_files(self, file_paths, rag_name: str | None = None):
        """yaml 파일에서 여러 파일을 삭제합니다."""
        info = self.load_monitoring_info(rag_name)
        ip = info.get('ip')
        port = info.get('port')
        if port is None or ip is None:
            raise ValueError("IP or Port is not set for moinotirng files")
        
        files = info.get('files', [])
        
        # 파일 경로가 일치하지 않는 항목만 유지
        files = [f for f in files if f.get('path') not in file_paths]
        self.save_monitoring_info(ip, port, files, rag_name)
        monitoring_logger.info(f"[ip_middleware] {len(file_paths)}개 파일 yaml 파일에서 삭제됨")