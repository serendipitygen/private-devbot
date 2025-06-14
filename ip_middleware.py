import os
import yaml
import socket
import ipaddress
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Dict, Any, Optional
import ast
from typing import Set
import config
from datetime import datetime

try:
    import netifaces
except ImportError:
    netifaces = None

private_devbot_version = config.private_devbot_version

def get_local_ips() -> Set[str]:
    """
    모든 OS에서 현재 PC의 모든 IPv4 주소를 set 형태로 반환합니다.
    - loopback(127.x.x.x)은 자동으로 제외
    - Windows, Linux, macOS 모두 호환
    - netifaces가 없어도 모든 IP를 추출
    """
    ips: Set[str] = set()

    # 1) UDP 소켓 방식으로 기본 라우팅된 로컬 IP 얻기
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            addr = s.getsockname()[0]
            if not addr.startswith("127.") and not addr.endswith(".1"):
                ips.add(addr)
    except Exception:
        pass  # 네트워크 연결 불가 시 무시

    # 2) netifaces가 설치되어 있으면 모든 인터페이스 순회 (가장 정확한 방법)
    if netifaces:
        for iface in netifaces.interfaces():
            try:
                addrs = netifaces.ifaddresses(iface)
                for link in addrs.get(netifaces.AF_INET, []):
                    addr = link.get("addr")
                    # loopback 제외
                    if addr and not addr.startswith("127.") and not addr.endswith(".1"):
                        ips.add(addr)
            except Exception:
                # 해당 인터페이스 처리 중 오류 발생 시 건너뜀
                continue
    # 3) netifaces가 없을 경우 socket.gethostbyname_ex 방식으로 모든 IP 추출
    else:
        try:
            # 호스트명으로 모든 IP 주소 조회
            hostname = socket.gethostname()
            _, _, all_ips = socket.gethostbyname_ex(hostname)
            for ip in all_ips:
                if not ip.startswith("127.") and not ip.endswith(".1"):
                    ips.add(ip)
            
            # Windows에서 추가 IP 확인 (일부 가상 어댑터 IP가 누락될 수 있음)
            if os.name == 'nt':
                try:
                    # ipconfig 명령어 실행하여 모든 IP 추출
                    import subprocess
                    output = subprocess.check_output('ipconfig', shell=True).decode('cp949')
                    for line in output.split('\n'):
                        line = line.strip()
                        if 'IPv4' in line:
                            ip_parts = line.split(':')[-1].strip()
                            if ip_parts and not ip_parts.startswith('127.') and not ip_parts.endswith('.1'):
                                ips.add(ip_parts)
                except Exception:
                    pass  # ipconfig 명령 실패 시 무시
        except Exception:
            pass  # 호스트명 조회 실패 시 무시

    ips.add('127.0.0.1')
    ips.add('localhost')
    return ips

class IPRestrictionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config_path: str = f"./store/devbot_config_{private_devbot_version}.yaml"):
        super().__init__(app)
        os.makedirs(os.path.dirname(config_path), exist_ok=True)  # 디렉토리 생성
        self.is_allowed_all_ips = False
        self.config_path = config_path
        self.allowed_ips = set()
        self.last_modified_time = 0  # 마지막 파일 수정 시간
        self.last_load_time = 0      # 마지막 로드 시간
        self.reload_interval = 5      # 최소 재로드 간격(초)
        self.load_config()
        
    def load_config(self, force=False):
        """설정 파일에서 허용된 IP 목록을 로드합니다.
        파일이 없거나 IP 목록이 비어있는 경우 현재 서버의 IP를 자동으로 등록합니다.
        변경 감지 메커니즘 적용: 파일이 변경된 경우에만 재로딩합니다.
        기본적으로 프록시 서버 IP(168.219.61.213)를 허용합니다.
        """
        current_time = time.time()
        
        # 파일이 존재하는지 확인
        config_exists = os.path.exists(self.config_path)
        
        # 강제 로드가 아니고, 마지막 로드 후 최소 간격이 지나지 않았다면 로드하지 않음
        if not force and (current_time - self.last_load_time < self.reload_interval):
            return
        
        # 파일이 존재하고, 마지막 수정 시간을 확인하여 변경이 없으면 로드하지 않음
        if config_exists and not force:
            file_mtime = os.path.getmtime(self.config_path)
            if file_mtime <= self.last_modified_time:
                self.last_load_time = current_time  # 로드 시도 시간 업데이트
                return
        
        try:
            # 파일이 존재하면 로드
            if config_exists:
                with open(self.config_path, 'r') as file:
                    config = yaml.safe_load(file)
                    if config and 'allowed_ips' in config:
                        self.allowed_ips = set(config['allowed_ips'])
                        self.is_allowed_all_ips = config.get('is_allowed_all_ips', False)
                        print(f"Loaded allowed IPs: {self.allowed_ips}")
                
                # 파일 수정 시간 업데이트
                self.last_modified_time = os.path.getmtime(self.config_path)
            
            # 항상 Private RAG 서버의 IP와 프록시 서버 IP는 추가한다.
            self.allowed_ips = self.allowed_ips | get_local_ips() | {'168.219.61.213'}
            
            # 새 파일 생성 또는 기존 파일 업데이트 필요 시
            if not config_exists or force:
                self.save_config()
                if config_exists:
                    self.last_modified_time = os.path.getmtime(self.config_path)
            
            # 마지막 로드 시간 업데이트
            self.last_load_time = current_time
                
        except Exception as e:
            print(f"Fail to load setting file of datastore: {str(e)}")
    
    def save_config(self):
        """현재 허용된 IP 목록을 설정 파일에 저장합니다."""
        try:
            config = {'allowed_ips': list(self.allowed_ips), 'is_allowed_all_ips': self.is_allowed_all_ips}
            with open(self.config_path, 'w') as file:
                yaml.dump(config, file, default_flow_style=False)
            print(f"Saved the setting of datastore: {self.config_path}")
        except Exception as e:
            print(f"Error to save the setting of datastore: {str(e)}")
    
    def is_local_ip(self, ip) -> bool:
        """주어진 IP가 로컬 IP인지 확인합니다."""
        local_ips = get_local_ips()
        localhost_ips = list({"127.0.0.1", "::1"} | local_ips)
        if isinstance(ip, list):
            return any(ip in localhost_ips for ip in ip)
        else:
            return ip in localhost_ips
    
    def is_private_ip(self, ip: str) -> bool:
        """주어진 IP가 사설 IP인지 확인합니다."""
        try:
            return ipaddress.ip_address(ip).is_private
        except:
            return False
    
    def update_allowed_ips(self, ips: List[str]) -> Dict[str, Any]:
        """허용된 IP 목록을 업데이트합니다."""
        valid_ips = []
        invalid_ips = []
        
        # 빈 리스트가 넘어오면 모든 IP 허용 (허용 IP 목록 초기화)
        if len(ips) == 0:
            self.allowed_ips = get_local_ips()
            self.is_allowed_all_ips = True
            self.save_config()
            return {
                "status": "success",
                "valid_ips": [],
                "invalid_ips": [],
                "message": "All IPs are set to connect"
            }
        
        for ip in ips:
            try:
                # IP 주소 유효성 검사
                ipaddress.ip_address(ip)
                valid_ips.append(ip)
            except ValueError:
                invalid_ips.append(ip)
        
        if valid_ips:
            self.allowed_ips = set(valid_ips)
            self.is_allowed_all_ips = False
            self.save_config()
            return {
                "status": "success" if not invalid_ips else "partial_success",
                "valid_ips": valid_ips,
                "invalid_ips": invalid_ips,
                "message": "IP list was updated."
            }
        else:
            return {
                "status": "failed",
                "valid_ips": [],
                "invalid_ips": ips,
                "message": "Fail to set IP list"
            }
    
    def get_allowed_ips(self) -> List[str]:
        """현재 허용된 IP 목록을 반환합니다."""
        # 캐시된 값 사용, 필요할 때만 설정 파일 로드
        self.load_config(force=False)
        return list(self.allowed_ips)
    
    async def dispatch(self, request: Request, call_next):
        """요청을 처리하고 IP 제한을 적용합니다."""
        # 필요할 때만 설정 파일 로드 (변경 감지)
        self.load_config(force=False)

        if self.is_allowed_all_ips:
            return await call_next(request)

        client_ip = request.headers.get("X-Real-IP") or request.client.host

        if client_ip.startswith("["):  
            client_ip = ast.literal_eval(client_ip)
        elif client_ip.startswith("::ffff:"):
            client_ip = client_ip[7:]  # IPv4-mapped IPv6 address 형식인 경우 IPv4 부분만 추출
        elif client_ip.startswith("fe80:"):
            client_ip = client_ip.split("%")[0]  # 링크 로컬 IPv6 주소의 경우 인터페이스 식별자 제거
        elif isinstance(client_ip, str):
            if client_ip.count(",") > 0: # 콤마로 구분되어 여러개의 IP가 넘어온 경우에는 리스트로 변환
                client_ip = client_ip.split(",")
            else:
                client_ip = client_ip.strip()  # 공백 제거
        
        # 로컬 IP는 항상 허용
        if self.is_local_ip(client_ip):
            return await call_next(request)
        
        # 허용된 IP 목록이 비어있으면 모든 요청 허용
        if not self.allowed_ips:
            return await call_next(request)
        
        # 허용된 IP 목록에 있는지 확인
        try:
            if isinstance(client_ip, str):  # 문자열인 경우
                if client_ip in self.allowed_ips:
                    return await call_next(request)
                # IP 주소 정규화 (예: ::ffff:192.168.1.1 -> 192.168.1.1)
                if client_ip.startswith('::ffff:'):
                    normalized_ip = client_ip[7:]
                    if normalized_ip in self.allowed_ips:
                        return await call_next(request)
            elif isinstance(client_ip, list): # 리스트인 경우
                for ip in client_ip:
                    if ip in self.allowed_ips:
                        return await call_next(request)
                    # IP 주소 정규화
                    if ip.startswith('::ffff:'):
                        normalized_ip = ip[7:]
                        if normalized_ip in self.allowed_ips:
                            return await call_next(request)
        except Exception as e:
            print(f"IP 검증 중 오류 발생: {e}")
                
        # 접근 거부
        print(f"차단된 IP: {client_ip}")
        raise HTTPException(status_code=403, detail=f"Access is not allowed for the ip : {client_ip}")