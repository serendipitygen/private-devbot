import threading
import queue
import os
from typing import Callable, Optional, Dict, Any, List
from datetime import datetime

class UploadQueueManager:
    def __init__(self, max_queue_size: int = 10000):
        self.upload_queue = queue.Queue(maxsize=max_queue_size)
        self.subscribers: Dict[str, Callable] = {}
        self.processing = False
        self._lock = threading.Lock()

    def add_file(self, file_path: str) -> bool:
        """파일을 업로드 큐에 추가합니다."""
        try:
            # 파일의 마지막 수정 시간을 가져옴
            last_modified = os.path.getmtime(file_path)
            file_info = {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'status': 'pending',
                'added_time': datetime.now().timestamp(),
                'last_modified': last_modified
            }
            self.upload_queue.put(file_info, block=False)
            self._notify_subscribers('file_added', file_info)
            return True
        except queue.Full:
            return False

    def get_queue_size(self) -> int:
        """현재 큐의 크기를 반환합니다."""
        return self.upload_queue.qsize()

    def get_remaining_capacity(self) -> int:
        """남은 큐 용량을 반환합니다."""
        return self.upload_queue.maxsize - self.upload_queue.qsize()

    def get_next_file(self) -> Dict[str, Any]:
        """다음 처리할 파일을 큐에서 가져옵니다."""
        return self.upload_queue.get()

    def mark_file_complete(self, file_path: str):
        """파일 처리가 완료되었음을 표시합니다."""
        file_info = {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'status': 'completed',
            'completed_time': datetime.now().timestamp()
        }
        self._notify_subscribers('file_completed', file_info)

    def mark_file_failed(self, file_path: str, error: str):
        """파일 처리 실패를 표시합니다."""
        file_info = {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'status': 'failed',
            'error': error,
            'failed_time': datetime.now().timestamp()
        }
        self._notify_subscribers('file_failed', file_info)

    def subscribe(self, event_type: str, callback: Callable):
        """이벤트 구독을 등록합니다."""
        with self._lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            self.subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        """이벤트 구독을 해제합니다."""
        with self._lock:
            if event_type in self.subscribers:
                self.subscribers[event_type].remove(callback)

    def _notify_subscribers(self, event_type: str, data: Dict[str, Any]):
        """구독자들에게 이벤트를 알립니다."""
        with self._lock:
            if event_type in self.subscribers:
                for callback in self.subscribers[event_type]:
                    try:
                        callback(data)
                    except Exception as e:
                        print(f"Error notifying subscriber: {e}")

    def start_processing(self):
        """파일 처리 시작"""
        self.processing = True

    def stop_processing(self):
        """파일 처리 중지"""
        self.processing = False
