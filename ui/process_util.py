import socket
import os
import psutil
import subprocess
from datetime import datetime
import json
from .config_util import load_json_config, get_config_file

def write_pid_to_file(pid, server_pid_file):
    """Write the server process PID to a file for persistence between UI restarts."""
    try:
        with open(server_pid_file, 'w') as f:
            f.write(str(pid))
        print(f"[AdminPanel] Wrote PID {pid} to {server_pid_file}")
        return True
    except Exception as e:
        print(f"[AdminPanel] Error writing PID to file: {e}")
        return False

def read_pid_from_file(server_pid_file):
    """Read the server process PID from file."""
    if not os.path.exists(server_pid_file):
        return None
    try:
        with open(server_pid_file, 'r') as f:
            pid_str = f.read().strip()
            if pid_str and pid_str.isdigit():
                return int(pid_str)
    except Exception as e:
        print(f"[AdminPanel] Error reading PID from file: {e}")
    return None

def is_process_running(pid):
    """Check if a process with the given PID is running."""
    if pid is None:
        return False
    try:
        # psutil.pid_exists is cross-platform
        if psutil.pid_exists(pid):
            return True
    except Exception as e:
        print(f"[AdminPanel] Error checking if process {pid} is running: {e}")
    return False

def is_port_in_use(port):
    """Check if the specified port is already in use."""
    print(f"[AdminPanel] Checking if port {port} is in use...")
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set shorter timeout
        sock.settimeout(1)
        # Try connecting to the port (different from binding)
        result = sock.connect_ex(("127.0.0.1", port))
        is_used = result == 0
        print(f"[AdminPanel] Port {port} is {'IN USE' if is_used else 'FREE'} (connect_ex result: {result})")
        return is_used
    except Exception as e:
        print(f"[AdminPanel] Error checking port {port}: {e}")
        # If we can't check, assume it's not in use
        return False
    finally:
        if sock:
            sock.close()

def get_process_using_port(port):
    """Get information about the process using the specified port."""

    print(f"[AdminPanel] Attempting to find process using port {port}...")
    try:
        # 방법1: netstat로 포트 사용 프로세스 PID 확인
        netstat_result = subprocess.run(
            ['netstat', '-ano'], 
            capture_output=True, 
            text=True, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        print(f"[AdminPanel] Searching netstat output for port :{port}")
        # 포트 사용 PID 추출
        for line in netstat_result.stdout.splitlines():
            config = load_json_config(get_config_file())
            
            
            if (f":{port}" in line or f"{config['ip']}:{port}" in line or f"0.0.0.0:{port}" in line) and \
                ("LISTENING" in line or "ESTABLISHED" in line):
                print(f"[AdminPanel] Found matching port in line: {line}")
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1].strip()
                    print(f"[AdminPanel] Extracted PID: {pid}")
                    try:
                        pid = int(pid)
                        # PID로 프로세스 정보 가져오기
                        try:
                            process = psutil.Process(pid)
                            process_info = {
                                'pid': pid,
                                'name': process.name(),
                                'create_time': datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S'),
                                'cmd': ' '.join(process.cmdline()) if len(' '.join(process.cmdline())) < 100 else ' '.join(process.cmdline())[:100] + '...'
                            }
                            print(f"[AdminPanel] Found process info: {process_info}")
                            return process_info
                        except psutil.NoSuchProcess:
                            print(f"[AdminPanel] Process with PID {pid} no longer exists")
                            return {'pid': pid, 'name': '알 수 없음', 'create_time': '알 수 없음', 'cmd': '알 수 없음'}
                    except ValueError:
                        print(f"[AdminPanel] Could not convert PID to integer: {pid}")
                        pass
        
        # 방법2: 더 확실한 방법으로 커스텀 커맨드 실행
        try:
            print(f"[AdminPanel] Trying alternative method to find process using port {port}")
            # netstat에서 좀 더 구체적인 추출
            alt_cmd = f"netstat -ano | findstr :{port} | findstr LISTENING"
            alt_result = subprocess.run(alt_cmd, capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            print(f"[AdminPanel] Alternative command result: {alt_result.stdout}")
            
            # 출력에서 PID 추출
            for line in alt_result.stdout.splitlines():
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            pid = int(pid)
                            process = psutil.Process(pid)
                            process_info = {
                                'pid': pid,
                                'name': process.name(),
                                'create_time': datetime.fromtimestamp(process.create_time()).strftime('%Y-%m-%d %H:%M:%S'),
                                'cmd': ' '.join(process.cmdline()) if len(' '.join(process.cmdline())) < 100 else ' '.join(process.cmdline())[:100] + '...'
                            }
                            print(f"[AdminPanel] Found process info (alt method): {process_info}")
                            return process_info
                        except (ValueError, psutil.NoSuchProcess) as e:
                            print(f"[AdminPanel] Error in alternative method: {e}")
        except Exception as alt_e:
            print(f"[AdminPanel] Alternative method failed: {alt_e}")
        
        print(f"[AdminPanel] No process found using port {port}")
        return None
    except Exception as e:
        print(f"[AdminPanel] Error getting process using port {port}: {e}")
        return None

def kill_process(pid):
    """Kill the process with the specified PID."""
    try:
        # Windows에서는 taskkill 명령어가 더 확실함
        subprocess.run(
            ['taskkill', '/F', '/PID', str(pid)], 
            check=True, 
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return True
    except Exception as e:
        print(f"[AdminPanel] Error killing process {pid}: {e}")
        return False