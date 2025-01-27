from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests
import os
import time

observer = None

class FolderHandler(FileSystemEventHandler):
    def on_created(self, event):
        self._process_event(event)

    def on_modified(self, event):
        self._process_event(event)

    def _process_event(self, event):
        if event.is_directory:
            return

        file_path = event.src_path
        current_mtime = os.path.getmtime(file_path)

        # 서버에서 문서 메타데이터 조회
        try:
            # response = requests.get(
            #     f"http://localhost:8123/document_info",
            #     params={"file_path": file_path},
            #     timeout=10
            # )
            response = requests.get(
                f"http://localhost:8123/document_info",
                params={"file_path": file_path.encode('utf-8')},  # 인코딩 추가
                timeout=10
            )
            response.raise_for_status()
            stored_mtime = response.json().get("last_uploaded", 0)
            
            # 변경 여부 확인
            if current_mtime <= stored_mtime:
                print(f"[SKIP] No changes detected: {file_path}")
                return

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to check metadata: {str(e)}")
            return

        # 업로드 실행
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                response = requests.post(
                    "http://localhost:8123/upload",
                    files=files,
                    timeout=30
                )
                if response.status_code == 200:
                    print(f"[UPLOADED] Success: {file_path}")
                else:
                    print(f"[FAILED] {file_path}: {response.text}")
        except Exception as e:
            print(f"[ERROR] Upload failed: {str(e)}")

def start_monitoring(path="."):
    global observer
    observer = Observer()
    observer.schedule(FolderHandler(), path, recursive=True)
    observer.start()
    print(f"Monitoring started: {path}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def stop_monitoring():
    global observer
    if observer:
        observer.stop()
        observer.join()
        observer = None