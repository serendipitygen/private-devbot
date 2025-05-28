import os
import time
import psutil
import threading
import yaml
from datetime import datetime
import socket
import json
import traceback
from typing import Dict, Optional
from ui.api_client import ApiClient
from ip_middleware import get_local_ips
from ui.config_util import load_json_config, get_config_file
import fnmatch

class MonitoringDaemon:
    def __init__(self, config_path: str = "monitoring_config.yaml"):
        self.config_path = config_path
        self.running = False
        self.monitor_thread = None
        self.metrics = {
            "cpu_usage": [],
            "memory_usage": [],
            "disk_usage": [],
            "network_io": [],
            "server_status": "stopped"
        }
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
        self.last_check_timestamp = datetime.now()
        self.initialized_file_tracking = False  # 파일 추적 초기화 여부
        
        self.max_metrics_history = 1000  # 최대 메트릭 저장 개수
        self.monitoring_interval = 10  # 모니터링 간격 (초)
        self.init_api_base_url()

    def init_api_base_url(self):
        try:
            config = load_json_config(get_config_file())
            ip = config.get("ip")
            # "ip" 키가 없으면 "client_ip" 키를 사용
            if ip is None:
                ip = config.get("client_ip")
            
            port = config.get("port")

            if ip is None or port is None:
                # 에러 메시지를 좀 더 구체적으로 변경
                missing_keys = []
                if ip is None:
                    missing_keys.append("'ip' or 'client_ip'")
                if port is None:
                    missing_keys.append("'port'")
                
                error_msg = f"MonitoringDaemon: {', '.join(missing_keys)} not found in config or is None."
                print(f"[ERROR] {error_msg}")
                raise ValueError(error_msg)

            api_base_url = f"http://{ip}:{port}"
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print(api_base_url)
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            self.api_client = ApiClient(lambda: {"api_base_url": api_base_url}, lambda: {})
            self.load_config()
            self._pause_event = threading.Event()
            self._pause_event.clear()

        except FileNotFoundError:
            print("[ERROR] MonitoringDaemon: Configuration file not found. Cannot initialize.")
            raise
        except ValueError as ve:
            print(f"[ERROR] MonitoringDaemon: Configuration error - {ve}")
            raise
        except Exception as e:
            print(f"[ERROR] MonitoringDaemon: Unexpected error during initialization: {e}")
            traceback.print_exc()
            raise

    def load_config(self):
        """설정 파일을 로드합니다."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self.monitoring_interval = config.get('monitoring_interval', 10)
                    self.max_metrics_history = config.get('max_metrics_history', 1000)
        except Exception as e:
            print(f"설정 파일 로드 중 오류 발생: {e}")

    def save_config(self):
        """설정을 파일에 저장합니다."""
        try:
            config = {
                'monitoring_interval': self.monitoring_interval,
                'max_metrics_history': self.max_metrics_history
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True)
        except Exception as e:
            print(f"설정 파일 저장 중 오류 발생: {e}")

    def start(self):
        """모니터링 데몬을 시작합니다."""
        if self.running:
            print("[모니터링] 이미 실행 중이므로 중복 시작 요청 무시")
            return

        print(f"[모니터링] 데몬 시작됨: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
        
        # 첫 시작시에만 이전 파일 목록 초기화
        if not self.initialized_file_tracking:
            # 이전 파일 목록 초기화 (새로 시작할 때만)
            self.previous_file_paths = set()
            
            # 모니터링 시작 전 현재 파일 목록 로드
            try:
                # 모든 monitoring_files_*_*.yaml 파일을 읽어 합산
                files = []
                for fname in os.listdir(os.getcwd()):
                    if fnmatch.fnmatch(fname, 'monitoring_files_*_*.yaml'):
                        try:
                            rag_part = fname.split('_')[2] if len(fname.split('_')) > 2 else None
                            info = self.load_monitoring_info(rag_part)
                            files.extend(info.get('files', []))
                        except Exception as e:
                            print(f"[모니터링] {fname} 로드 오류: {e}")
                self.previous_file_paths = set(file['path'] for file in files if 'path' in file)
                print(f"[모니터링] 초기 파일 목록 로드: {len(self.previous_file_paths)}개 파일")
                self.initialized_file_tracking = True  # 초기화 완료 표시
            except Exception as e:
                print(f"[모니터링] 초기 파일 목록 로드 실패: {e}")
                traceback.print_exc()  # 상세 오류 정보 출력
        else:
            print(f"[모니터링] 이미 초기화된 파일 추적 상태 유지: {len(self.previous_file_paths)}개 파일")
        
        print(f"[모니터링] 모니터링 시작됨: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("[모니터링] 모니터링 데몬이 시작되었습니다.")
        
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
            print(f"[모니터링] 데몬 중지됨: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("모니터링 데몬이 중지되었습니다.")

    def _monitor_loop(self):
        """메인 모니터링 루프"""
        check_count = 0

        config = load_json_config(get_config_file())
        interval = config.get('monitoring_interval')
        
        while self.running:
            if self._pause_event.is_set():
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
                    print(f"[모니터링] 주기 #{check_count} 시작: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # 메트릭 수집 및 파일 확인
                #self._collect_metrics()
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
                    print(f"[모니터링] 주기 #{check_count} 종료: {end_time.strftime('%H:%M:%S')}, 소요 시간: {int(hours)}시간 {int(minutes)}분 {int(seconds)}초")
                
                # 다음 주기까지 대기
                self.last_check_timestamp = end_time
                time.sleep(interval)
            except Exception as e:
                print(f"[모니터링] 모니터링 루프 오류: {e}")
                traceback.print_exc()
                time.sleep(1)
                
    def _collect_metrics(self):
        """시스템 메트릭을 수집합니다."""
        try:
            # CPU 사용량
            cpu_percent = psutil.cpu_percent(interval=1)
            self._add_metric("cpu_usage", cpu_percent)

            # 메모리 사용량
            memory = psutil.virtual_memory()
            self._add_metric("memory_usage", memory.percent)

            # 디스크 사용량
            disk = psutil.disk_usage('/')
            self._add_metric("disk_usage", disk.percent)

            # 네트워크 IO
            net_io = psutil.net_io_counters()
            self._add_metric("network_io", {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv
            })

            # 서버 상태 확인
            self._check_server_status()

        except Exception as e:
            print(f"메트릭 수집 중 오류 발생: {e}")

    def _add_metric(self, metric_name: str, value: any):
        """메트릭을 추가하고 최대 개수를 유지합니다."""
        timestamp = datetime.now().isoformat()
        self.metrics[metric_name].append({
            "timestamp": timestamp,
            "value": value
        })
        
        # 최대 개수 유지
        if len(self.metrics[metric_name]) > self.max_metrics_history:
            self.metrics[metric_name] = self.metrics[metric_name][-self.max_metrics_history:]

    def _check_server_status(self):
        """서버 상태를 확인합니다."""
        try:
            config = load_json_config(get_config_file())

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((config.get("ip"), config.get("port")))
            sock.close()
            
            self.metrics["server_status"] = "running" if result == 0 else "stopped"
        except:
            self.metrics["server_status"] = "stopped"

    def get_metrics(self, metric_name: Optional[str] = None) -> Dict:
        """수집된 메트릭을 반환합니다."""
        if metric_name:
            return self.metrics.get(metric_name, [])
        return self.metrics

    def get_latest_metrics(self) -> Dict:
        """최신 메트릭을 반환합니다."""
        latest = {}
        for metric_name, values in self.metrics.items():
            if values:
                latest[metric_name] = values[-1]
            else:
                latest[metric_name] = None
        return latest

    def get_monitoring_result(self) -> Dict:
        """모니터링 결과를 반환합니다."""
        return self.monitoring_result

    def save_metrics_to_file(self, file_path: str):
        """메트릭을 파일에 저장합니다."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"메트릭 저장 중 오류 발생: {e}")

    def load_metrics_from_file(self, file_path: str):
        """파일에서 메트릭을 로드합니다."""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.metrics = json.load(f)
        except Exception as e:
            print(f"메트릭 로드 중 오류 발생: {e}")

    def _check_and_upload_files(self):
        """파일 변경 감지 및 업로드"""
        try:
            # 파일 변경 확인 시작 로그는 변경사항이 있을 때만 출력
            # print(f"[모니터링] 파일 변경 확인 시작: {datetime.now().strftime('%H:%M:%S')}")
            
            # 모니터링 파일 정보 로드
            files = []
            for fname in os.listdir(os.getcwd()):
                if fnmatch.fnmatch(fname, 'monitoring_files_*_*.yaml'):
                    rag_part = fname.split('_')[2] if len(fname.split('_')) > 2 else None
                    try:
                        info = self.load_monitoring_info(rag_part)
                        files.extend(info.get('files', []))
                    except Exception as e:
                        print(f"[모니터링] {fname} 로드 오류: {e}")
            
            if not files:
                #print("[모니터링] 모니터링할 파일이 없습니다.")
                return
                
            # 파일 개수가 많을 때만 상세 로그 출력
            if len(files) > 10:
                print(f"[모니터링] 모니터링 중인 파일 수: {len(files)}개")
                print(f"[모니터링] 이전 파일 목록 크기: {len(self.previous_file_paths)}개")
            
            updated = False
            
            # 현재 모니터링 중인 파일 경로 목록
            current_file_paths = set(file['path'] for file in files if 'path' in file)
            
            # 새로 추가된 파일 감지 (현재 있지만 이전에 없었던 파일)
            new_files = list(current_file_paths - self.previous_file_paths)
            for path in new_files:
                if path and os.path.exists(path):
                    self.monitoring_result["added_files"].append(path)
                    print(f"[모니터링] 새 파일 감지: {path}")
                    
                    # 새 파일을 바로 업로드
                    try:
                        result = self.api_client.upload_file(path)
                        if not result.get("error"):
                            # 업로드 성공한 파일의 registered_at 정보 업데이트
                            for file in files:
                                if file.get('path') == path:
                                    file['registered_at'] = datetime.now().isoformat()
                                    updated = True
                                    print(f"[모니터링] 새 파일 업로드 성공: {path}")
                        else:
                            print(f"[모니터링] 새 파일 업로드 실패: {path}, 오류: {result.get('error')}")
                    except Exception as e:
                        print(f"[모니터링] 새 파일 업로드 중 오류: {e}")
            
            # 삭제된 파일 감지 (이전에 있었지만 현재 없는 파일)
            deleted_files = list(self.previous_file_paths - current_file_paths)
            for path in deleted_files:
                if path:
                    self.monitoring_result["deleted_files"].append(path)
                    print(f"[모니터링] 삭제된 파일 감지: {path}")
            
            # 각 파일의 변경 확인 및 업로드
            for file in files:
                if 'path' not in file:
                    continue
                    
                path = file['path']
                last_registered = file.get('registered_at')
                
                if not last_registered:
                    print(f"[모니터링] 파일에 등록 시간 정보가 없습니다: {path}")
                    continue
                    
                try:
                    last_registered_dt = datetime.fromisoformat(last_registered)
                except Exception as e:
                    print(f"[모니터링] 등록 시간 파싱 오류({path}): {e}")
                    continue
                    
                if os.path.exists(path):
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(path))
                        
                        # 파일이 변경되었는지 확인
                        if mtime > last_registered_dt:
                            print(f"[모니터링] 변경된 파일 감지: {path}")
                            print(f"  - 마지막 등록: {last_registered_dt}")
                            print(f"  - 수정 시간: {mtime}")
                            
                            # 파일 업로드
                            result = self.api_client.upload_file(path)
                            if not result.get("error"):
                                file['registered_at'] = datetime.now().isoformat()
                                updated = True
                                
                                # 변경된 파일 추적
                                self.monitoring_result["modified_files"].append(path)
                                print(f"[모니터링] 파일 업로드 성공: {path}")
                            else:
                                print(f"[모니터링] 파일 업로드 실패: {path}, 오류: {result.get('error')}")
                    except Exception as e:
                        print(f"[모니터링] 파일 변경 확인 중 오류({path}): {e}")
            
            if updated:
                # 변경된 정보 저장
                self.save_monitoring_info(info.get('ip'), info.get('port'), files)
                print("[모니터링] 모니터링 정보 업데이트됨")
            
            # 현재 파일 목록을 이전 목록으로 저장 (다음 비교를 위해)
            self.previous_file_paths = current_file_paths
            
            # 변경된 파일이 있을 때만 결과 요약 출력
            total_changed = len(self.monitoring_result['added_files']) + \
                          len(self.monitoring_result['modified_files']) + \
                          len(self.monitoring_result['deleted_files'])
            if total_changed > 0:
                print(f"[모니터링] 확인 결과 - 추가: {len(self.monitoring_result['added_files'])}개, " +
                      f"수정: {len(self.monitoring_result['modified_files'])}개, " +
                      f"삭제: {len(self.monitoring_result['deleted_files'])}개")
            
        except Exception as e:
            print(f"[모니터링] 파일 변경 확인 중 오류: {e}")
            traceback.print_exc()

    def set_interval(self, seconds: int):
        """모니터링 간격을 설정합니다."""
        if seconds < 1:
            seconds = 1
        self.monitoring_interval = seconds
        print(f"[모니터링] 모니터링 간격이 {seconds}초로 변경되었습니다.")

    def pause_monitoring(self):
        self._pause_event.set()

    def resume_monitoring(self, delay_sec=10):
        def delayed_resume():
            time.sleep(delay_sec)
            self._pause_event.clear()
        threading.Thread(target=delayed_resume, daemon=True).start() 


    def get_monitoring_yaml_path(self, rag_name: str | None = None, port: str | None = None):
        """
        현재 사용 중인 IP와 포트를 기반으로 monitoring yaml 파일 경로를 생성합니다.
        형식: monitoring_files_[IP]_[PORT].yaml
        """
        info = {}
        rag_name = rag_name or 'default'
        
        if port is None:
            # config나 환경변수에서 포트 추출 로직 필요시 추가
            raise ValueError("Port is not set. Please set the port in the devbot_config.json file.")
        
        # store 폴더 하위에 저장
        store_dir = os.path.join(os.getcwd(), 'store')
        os.makedirs(store_dir, exist_ok=True)
        filename = f'monitoring_files_{rag_name}_{port}.yaml'
        return os.path.join(store_dir, filename)

    def load_monitoring_info(self, rag_name: str | None = None, port: str | None = None):
        path = self.get_monitoring_yaml_path(rag_name, port)
        
        if not os.path.exists(path):
            return {'ip': None, 'port': None, 'files': []}
        
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {'ip': None, 'port': None, 'files': []}

    def save_monitoring_info(self, ip, port, files, rag_name: str | None = None):
        path = self.get_monitoring_yaml_path(rag_name, port)
        data = {'ip': ip, 'port': port, 'files': files}
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True)

    def append_monitoring_file(self, file_path, rag_name: str | None = None):
        info = self.load_monitoring_info(rag_name)
        ip = list(get_local_ips())[0] if get_local_ips() else '127.0.0.1'
        port = info.get('port')
        if port is None:
            raise ValueError("Port is not set. Please set the port in the devbot_config.json file.")

        port = info.get('port')
        files = info.get('files', [])
        name = os.path.basename(file_path)
        now = datetime.now().isoformat()
        files.append({'name': name, 'path': file_path, 'registered_at': now})
        self.save_monitoring_info(ip, port, files, rag_name)

    def append_monitoring_files(self, file_paths, rag_name: str | None = None):
        info = self.load_monitoring_info(rag_name)
        ip = list(get_local_ips())[0] if get_local_ips() else '127.0.0.1'
        port = info.get('port')

        if port is None:
            raise ValueError("Port is not set. Please set the port in the devbot_config.json file.")

        files = info.get('files', [])
        now = datetime.now().isoformat()
        for file_path in file_paths:
            name = os.path.basename(file_path)
            files.append({'name': name, 'path': file_path, 'registered_at': now})
        self.save_monitoring_info(ip, port, files, rag_name)

    def clear_monitoring_files(self, rag_name: str | None = None):
        """모든 문서 삭제 시 monitoring_files_ip_port.yaml 파일 초기화"""
        info = self.load_monitoring_info(rag_name)
        ip = info.get('ip') or (list(get_local_ips())[0] if get_local_ips() else '127.0.0.1')
        port = info.get('port')

        if port is None:
            raise ValueError("Port is not set. Please set the port in the devbot_config.json file.")

        # 파일 목록만 비우고 IP와 포트는 유지
        self.save_monitoring_info(ip, port, [], rag_name)
        print(f"[ip_middleware] monitoring_files_ip_port.yaml 파일 초기화 완료")

    def delete_monitoring_file(self, file_path, rag_name: str | None = None):
        """yaml 파일에서 특정 파일을 삭제합니다."""
        info = self.load_monitoring_info(rag_name)
        ip = info.get('ip') or (list(get_local_ips())[0] if get_local_ips() else '127.0.0.1')
        port = info.get('port')

        if port is None:
            raise ValueError("Port is not set. Please set the port in the devbot_config.json file.")

        files = info.get('files', [])
        
        # 파일 경로가 일치하는 항목 제거
        files = [f for f in files if f.get('path') != file_path]
        self.save_monitoring_info(ip, port, files, rag_name)
        print(f"[ip_middleware] {os.path.basename(file_path)} yaml 파일에서 삭제됨")

    def delete_monitoring_files(self, file_paths, rag_name: str | None = None):
        """yaml 파일에서 여러 파일을 삭제합니다."""
        info = self.load_monitoring_info(rag_name)
        ip = info.get('ip') or (list(get_local_ips())[0] if get_local_ips() else '127.0.0.1')
        port = info.get('port')

        if port is None:
            raise ValueError("Port is not set. Please set the port in the devbot_config.json file.")

        files = info.get('files', [])
        
        # 파일 경로가 일치하지 않는 항목만 유지
        files = [f for f in files if f.get('path') not in file_paths]
        self.save_monitoring_info(ip, port, files, rag_name)
        print(f"[ip_middleware] {len(file_paths)}개 파일 yaml 파일에서 삭제됨")