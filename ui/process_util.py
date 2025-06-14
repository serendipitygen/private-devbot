import socket
import os
import psutil
import subprocess
from datetime import datetime
from logger_util import ui_logger


def is_port_in_use(port):
    """Check if the specified port is already in use."""
    ui_logger.info(f"[AdminPanel] Checking if port {port} is in use...")
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        sock.settimeout(1)
        
        result = sock.connect_ex(("127.0.0.1", int(port)))
        is_used = result == 0
        ui_logger.info(f"[AdminPanel] Port {port} is {'IN USE' if is_used else 'FREE'} (connect_ex result: {result})")
        return is_used
    except Exception as e:
        ui_logger.exception(f"[AdminPanel] Error checking port {port}: {e}")
        # If we can't check, assume it's not in use
        return False
    finally:
        if sock:
            sock.close()

def get_process_using_port(port):
    """Get information about the process using the specified port."""        
    try:
        ui_logger.info(f"[AdminPanel] Trying alternative method to find process using port {port}")
        # netstat에서 좀 더 구체적인 추출
        alt_cmd = f"netstat -ano | findstr :{port} | findstr LISTENING"
        alt_result = subprocess.run(alt_cmd, capture_output=True, text=True, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        ui_logger.debug(f"[AdminPanel] Alternative command result: {alt_result.stdout}")
        
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

                        # 프로세스 정보가 있으면 추가
                        # 메시지 텍스트
                        message_text = f"기존 포트({port})가 이미 사용 중입니다.\n다른 포트를 선택해주세요."
                        
                        if process_info:
                            message_text += f"\n\n포트 {port}를 사용 중인 프로세스:\n"
                            message_text += f"PID: {process_info['pid']}\n"
                            message_text += f"프로세스 이름: {process_info['name']}\n"
                            message_text += f"생성 시간: {process_info['create_time']}\n"
                            message_text += f"명령어: {process_info['cmd']}"
                        return process_info, message_text
                    except (ValueError, psutil.NoSuchProcess) as e:
                        ui_logger.exception(f"[AdminPanel] Error in alternative method: {e}")
    except Exception as alt_e:
        ui_logger.exception(f"[AdminPanel] Alternative method failed: {alt_e}")
    
    ui_logger.info(f"[AdminPanel] No process found using port {port}")
    return None, None
    
def kill_process2(pid):
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
        ui_logger.exception(f"[AdminPanel] Error killing process {pid}: {e}")
        return False
    
def kill_process_by_pids(pids, force: bool = True):
    if type(pids) != list:
        pids = [pids]

    for pid in pids:
        try_count = 5
        is_success = False
        while try_count > 0:
            try:
                if _kill_process(pid, force):
                    is_success = True
                    break
            except:
                try_count -= 1
                continue

        if not is_success:
            return False
    return True

def _kill_process(pid, force: bool = True):
    try:
        proc = psutil.Process(pid)
        if force:
            proc.kill()
        else:
            proc.terminate()
        proc.wait(tiemout=1)
        return True
    except psutil.NoSuchProcess as e:
        return True
    except (psutil.AccessDenied, psutil.TimeoutExpired) as e:
        return False