import os
import yaml
import socket
import ipaddress
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Dict, Any, Optional
import ast
from typing import Set

try:
    import netifaces
except ImportError:
    netifaces = None


class IPRestrictionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config_path: str = "devbot_config.yaml"):
        super().__init__(app)
        self.is_allowed_all_ips = False
        self.config_path = config_path
        self.allowed_ips = set()
        self.load_config()
        
    def load_config(self):
        """설정 파일에서 허용된 IP 목록을 로드합니다.
        파일이 없거나 IP 목록이 비어있는 경우 현재 서버의 IP를 자동으로 등록합니다.
        """
        try:
            config_exists = os.path.exists(self.config_path)
            config_loaded = False
            
            if config_exists:
                with open(self.config_path, 'r') as file:
                    config = yaml.safe_load(file)
                    if config and 'allowed_ips' in config:
                        self.allowed_ips = set(config['allowed_ips'])
                        self.is_allowed_all_ips = config['is_allowed_all_ips'] if config['is_allowed_all_ips'] else False  # 허용된 IP가 없으면 모든 IP 허용
                        config_loaded = True
                        print(f"허용된 IP 목록을 로드했습니다: {self.allowed_ips}")
            
            # 설정 파일이 없거나 IP 목록이 비어있는 경우 로컬 IP를 자동으로 등록
            if not config_exists or not config_loaded or not self.allowed_ips:
                local_ips = self.get_local_ips()
                self.allowed_ips = local_ips
                self.save_config()
                print(f"허용 IP가 설정되어 있지 않아 현재 서버 IP({local_ips})를 자동으로 등록했습니다.")
        except Exception as e:
            print(f"설정 파일 로드 중 오류 발생: {str(e)}")
            local_ips = self.get_local_ips()
            self.allowed_ips = local_ips
            self.save_config()
            print(f"오류 발생으로 현재 서버 IP({local_ips})를 자동으로 등록했습니다.")
    
    def save_config(self):
        """현재 허용된 IP 목록을 설정 파일에 저장합니다."""
        try:
            config = {'allowed_ips': list(self.allowed_ips), 'is_allowed_all_ips': self.is_allowed_all_ips}
            with open(self.config_path, 'w') as file:
                yaml.dump(config, file, default_flow_style=False)
            print(f"설정이 저장되었습니다: {self.config_path}")
        except Exception as e:
            print(f"설정 파일 저장 중 오류 발생: {str(e)}")
    
    def get_local_ips(self) -> Set[str]:
        """
        모든 OS에서 현재 PC의 IPv4 주소를 set 형태로 반환합니다.
        - loopback(127.x.x.x)은 자동으로 제외
        - netifaces가 없으면 기본 소켓 방식 결과만 반환
        """
        ips: Set[str] = set()

        # 1) UDP 소켓 방식으로 기본 라우팅된 로컬 IP 얻기
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                addr = s.getsockname()[0]
                if not addr.startswith("127."):
                    ips.add(addr)
        except Exception:
            pass # 네트워크 연결 불가 시 무시

        # 2) netifaces가 설치되어 있으면 모든 인터페이스 순회
        if netifaces:
            for iface in netifaces.interfaces():
                try:
                    addrs = netifaces.ifaddresses(iface)
                    for link in addrs.get(netifaces.AF_INET, []):
                        addr = link.get("addr")
                        # loopback 제외
                        if addr and not addr.startswith("127."):
                            ips.add(addr)
                except Exception:
                    # 해당 인터페이스 처리 중 오류 발생 시 건너뜀
                    continue

        return ips
    
    def get_local_ips2(self) -> set:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()

            # 여러 개의 IP 주소를 찾기 위해, 네트워크 인터페이스를 반복
            ips = {local_ip}
            for interface, addr in socket.getifaddrs(socket.AF_INET).items():
                if addr != local_ip:
                    ips.add(addr)

            return ips
        except Exception as e:
            # 연결 실패 시 빈 Set 반환
            print(f"로컬 IP 검색 중 오류 발생: {str(e)}")
            return set()
    
    def is_local_ip(self, ip: str) -> bool:
        """주어진 IP가 로컬 IP인지 확인합니다."""
        local_ips = self.get_local_ips()
        localhost_ips = list({"127.0.0.1", "::1"} | local_ips)
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
            self.allowed_ips = self.get_local_ips()
            self.is_allowed_all_ips = True
            self.save_config()
            return {
                "status": "success",
                "valid_ips": [],
                "invalid_ips": [],
                "message": "모든 IP 허용으로 설정되었습니다."
            }
        
        for ip in ips:
            try:
                # IP 주소 유효성 검사
                ipaddress.ip_address(ip)
                valid_ips.append(ip)
            except ValueError:
                invalid_ips.append(ip)
        
        if valid_ips:
            self.allowed_ips = valid_ips
            self.is_allowed_all_ips = False
            self.save_config()
        
        return {
            "status": "success" if not invalid_ips else "partial_success",
            "valid_ips": valid_ips,
            "invalid_ips": invalid_ips,
            "message": "IP 목록이 업데이트되었습니다."
        }
    
    def get_allowed_ips(self) -> List[str]:
        """현재 허용된 IP 목록을 반환합니다."""
        # 설정 파일에서 최신 IP 목록을 다시 로드
        self.load_config()
        return list(self.allowed_ips)
    
    async def dispatch(self, request: Request, call_next):
        """요청을 처리하고 IP 제한을 적용합니다."""
        # 매 요청마다 설정 파일에서 최신 IP 목록을 로드
        self.load_config()

        if self.is_allowed_all_ips:
            return await call_next(request)

        from fastapi import FastAPI, Request
        client_ip = request.headers.get("X-Real-IP") or request.client.host

        if client_ip.startswith("["):  
            client_ip = ast.literal_eval(client_ip)
        elif client_ip.startswith("::ffff:"):
            client_ip = client_ip[7:]  # IPv4-mapped IPv6 address 형식인 경우 IPv4 부분만 추출
        elif client_ip.startswith("fe80:"):
            client_ip = client_ip.split("%")[0]  # 링크 로컬 IPv6 주소의 경우 인터페이스 식별자 제거
        elif isinstance(client_ip, str):
            client_ip = client_ip.strip()  # 공백 제거
        
        # 로컬 IP는 항상 허용
        if self.is_local_ip(client_ip):
            return await call_next(request)
        
        # 허용된 IP 목록이 비어있으면 모든 요청 허용
        if not self.allowed_ips:
            return await call_next(request)
        
        # 허용된 IP 목록에 있는지 확인
        if isinstance(client_ip, str):  # 문자열인 경우에만 검사
            if client_ip in self.allowed_ips:
                return await call_next(request)
        elif isinstance(client_ip, list): # 리스트인 경우
            for ip in client_ip:
                if ip in self.allowed_ips:
                    return await call_next(request)
                
        # 접근 거부
        print(f"차단된 IP: {client_ip}")
        raise HTTPException(status_code=403, detail=f"접근이 거부되었습니다. 허용되지 않은 IP입니다: {client_ip}")