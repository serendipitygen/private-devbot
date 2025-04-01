import os
import yaml
import socket
import ipaddress
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Dict, Any, Optional
import ast

class IPRestrictionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config_path: str = "devbot_config.yaml"):
        super().__init__(app)
        self.config_path = config_path
        self.allowed_ips = []
        self.load_config()
        
    def load_config(self):
        """설정 파일에서 허용된 IP 목록을 로드합니다."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as file:
                    config = yaml.safe_load(file)
                    if config and 'allowed_ips' in config:
                        self.allowed_ips = config['allowed_ips']
                        print(f"허용된 IP 목록을 로드했습니다: {self.allowed_ips}")
            else:
                # 설정 파일이 없으면 빈 설정으로 초기화
                self.save_config()
                print(f"설정 파일이 없어 새로 생성했습니다: {self.config_path}")
        except Exception as e:
            print(f"설정 파일 로드 중 오류 발생: {str(e)}")
            # 오류 발생 시 빈 설정으로 초기화
            self.allowed_ips = []
            self.save_config()
    
    def save_config(self):
        """현재 허용된 IP 목록을 설정 파일에 저장합니다."""
        try:
            config = {'allowed_ips': self.allowed_ips}
            with open(self.config_path, 'w') as file:
                yaml.dump(config, file, default_flow_style=False)
            print(f"설정이 저장되었습니다: {self.config_path}")
        except Exception as e:
            print(f"설정 파일 저장 중 오류 발생: {str(e)}")
    
    def get_local_ip(self) -> str:
        """로컬 머신의 IP 주소를 반환합니다."""
        try:
            # 외부 연결을 시도하여 로컬 IP 확인
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            # 연결 실패 시 localhost 반환
            return "127.0.0.1"
    
    def is_local_ip(self, ip: str) -> bool:
        """주어진 IP가 로컬 IP인지 확인합니다."""
        local_ip = self.get_local_ip()
        localhost_ips = ["127.0.0.1", "::1", local_ip]
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
            self.allowed_ips = []
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
        return self.allowed_ips
    
    async def dispatch(self, request: Request, call_next):
        """요청을 처리하고 IP 제한을 적용합니다."""
        # 매 요청마다 설정 파일에서 최신 IP 목록을 로드
        self.load_config()

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
        raise HTTPException(status_code=403, detail="접근이 거부되었습니다. 허용되지 않은 IP입니다.")